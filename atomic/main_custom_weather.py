#!/usr/bin/env python3
"""
Custom training pipeline for skill tasks.
Loads every *.json file under a skills directory (one task per file) and
converts the items into the task-based learning format.
"""

import torch
from transformers import AutoTokenizer
import argparse
import os
import random
import numpy as np
import json
from pathlib import Path
from typing import List, Dict, Tuple

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

def load_skill_datasets(data_dir: str) -> Tuple[List[Dict], List[str]]:
    """
    Load every *.json file under ``data_dir`` and convert each item into the
    task-based learning format. The filename (without ``.json``) becomes the
    task name.

    Each input item is expected to look like::

        {"query": "...", "function_name": "...", "arguments": {...}}

    and is converted into::

        {
            "instruction": f"Using {task_name} functions, get correct result with given query",
            "query":       item["query"],
            "tasks":       [task_name],
            "responses":   [json.dumps({"function_name": ..., "arguments": ...}, ensure_ascii=False)],
        }

    Returns (formatted_data, task_names) where ``task_names`` is sorted & deduped.
    """
    data_path = Path(data_dir)
    if not data_path.is_dir():
        raise FileNotFoundError(f"Skill dataset directory not found: {data_dir}")

    json_files = sorted(data_path.glob('*.json'))
    if not json_files:
        raise FileNotFoundError(f"No *.json files found in {data_dir}")

    formatted_data: List[Dict] = []
    task_names: List[str] = []

    for json_file in json_files:
        task_name = json_file.stem
        task_names.append(task_name)
        instruction = f"Using {task_name} functions, get correct result with given query"

        with open(json_file, 'r', encoding='utf-8') as f:
            raw_items = json.load(f)

        if not isinstance(raw_items, list):
            print(f"⚠️  {json_file.name}: top-level JSON is not a list — skipping")
            continue

        count = 0
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            if 'query' not in item or 'function_name' not in item:
                continue

            response_obj = {
                "function_name": item['function_name'],
                "arguments": item.get('arguments', {}),
            }
            sample = {
                'instruction': instruction,
                'query': item['query'],
                'tasks': [task_name],
                'responses': [json.dumps(response_obj, ensure_ascii=False)],
            }
            formatted_data.append(sample)
            count += 1

        print(f"   - {json_file.name}: {count} sample(s) loaded as task '{task_name}'")

    print(f"✅ Loaded and formatted {len(formatted_data)} samples across {len(json_files)} task file(s).")
    return formatted_data, sorted(set(task_names))

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
    default_data_dir = os.path.join(script_dir, "..", "skills", "generated_datasets")

    parser = argparse.ArgumentParser(description='Custom Skill Task Learning')
    parser.add_argument('--data_dir', type=str, default=default_data_dir,
                        help='Directory containing skill dataset JSON files (one task per file)')
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
    
    # Load and format data — task names are derived from JSON filenames
    full_data, task_names = load_skill_datasets(args.data_dir)
    print(f"📚 Discovered {len(task_names)} task(s): {task_names}")
    tokenizer, is_extended = add_reserved_special_tokens(tokenizer, len(task_names))
    
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
    print("\nCustom skill task learning pipeline completed!")

if __name__ == "__main__":
    main()
