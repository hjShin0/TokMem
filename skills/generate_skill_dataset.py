#!/usr/bin/env python3
"""
Skill Dataset Generator

This script generates training data for skill-based tasks by:
1. Loading skill markdown files from skills/MDs/
2. Using an LLM to generate hypothetical user queries and corresponding function calls
3. Saving the dataset in a format compatible with NaturalInstructionsTaskDataset

The generated dataset follows the format:
{
    "instruction": "Using {skill_name} functions, get correct result with given query",
    "query": "{user_query}",
    "tasks": ["{skillTask}"],
    "responses": ["{\"function_name\": \"...\", \"arguments\": {...}}"]
}
"""

import os
import json
import argparse
import re
from typing import List, Dict, Any, Optional
from pathlib import Path
import hashlib


def load_skill_markdown(md_path: str) -> str:
    """Load the content of a skill markdown file."""
    with open(md_path, 'r', encoding='utf-8') as f:
        return f.read()


def extract_skill_info(markdown_content: str) -> Dict[str, Any]:
    """Extract key information from skill markdown content."""
    info = {
        'id': '',
        'name': '',
        'description': '',
        'triggers': [],
        'verbs': [],
        'full_content': markdown_content
    }
    
    # Extract frontmatter
    frontmatter_match = re.search(r'---\n(.*?)\n---', markdown_content, re.DOTALL)
    if frontmatter_match:
        frontmatter = frontmatter_match.group(1)
        
        # Extract id
        id_match = re.search(r'id:\s*(.+)', frontmatter)
        if id_match:
            info['id'] = id_match.group(1).strip()
        
        # Extract name
        name_match = re.search(r'name:\s*(.+)', frontmatter)
        if name_match:
            info['name'] = name_match.group(1).strip()
        
        # Extract description
        desc_match = re.search(r'description:\s*(.+)', frontmatter)
        if desc_match:
            info['description'] = desc_match.group(1).strip()
        
        # Extract triggers
        triggers_match = re.search(r'triggers:\s*\[(.+?)\]', frontmatter)
        if triggers_match:
            info['triggers'] = [t.strip() for t in triggers_match.group(1).split(',')]
    
    # Extract verbs (function names) from the markdown
    # Look for patterns like "### verb" under the "## Verbs" section
    verbs_section = re.search(r'## Verbs\n(.*?)(?:## |\Z)', markdown_content, re.DOTALL)
    if verbs_section:
        verb_matches = re.findall(r'### (\w+)', verbs_section.group(1))
        info['verbs'] = verb_matches
    
    return info


def generate_llm_prompt(skill_info: Dict[str, Any], num_samples: int = 5) -> str:
    """Generate a prompt for the LLM to create query-response pairs."""
    
    prompt = f"""You are a dataset generation assistant. Your task is to create training data for a skill-based AI assistant.

## Skill Information

**Skill ID:** {skill_info['id']}
**Skill Name:** {skill_info['name']}
**Skill Description:** {skill_info['description']}
**Trigger Keywords:** {', '.join(skill_info['triggers'])}
**Available Functions (Verbs):** {', '.join(skill_info['verbs'])}

## Full Skill Documentation

{skill_info['full_content']}

## Task

Generate {num_samples} diverse hypothetical user queries that would require using this skill. For each query, provide the corresponding function call that the AI assistant should make.

### Output Format

You must respond with a valid JSON array. Each element must have this exact structure:

```json
[
  {{
    "query": "A realistic user request that requires this skill",
    "function_name": "the exact function/verb name from the skill documentation",
    "arguments": {{
      "param1": "value1",
      "param2": "value2"
    }}
  }}
]
```

### Requirements

1. **query**: Must be a natural, realistic user request (not a command). It should be something a real user would say when they need this skill.
2. **function_name**: Must match one of the available functions listed above.
3. **arguments**: Must contain the parameters needed for that function call, based on the skill documentation.

### Example Output Format (for a weather skill)

```json
[
  {{
    "query": "What's the weather like in Seoul today?",
    "function_name": "current",
    "arguments": {{
      "location": "Seoul"
    }}
  }},
  {{
    "query": "Will it rain in Paris tomorrow?",
    "function_name": "forecast",
    "arguments": {{
      "location": "Paris,France"
    }}
  }}
]
```

Now, generate {num_samples} diverse query-response pairs for the {skill_info['name']} skill. Make sure the queries are varied and cover different use cases of the skill."""

    return prompt


