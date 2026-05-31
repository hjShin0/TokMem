#!/usr/bin/env python3
"""
Custom training pipeline for Weather Task
Converts custom JSON data into the task-based learning format.
"""

import torch
from transformers import AutoTokenizer
import argparse
import os
import random
import numpy as np
import json
from typing import List, Dict

# Import our custom modules
from task_model import TaskCallingModel, print_model_info
from task_dataset import (
    NaturalInstructionsTaskDataset,
    collate_fn
)
from torch.utils.data import DataLoader
from task_training import (
    train_task_calling_model,
    demo_task_calling,
    eval_task_calling,
    setup_logging
)

def load_custom_weather_data(json_path: str):
    """
    Load weather data and convert it to the required format:
    instruction: "Using get_weather function, get correct result with given location and time"
    query: {user_query}
    tasks: ["weatherTask"]
    responses: {trajectory}
    """
    if not os.path.exists(json_path):
        raise FileNotFoundError(f"Data file not found: {json_path}")
    
    with open(json_path, 'r', encoding='utf-8') as f:
        raw_data = json.load(f)
    
    formatted_data = []
    
    def process_item(item):
        if isinstance(item, list):
            for sub_item in item:
                process_item(sub_item)
            return

        if 'user_query' in item and 'trajectory' in item:
            # Handle trajectory as string if it's a dict/list
            trajectory = item['trajectory']
            if not isinstance(trajectory, str):
                trajectory = json.dumps(trajectory, ensure_ascii=False)
            
            sample = {
                'instruction': "Using get_weather function, get correct result with given location and time",
                'query': item['user_query'],
                'tasks': ["weatherTask"],
                'responses': [trajectory]
            }
            print(sample)
            formatted_data.append(sample)

    process_item(raw_data)
    
    print(f"✅ Loaded and formatted {len(formatted_data)} weather samples.")
    return formatted_data

def add_reserved_special_tokens(tokenizer, num_of_tasks):
    """Add reserved special tokens to the tokenizer"""
    start_idx = len([t for t in tokenizer.get_vocab() if t.startswith("<|reserved_special_token_")])

    if num_of_tasks <= start_idx:
        return tokenizer, False
    else:
        num_additional_tokens = num_of_tasks - start_idx
        new_tokens = [f"<|reserved_special_token_{i}|>" for i in range(start_idx, start_idx + num_additional_tokens)]
        added = tokenizer.add_special_tokens({'additional_special_tokens': new_tokens})
        assert added == num_additional_tokens, f"Expected to add {num_additional_tokens} tokens, but added {added}"

        return tokenizer, True

def set_random_seed(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    os.environ['PYTHONHASHSEED'] = str(seed)
    print(f"Random seed set to: {seed}")

def main():
    # Detect script directory for relative path resolution (useful in WSL/Linux)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # Go up one level to TokMem/ and then to skill_data_generation/...
    default_data_path = os.path.join(script_dir, "..", "..", "skill_data_generation", "skills", "weather", "train_data.json")
    
    parser = argparse.ArgumentParser(description='Custom Weather Task Learning')
    parser.add_argument('--data_path', type=str, default=default_data_path, 
                        help='Path to weather train_data.json')
    parser.add_argument('--model_name', type=str, default="meta-llama/Llama-3.2-3B", 
                        help='HuggingFace model name')
    parser.add_argument('--batch_size', type=int, default=1, help='Training batch size')
    parser.add_argument('--eval_batch_size', type=int, default=8, help='Evaluation batch size')
    parser.add_argument('--max_length', type=int, default=1024, help='Maximum sequence length')
    parser.add_argument('--num_epochs', type=int, default=10, help='Number of training epochs')
    parser.add_argument('--lr', type=float, default=0.001, help='Learning rate')
    parser.add_argument('--device', type=str, default="cuda" if torch.cuda.is_available() else "cpu", help='Device to use')
    parser.add_argument('--seed', type=int, default=42, help='Random seed')
    parser.add_argument('--val_ratio', type=float, default=0.1, help='Validation split ratio')
    
    args = parser.parse_args()
    
    set_random_seed(args.seed)
    
    # Set up logging
    training_logger, eval_logger, training_log, evaluation_log, timestamp = setup_logging()
    
    # Load tokenizer
    print(f"Loading tokenizer: {args.model_name}")
    tokenizer = AutoTokenizer.from_pretrained(args.model_name)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.bos_token
    
    # We only have one task: "weatherTask"
    task_names = ["weatherTask"]
    tokenizer, is_extended = add_reserved_special_tokens(tokenizer, len(task_names))
    
    # Load and format data
    full_data = load_custom_weather_data(args.data_path)
    
    # Split data
    random.shuffle(full_data)
    val_size = int(len(full_data) * args.val_ratio)
    train_data = full_data[val_size:]
    val_data = full_data[:val_size]
    
    # Initialize model
    print("Initializing Task Calling Model...")
    model = TaskCallingModel(
        model_name=args.model_name,
        num_tasks=len(task_names),
        task_names=task_names,
        tokenizer=tokenizer,
        device=args.device,
        is_extended=is_extended,
    )
    
    # Create data loaders
    train_dataset = NaturalInstructionsTaskDataset(data=train_data, tokenizer=tokenizer, max_length=args.max_length, model=model)
    val_dataset = NaturalInstructionsTaskDataset(data=val_data, tokenizer=tokenizer, max_length=args.max_length, model=model)
    
    train_dataloader = DataLoader(
        train_dataset,
        batch_size=args.batch_size,
        shuffle=True,
        collate_fn=lambda batch: collate_fn(batch, tokenizer)
    )
    
    val_dataloader = DataLoader(
        val_dataset,
        batch_size=args.eval_batch_size,
        shuffle=False,
        collate_fn=lambda batch: collate_fn(batch, tokenizer)
    )
    
    # Training
    print(f"Starting Training for {args.num_epochs} epochs...")
    train_results = train_task_calling_model(
        model=model,
        dataloader=train_dataloader,
        val_dataloader=val_dataloader,
        num_epochs=args.num_epochs,
        lr=args.lr,
        device=args.device,
        timestamp=timestamp
    )
    
    print(f"Training completed. Avg loss: {train_results['avg_total_loss']:.4f}")
    print("\nCustom weather task learning pipeline completed!")

if __name__ == "__main__":
    main()
