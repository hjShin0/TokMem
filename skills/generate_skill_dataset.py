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
    "responses": ["{'function_name': '...', 'arguments': {...}}"]
}
"""

import os
import json
import argparse
import re
from typing import List, Dict, Any, Optional, Tuple
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


def generate_llm_prompt_batch(skill_infos: List[Dict[str, Any]], num_samples: int = 5) -> str:
    """Generate a single prompt covering multiple skills to minimize API requests."""

    skill_blocks = []
    for idx, info in enumerate(skill_infos, 1):
        skill_blocks.append(
            f"""### Skill {idx}: {info['name']}

- **Skill ID:** `{info['id']}`
- **Description:** {info['description']}
- **Trigger Keywords:** {', '.join(info['triggers'])}
- **Available Functions (Verbs):** {', '.join(info['verbs'])}

#### Full Documentation
{info['full_content']}
"""
        )
    skills_section = "\n---\n".join(skill_blocks)
    skill_ids = [info['id'] for info in skill_infos]
    keys_hint = ', '.join(f'"{sid}"' for sid in skill_ids)

    prompt = f"""You are a dataset generation assistant. Your task is to create training data for a skill-based AI assistant.

You are given **{len(skill_infos)} skills**. For **each skill**, generate **{num_samples} diverse hypothetical user queries** along with the corresponding function call.

## Skills

{skills_section}

## Output Format

Respond with a SINGLE valid JSON object. Its keys MUST be the skill IDs listed below, and each value MUST be an array of exactly {num_samples} samples.

Skill ID keys (use these verbatim): {keys_hint}

Schema:

```json
{{
  "<skill_id>": [
    {{
      "query": "A realistic user request that requires this skill",
      "function_name": "the exact function/verb name from the skill documentation",
      "arguments": {{ "param1": "value1" }}
    }}
  ]
}}
```

## Requirements