def call_llm_api(prompt: str, api_key: str, model: str = "gpt-4o-mini") -> str:
    """Call the LLM API to generate responses.
    
    This function supports multiple LLM providers:
    - OpenAI (default)
    - You can extend this to support other providers
    """
    import urllib.request
    import urllib.error
    
    # Using OpenAI API format
    url = "https://api.openai.com/v1/chat/completions"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.7,
        "max_tokens": 2000
    }
    
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode('utf-8'),
            headers=headers,
            method='POST'
        )
        
        with urllib.request.urlopen(req, timeout=60) as response:
            result = json.loads(response.read().decode('utf-8'))
            return result['choices'][0]['message']['content']
    
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8') if e.fp else ""
        raise Exception(f"API request failed with status {e.code}: {error_body}")
    except Exception as e:
        raise Exception(f"Failed to call LLM API: {str(e)}")


def parse_llm_response(response: str) -> List[Dict[str, Any]]:
    """Parse the LLM response to extract query-response pairs."""
    
    # Try to find JSON array in the response
    json_match = re.search(r'\[\s*\{.*?\}\s*\]', response, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass
    
    # If no JSON found, try to parse line by line
    items = []
    return items


def format_for_natural_instructions(
    parsed_items: List[Dict[str, Any]], 
    skill_info: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Format the parsed items for NaturalInstructionsTaskDataset compatibility."""
    
    formatted_data = []
    skill_task_name = f"{skill_info['name'].lower().replace(' ', '')}Task"
    
    # Create instruction template
    instruction = f"Using {skill_info['name'].lower()} functions, get correct result with given query"
    
    for item in parsed_items:
        if 'query' not in item or 'function_name' not in item:
            continue
        
        # Create the response JSON as expected by the training pipeline
        response_obj = {
            "function_name": item['function_name'],
            "arguments": item.get('arguments', {})
        }
        
        formatted_item = {
            'instruction': instruction,
            'query': item['query'],
            'tasks': [skill_task_name],
            'responses': [json.dumps(response_obj, ensure_ascii=False)]
        }
        
        formatted_data.append(formatted_item)
    
    return formatted_data


def generate_dataset_for_skill(
    md_path: str, 
    api_key: str, 
    model: str,
    num_samples: int = 5,
    output_dir: str = "generated_datasets"
) -> Dict[str, Any]:
    """Generate dataset for a single skill."""
    
    print(f"\n📄 Processing skill: {md_path}")
    
    # Load and parse skill markdown
    markdown_content = load_skill_markdown(md_path)
    skill_info = extract_skill_info(markdown_content)
    
    print(f"   Skill: {skill_info['name']} ({skill_info['id']})")
    print(f"   Functions: {skill_info['verbs']}")
    
    # Generate LLM prompt
    prompt = generate_llm_prompt(skill_info, num_samples)
    
    # Call LLM API
    print(f"   Calling LLM API ({model})...")
    try:
        llm_response = call_llm_api(prompt, api_key, model)
    except Exception as e:
        print(f"   ❌ Error calling LLM: {e}")
        return {
            'skill_name': skill_info['name'],
            'success': False,
            'error': str(e),
            'data': []
        }
    
    # Parse response
    parsed_items = parse_llm_response(llm_response)
    
    if not parsed_items:
        print(f"   ⚠️  No valid items parsed from LLM response")
        # Save raw response for debugging
        debug_file = os.path.join(output_dir, f"{skill_info['name'].lower()}_raw_response.txt")
        with open(debug_file, 'w', encoding='utf-8') as f:
            f.write(llm_response)
        return {
            'skill_name': skill_info['name'],
            'success': False,
            'error': 'No valid items parsed',
            'data': [],
            'raw_response': llm_response
        }
    
    print(f"   ✅ Parsed {len(parsed_items)} items")
    
    # Format for NaturalInstructionsTaskDataset
    formatted_data = format_for_natural_instructions(parsed_items, skill_info)
    
    return {
        'skill_name': skill_info['name'],
        'skill_id': skill_info['id'],
        'success': True,
        'data': formatted_data,
        'num_samples': len(formatted_data)
    }


def save_dataset(all_data: List[Dict[str, Any]], output_path: str):
    """Save the generated dataset to a JSON file."""
    
    # Flatten all data
    flat_data = []
    for skill_result in all_data:
        if skill_result.get('success') and skill_result.get('data'):
            flat_data.extend(skill_result['data'])
    
    # Save as JSON
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(flat_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Saved {len(flat_data)} total samples to {output_path}")


def load_existing_dataset(output_path: str) -> List[Dict[str, Any]]:
    """Load an existing dataset if it exists."""
    if os.path.exists(output_path):
        with open(output_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


def main():
    parser = argparse.ArgumentParser(description='Generate skill-based training datasets')
    parser.add_argument('--skills_dir', type=str, default='skills/MDs',
                        help='Directory containing skill markdown files')
    parser.add_argument('--output_dir', type=str, default='skills/generated_datasets',
                        help='Directory to save generated datasets')
    parser.add_argument('--output_file', type=str, default='train_data.json',
                        help='Output filename for the combined dataset')
    parser.add_argument('--num_samples', type=int, default=5,
                        help='Number of samples to generate per skill')
    parser.add_argument('--api_key', type=str, default=None,
                        help='OpenAI API key (or set OPENAI_API_KEY env var)')
    parser.add_argument('--model', type=str, default='gpt-4o-mini',
                        help='LLM model to use')
    parser.add_argument('--skills', type=str, nargs='*', default=None,
                        help='Specific skill files to process (default: all .md files)')
    parser.add_argument('--resume', action='store_true',
                        help='Resume from existing dataset if found')
    
    args = parser.parse_args()
    
    # Get API key
    api_key = args.api_key or os.environ.get('OPENAI_API_KEY')
    if not api_key:
        print("❌ Error: OPENAI_API_KEY environment variable not set and --api_key not provided")
        print("   Please set OPENAI_API_KEY or provide --api_key")
        return
    
    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Output file path
    output_path = os.path.join(args.output_dir, args.output_file)
    
    # Load existing dataset if resuming
    existing_data = []
    if args.resume and os.path.exists(output_path):
        print(f"📂 Loading existing dataset from {output_path}")
        existing_data = load_existing_dataset(output_path)
        print(f"   Found {len(existing_data)} existing samples")
    
    # Find skill files
    skills_dir = Path(args.skills_dir)
    if args.skills:
        skill_files = [skills_dir / s for s in args.skills]
    else:
        skill_files = list(skills_dir.glob('*.md'))
    
    if not skill_files:
        print(f"❌ No skill files found in {args.skills_dir}")
        return
    
    print(f"📚 Found {len(skill_files)} skill files:")
    for sf in skill_files:
        print(f"   - {sf.name}")
    
    # Process each skill
    all_results = []
    for skill_file in skill_files:
        result = generate_dataset_for_skill(
            md_path=str(skill_file),
            api_key=api_key,
            model=args.model,
            num_samples=args.num_samples,
            output_dir=args.output_dir
        )
        all_results.append(result)
        
        # Save intermediate results
        save_dataset(all_results, output_path)
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 GENERATION SUMMARY")
    print("=" * 50)
    
    total_samples = 0
    successful = 0
    failed = 0
    
    for result in all_results:
        status = "✅" if result.get('success') else "❌"
        samples = result.get('num_samples', 0)
        total_samples += samples
        if result.get('success'):
            successful += 1
        else:
            failed += 1
        print(f"   {status} {result.get('skill_name', 'Unknown')}: {samples} samples")
        if not result.get('success') and result.get('error'):
            print(f"       Error: {result['error']}")
    
    print(f"\n📈 Total: {total_samples} samples from {successful} successful, {failed} failed skills")
    print(f"💾 Output: {output_path}")


if __name__ == "__main__":
    main()