#!/usr/bin/env python3
"""
Inference script for Weather Task
Loads a trained model and generates responses for user queries.
"""

import torch
from transformers import AutoTokenizer
import argparse
import os
import json

# Import our custom modules
from task_model import TaskCallingModel
from task_training import demo_task_calling

def main():
    parser = argparse.ArgumentParser(description='Inference for Custom Weather Task')
    parser.add_argument('--model_path', type=str, required=True, 
                        help='Path to the saved task tokens (.pt file)')
    parser.add_argument('--model_name', type=str, default="meta-llama/Llama-3.2-3B", 
                        help='HuggingFace model name')
    parser.add_argument('--query', type=str, default="How is the weather in London tomorrow?", 
                        help='User query to test')
    parser.add_argument('--device', type=str, default="cuda" if torch.cuda.is_available() else "cpu", 
                        help='Device to use')
    
    args = parser.parse_args()
    
    # Task name should match what was used during training
    task_names = ["weatherTask"]
    
    # Load tokenizer
    print(f"Loading tokenizer: {args.model_name}")
    tokenizer = AutoTokenizer.from_pretrained(args.model_name)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.bos_token
    
    # Add reserved special tokens (must match training)
    new_tokens = [f"<|reserved_special_token_{i}|>" for i in range(len(task_names))]
    tokenizer.add_special_tokens({'additional_special_tokens': new_tokens})
    
    # Initialize model
    print("Initializing Task Calling Model...")
    model = TaskCallingModel(
        model_name=args.model_name,
        num_tasks=len(task_names),
        task_names=task_names,
        tokenizer=tokenizer,
        device=args.device,
        is_extended=True,
    )
    
    # Load the trained task tokens
    print(f"Loading trained task tokens from: {args.model_path}")
    model.load_task_tokens(args.model_path)
    model.to(args.device)
    model.eval()
    
    # Prepare example for demo function
    example = {
        'instruction': "Using get_weather function, get correct result with given location and time",
        'query': args.query,
        'tasks': ["weatherTask"] # This is for display purpose in demo_task_calling
    }
    
    print("\n" + "="*50)
    print("RUNNING INFERENCE")
    print("="*50)
    print(f"Query: {args.query}")
    
    # Use existing demo function to show result
    demo_task_calling(model, tokenizer, [example], device=args.device)
    
    print("\nInference completed!")

if __name__ == "__main__":
    main()