1. **query**: A natural, realistic user request (not a command) — something a real user would actually say.
2. **function_name**: Must match one of the available functions for the corresponding skill.
3. **arguments**: Must contain the parameters needed for that function call based on the skill documentation.
4. Each skill must have exactly {num_samples} diverse samples covering different use cases of that skill.
5. Return ONLY the JSON object — no surrounding prose. Code fences are optional.
"""

    return prompt


def call_llm_api(
    prompt: str,
    api_key: str,
    model: str = "gemini-2.0-flash",
    max_output_tokens: int = 4096,
) -> str:
    """Call the Google Gemini API to generate responses."""
    import urllib.request
    import urllib.error

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        f"?key={api_key}"
    )

    headers = {
        "Content-Type": "application/json",
    }

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}],
            }
        ],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": max_output_tokens,
            "topP": 0.95,
            "topK": 40,
        },
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

        candidates = result.get('candidates') or []
        if not candidates:
            raise Exception(f"Gemini returned no candidates: {result}")

        parts = candidates[0].get('content', {}).get('parts') or []
        text_chunks = [p.get('text', '') for p in parts if 'text' in p]
        if not text_chunks:
            raise Exception(f"Gemini response had no text parts: {result}")
        return ''.join(text_chunks)

    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8') if e.fp else ""
        raise Exception(f"API request failed with status {e.code}: {error_body}")
    except Exception as e:
        raise Exception(f"Failed to call LLM API: {str(e)}")


def _strip_code_fences(text: str) -> str:
    """Strip a leading ```json / ``` and trailing ``` from a Gemini response, if present."""
    stripped = text.strip()
    fence_match = re.match(r'^```(?:json)?\s*(.*?)\s*```\s*$', stripped, re.DOTALL)
    if fence_match:
        return fence_match.group(1).strip()
    return stripped


def parse_llm_response_batch(response: str) -> Dict[str, List[Dict[str, Any]]]:
    """Parse a batched Gemini response into {skill_id: [sample, ...]}.

    Accepts the response with or without ```json fences. Items missing
    `query` or `function_name` are dropped silently.
    """
    candidate = _strip_code_fences(response)

    parsed: Any = None
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        # Fallback: locate the outermost JSON object in the text.
        obj_match = re.search(r'\{.*\}', candidate, re.DOTALL)
        if obj_match:
            try:
                parsed = json.loads(obj_match.group(0))
            except json.JSONDecodeError:
                parsed = None

    if not isinstance(parsed, dict):
        return {}

    cleaned: Dict[str, List[Dict[str, Any]]] = {}
    for skill_id, items in parsed.items():
        if not isinstance(items, list):
            continue
        valid = [
            it for it in items
            if isinstance(it, dict) and 'query' in it and 'function_name' in it
        ]
        if valid:
            cleaned[skill_id] = valid
    return cleaned


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


def _estimate_max_output_tokens(num_skills: int, num_samples: int) -> int:
    """Roughly estimate output token budget for a batch.

    ~200 tokens per sample, with a floor of 1024 and a cap of 8192
    (the maxOutputTokens limit for Gemini 2.0 Flash).
    """
    estimate = num_skills * num_samples * 200
    return max(1024, min(estimate + 512, 8192))


def generate_dataset_for_batch(
    skill_md_paths: List[str],
    api_key: str,
    model: str,
    num_samples: int = 5,
    output_dir: str = "generated_datasets",
) -> List[Dict[str, Any]]:
    """Generate datasets for a batch of skills in a SINGLE Gemini request."""

    # Load and parse skill markdown files in the batch
    batch_infos: List[Dict[str, Any]] = []
    for md_path in skill_md_paths:
        markdown_content = load_skill_markdown(md_path)
        info = extract_skill_info(markdown_content)
        info['_md_path'] = md_path
        batch_infos.append(info)

    print(f"\n📦 Batch of {len(batch_infos)} skills:")
    for info in batch_infos:
        print(f"   - {info['name']} ({info['id']})  verbs: {info['verbs']}")

    prompt = generate_llm_prompt_batch(batch_infos, num_samples)
    max_tokens = _estimate_max_output_tokens(len(batch_infos), num_samples)

    print(f"   Calling Gemini API ({model}, max_output_tokens={max_tokens})...")
    try:
        llm_response = call_llm_api(prompt, api_key, model, max_output_tokens=max_tokens)
        print(llm_response)
    except Exception as e:
        print(f"   ❌ Error calling LLM: {e}")
        return [
            {
                'skill_name': info['name'],
                'skill_id': info['id'],
                'success': False,
                'error': str(e),
                'data': [],
            }
            for info in batch_infos
        ]

    parsed_by_skill = parse_llm_response_batch(llm_response)

    if not parsed_by_skill:
        print(f"   ⚠️  No valid items parsed from LLM response")
        batch_label = '_'.join(info['name'].lower().replace(' ', '') for info in batch_infos)[:60]
        debug_file = os.path.join(output_dir, f"batch_{batch_label}_raw_response.txt")
        with open(debug_file, 'w', encoding='utf-8') as f:
            f.write(llm_response)
        return [
            {
                'skill_name': info['name'],
                'skill_id': info['id'],
                'success': False,
                'error': 'No valid items parsed',
                'data': [],
            }
            for info in batch_infos
        ]

    results: List[Dict[str, Any]] = []
    for info in batch_infos:
        items = parsed_by_skill.get(info['id'], [])
        if not items:
            print(f"   ⚠️  {info['name']}: skill missing from batched response")
            results.append({
                'skill_name': info['name'],
                'skill_id': info['id'],
                'success': False,
                'error': 'Skill missing from batched response',
                'data': [],
            })
            continue

        # Save items in their raw {query, function_name, arguments} shape.
        # The training-side loader (atomic/main_custom_weather.py :: load_skill_datasets)
        # converts these into the instruction/tasks/responses format at load time.
        raw_data = [
            {
                'query': it['query'],
                'function_name': it['function_name'],
                'arguments': it.get('arguments', {}),
            }
            for it in items
        ]
        print(f"   ✅ {info['name']}: {len(raw_data)} samples")
        results.append({
            'skill_name': info['name'],
            'skill_id': info['id'],
            'success': True,
            'data': raw_data,
            'num_samples': len(raw_data),
        })

    return results


def save_dataset(
    all_data: List[Dict[str, Any]],
    output_path: str,
    existing_data: Optional[List[Dict[str, Any]]] = None,
):
    """Save the generated dataset to a JSON file, appending to existing data."""

    if existing_data is None:
        existing_data = []

    # Flatten new data from this run
    new_data = []
    for skill_result in all_data:
        if skill_result.get('success') and skill_result.get('data'):
            new_data.extend(skill_result['data'])

    combined_data = existing_data + new_data

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(combined_data, f, indent=2, ensure_ascii=False)

    print(
        f"\n💾 Appended {len(new_data)} new samples "
        f"(existing {len(existing_data)}, total {len(combined_data)}) to {output_path}"
    )


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
    parser.add_argument('--batch_size', type=int, default=5,
                        help='Number of skills to bundle into a SINGLE Gemini request '
                             '(higher = fewer requests, but larger prompt/response). Default: 5')
    parser.add_argument('--api_key', type=str, default=None,
                        help='Gemini API key (or set GEMINI_API_KEY / GOOGLE_API_KEY env var)')
    parser.add_argument('--model', type=str, default='gemini-2.0-flash',
                        help='Gemini model to use (e.g. gemini-2.0-flash, gemini-1.5-flash, gemini-2.0-pro)')
    parser.add_argument('--skills', type=str, nargs='*', default=None,
                        help='Specific skill files to process (default: all .md files)')
    parser.add_argument('--resume', action='store_true',
                        help='Resume from existing dataset if found')
    
    args = parser.parse_args()
    
    # Get API key (Gemini)
    api_key = (
        args.api_key
        or os.environ.get('GEMINI_API_KEY')
        or os.environ.get('GOOGLE_API_KEY')
    )
    if not api_key:
        print("❌ Error: GEMINI_API_KEY / GOOGLE_API_KEY environment variable not set and --api_key not provided")
        print("   Please set GEMINI_API_KEY (or GOOGLE_API_KEY) or provide --api_key")
        return
    
    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Output file path
    output_path = os.path.join(args.output_dir, args.output_file)
    
    # Always load existing dataset so new runs append rather than overwrite
    existing_data = []
    if os.path.exists(output_path):
        print(f"📂 Loading existing dataset from {output_path}")
        existing_data = load_existing_dataset(output_path)
        print(f"   Found {len(existing_data)} existing samples — new samples will be appended")
    
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
    
    # Chunk skills into batches so each Gemini call covers multiple skills
    batch_size = max(1, args.batch_size)
    batches = [
        skill_files[i:i + batch_size]
        for i in range(0, len(skill_files), batch_size)
    ]
    print(f"\n🧮 Will send {len(batches)} Gemini request(s) "
          f"(batch_size={batch_size}, {args.num_samples} samples/skill)")

    all_results: List[Dict[str, Any]] = []
    for batch_idx, batch in enumerate(batches, 1):
        print(f"\n=== Batch {batch_idx}/{len(batches)} ===")
        batch_results = generate_dataset_for_batch(
            skill_md_paths=[str(sf) for sf in batch],
            api_key=api_key,
            model=args.model,
            num_samples=args.num_samples,
            output_dir=args.output_dir,
        )
        all_results.extend(batch_results)

        # Save intermediate results after each batch (appended to existing data)
        save_dataset(all_results, output_path, existing_data=existing_data)
    
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