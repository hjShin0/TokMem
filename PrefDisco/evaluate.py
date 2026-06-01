#!/usr/bin/env python3
"""PrefDisco-inspired evaluation for TokMem-trained skill models.

Compares three variants of the same base model running on three GPUs:

  - measured : base model + loaded TokMem task-token embeddings (.pt checkpoint)
  - oracle   : plain base model given the skill markdown as a system prompt
  - baseline : plain base model with nothing extra

For each query, all three models produce a response. The model and baseline
responses are scored with PrefAlign against the oracle response (exact match,
weights 0.4 / 0.3 / 0.3 for function_name / argument keys / argument values).

NormAlign is left unimplemented for now (PrefDisco formula not yet wired in).
"""

import argparse
import ast
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

# Make atomic/ importable so we can reuse TaskCallingModel
SCRIPT_DIR = Path(__file__).resolve().parent
ATOMIC_DIR = SCRIPT_DIR.parent / "atomic"
if str(ATOMIC_DIR) not in sys.path:
    sys.path.insert(0, str(ATOMIC_DIR))

from task_model import TaskCallingModel  # noqa: E402


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

def parse_function_call(response_text: str) -> Dict:
    """Best-effort parse of a model response into ``{function_name, arguments}``.

    Tolerates strict JSON, Python repr (single-quoted dicts), and optional
    ``json``/``python`` code fences. Returns ``{function_name: None,
    arguments: {}}`` when no parseable object is found.
    """
    text = response_text.strip()
    fence_match = re.match(r"^```(?:json|python)?\s*(.*?)\s*```", text, flags=re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()

    obj_match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not obj_match:
        return {"function_name": None, "arguments": {}}

    candidate = obj_match.group(0)
    for loader in (json.loads, ast.literal_eval):
        try:
            data = loader(candidate)
        except (ValueError, SyntaxError, json.JSONDecodeError):
            continue
        if isinstance(data, dict) and "function_name" in data:
            args = data.get("arguments")
            return {
                "function_name": data.get("function_name"),
                "arguments": args if isinstance(args, dict) else {},
            }
    return {"function_name": None, "arguments": {}}


# ---------------------------------------------------------------------------
# PrefAlign
# ---------------------------------------------------------------------------

def pref_align(prediction: Dict, reference: Dict) -> Dict[str, float]:
    """Exact-match PrefAlign against an oracle reference.

    Components:
      - ``function_name``     : 0.4 if equal else 0.0
      - ``argument_keys``     : 0.3 if key sets are equal else 0.0
      - ``argument_values``   : 0.3 if argument dicts are fully equal else 0.0
    """
    pred_args = prediction.get("arguments") or {}
    ref_args = reference.get("arguments") or {}
    pred_keys = set(pred_args.keys()) if isinstance(pred_args, dict) else set()
    ref_keys = set(ref_args.keys()) if isinstance(ref_args, dict) else set()

    fn_score = 0.4 if prediction.get("function_name") == reference.get("function_name") else 0.0
    keys_score = 0.3 if pred_keys == ref_keys else 0.0
    values_score = 0.3 if pred_args == ref_args else 0.0
    return {
        "function_name": fn_score,
        "argument_keys": keys_score,
        "argument_values": values_score,
        "total": fn_score + keys_score + values_score,
    }


def norm_align(
    measured_pref: float, baseline_pref: float, oracle_pref: float = 1.0
) -> Optional[float]:
    """NormAlign from PrefDisco.

        NormAlign = 100 * (PrefAlign(discovery) - PrefAlign(baseline))
                        / (PrefAlign(oracle)    - PrefAlign(baseline))

    Since PrefAlign is computed against the oracle, ``PrefAlign(oracle) == 1.0``
    by construction, so the denominator collapses to ``1 - PrefAlign(baseline)``.
    Returns ``None`` when the denominator is zero (baseline already matches the
    oracle perfectly — NormAlign is undefined).
    """
    denom = oracle_pref - baseline_pref
    if denom == 0:
        return None
    return 100.0 * (measured_pref - baseline_pref) / denom


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

ORACLE_FORMAT_HINT = (
    "Respond with a single JSON object of the form "
    '{"function_name": "...", "arguments": {...}} '
    "based on the user query. Do not include any other text."
)


def build_measured_prompt(tokenizer, task_name: str, query: str) -> str:
    """Reconstruct the training-time prompt for the measured model.

    Mirrors ``NaturalInstructionsTaskDataset._format_instruction`` for the
    no-few-shot path, branching on Qwen vs. Llama-style chat templates.
    """
    instruction = f"Using {task_name} functions, get correct result with given query"
    name_lower = (tokenizer.name_or_path or "").lower()
    if "qwen" in name_lower:
        return (
            f"<|im_start|>user\n{instruction}\n\n{query}<|im_end|>\n"
            f"<|im_start|>assistant\n"
        )
    return (
        f"<|begin_of_text|><|start_header_id|>user<|end_header_id|>\n"
        f"{instruction}\n\n{query}<|eot_id|>"
        f"<|start_header_id|>assistant<|end_header_id|>"
    )


def build_chat_prompt(tokenizer, system_prompt: Optional[str], user_query: str) -> str:
    """Build a chat prompt via the tokenizer's chat template."""
    messages: List[Dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_query})
    return tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )


# ---------------------------------------------------------------------------
# Model loading (each variant lives on its own GPU)
# ---------------------------------------------------------------------------

def load_measured_model(
    model_name: str, checkpoint_path: str, device: str
) -> Tuple[TaskCallingModel, "AutoTokenizer", List[str]]:
    """Load TokMem-trained model. Reads task_names from the checkpoint itself."""
    ckpt = torch.load(checkpoint_path, map_location="cpu")
    task_names: List[str] = ckpt["task_names"]
    num_tasks = ckpt["num_tasks"]
    decouple = ckpt.get("decouple_embeddings", False)

    tokenizer = AutoTokenizer.from_pretrained(model_name)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.bos_token

    new_tokens = [f"<|reserved_special_token_{i}|>" for i in range(num_tasks)]
    tokenizer.add_special_tokens({"additional_special_tokens": new_tokens})

    model = TaskCallingModel(
        model_name=model_name,
        num_tasks=num_tasks,
        task_names=task_names,
        tokenizer=tokenizer,
        device=device,
        is_extended=True,
        decouple_embeddings=decouple,
    )
    model.load_task_tokens(checkpoint_path)
    model.to(device)
    model.eval()
    return model, tokenizer, task_names


def load_plain_model(model_name: str, device: str):
    """Load a vanilla HF causal LM on the given device (bfloat16 for memory)."""
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.bos_token
    model = AutoModelForCausalLM.from_pretrained(
        model_name, torch_dtype=torch.bfloat16
    ).to(device)
    model.eval()
    return model, tokenizer


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

@torch.no_grad()
def generate_measured(
    model: TaskCallingModel, tokenizer, prompt: str, device: str, max_new_tokens: int
) -> str:
    inputs = tokenizer(prompt, return_tensors="pt").to(device)
    results = model.generate_with_task_prediction(
        inputs["input_ids"],
        inputs["attention_mask"],
        tokenizer,
        max_new_tokens=max_new_tokens,
        do_sample=False,
        temperature=1.0,
        top_p=1.0,
    )
    return results[0]["response"]


@torch.no_grad()
def generate_plain(model, tokenizer, prompt: str, device: str, max_new_tokens: int) -> str:
    inputs = tokenizer(prompt, return_tensors="pt").to(device)
    output = model.generate(
        **inputs,
        max_new_tokens=max_new_tokens,
        do_sample=False,
        pad_token_id=tokenizer.eos_token_id,
    )
    new_tokens = output[0][inputs["input_ids"].shape[1]:]
    return tokenizer.decode(new_tokens, skip_special_tokens=True).strip()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="PrefDisco-style benchmark for TokMem skill models")
    parser.add_argument("--checkpoint", required=True, help="Path to TokMem .pt checkpoint")
    parser.add_argument("--model_name", default="meta-llama/Llama-3.2-3B",
                        help="Base HuggingFace model name (must match the one used during training)")
    parser.add_argument("--skill_md", required=True,
                        help="Path to the skill markdown file (used as the oracle's system prompt)")
    parser.add_argument("--task_name", required=True,
                        help="Task name registered in the measured model (e.g. 'WeatherTask')")
    parser.add_argument("--queries", required=True,
                        help="Path to a txt file with one query per line")
    parser.add_argument("--output", default="evaluate_results.json",
                        help="Where to write per-query results and summary")
    parser.add_argument("--max_new_tokens", type=int, default=256)
    parser.add_argument("--measured_device", default="cuda:0")
    parser.add_argument("--oracle_device", default="cuda:1")
    parser.add_argument("--baseline_device", default="cuda:2")
    args = parser.parse_args()

    skill_md_path = Path(args.skill_md)
    if not skill_md_path.is_file():
        raise FileNotFoundError(f"Skill MD not found: {args.skill_md}")
    skill_md = skill_md_path.read_text(encoding="utf-8")

    queries_path = Path(args.queries)
    if not queries_path.is_file():
        raise FileNotFoundError(f"Query file not found: {args.queries}")
    queries = [
        line.strip()
        for line in queries_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not queries:
        raise ValueError(f"No queries in {args.queries}")

    print(f"📄 Skill MD : {skill_md_path}")
    print(f"📝 Queries  : {len(queries)} from {queries_path}")
    print(f"🎯 Task name: {args.task_name}")
    print()

    print(f"🔧 Loading measured model on {args.measured_device} ...")
    measured_model, measured_tok, task_names = load_measured_model(
        args.model_name, args.checkpoint, args.measured_device
    )
    if args.task_name not in task_names:
        raise ValueError(
            f"Task '{args.task_name}' not in checkpoint task_names={task_names}"
        )

    print(f"🔧 Loading oracle model on {args.oracle_device} ...")
    oracle_model, oracle_tok = load_plain_model(args.model_name, args.oracle_device)

    print(f"🔧 Loading baseline model on {args.baseline_device} ...")
    baseline_model, baseline_tok = load_plain_model(args.model_name, args.baseline_device)
    print()

    oracle_system = skill_md.rstrip() + "\n\n## Response Format\n\n" + ORACLE_FORMAT_HINT

    results: List[Dict] = []
    for q_idx, query in enumerate(queries, 1):
        print(f"[{q_idx}/{len(queries)}] {query}")

        m_prompt = build_measured_prompt(measured_tok, args.task_name, query)
        o_prompt = build_chat_prompt(oracle_tok, oracle_system, query)
        b_prompt = build_chat_prompt(baseline_tok, None, query)

        m_text = generate_measured(
            measured_model, measured_tok, m_prompt, args.measured_device, args.max_new_tokens
        )
        o_text = generate_plain(
            oracle_model, oracle_tok, o_prompt, args.oracle_device, args.max_new_tokens
        )
        b_text = generate_plain(
            baseline_model, baseline_tok, b_prompt, args.baseline_device, args.max_new_tokens
        )

        m_call = parse_function_call(m_text)
        o_call = parse_function_call(o_text)
        b_call = parse_function_call(b_text)

        m_align = pref_align(m_call, o_call)
        o_align = pref_align(o_call, o_call)  # always 1.0; kept explicit for the NormAlign formula
        b_align = pref_align(b_call, o_call)
        n_align = norm_align(m_align["total"], b_align["total"], o_align["total"])

        results.append({
            "query": query,
            "measured":  {"raw": m_text, "parsed": m_call, "pref_align": m_align},
            "oracle":    {"raw": o_text, "parsed": o_call, "pref_align": o_align},
            "baseline":  {"raw": b_text, "parsed": b_call, "pref_align": b_align},
            "norm_align": n_align,
        })

        na_str = "n/a" if n_align is None else f"{n_align:6.2f}"
        print(
            f"   measured PrefAlign={m_align['total']:.3f} | "
            f"baseline PrefAlign={b_align['total']:.3f} | "
            f"NormAlign={na_str}"
        )

    def avg(scores: List[Dict[str, float]], key: str) -> float:
        return sum(s[key] for s in scores) / len(scores) if scores else 0.0

    measured_scores = [r["measured"]["pref_align"] for r in results]
    baseline_scores = [r["baseline"]["pref_align"] for r in results]
    oracle_scores = [r["oracle"]["pref_align"] for r in results]
    keys = ("function_name", "argument_keys", "argument_values", "total")
    measured_avg = {k: avg(measured_scores, k) for k in keys}
    baseline_avg = {k: avg(baseline_scores, k) for k in keys}
    oracle_avg = {k: avg(oracle_scores, k) for k in keys}

    # NormAlign computed from the aggregated PrefAlign totals.
    norm_align_aggregate = norm_align(
        measured_avg["total"], baseline_avg["total"], oracle_avg["total"]
    )
    # Mean of the per-query NormAligns (skipping undefined entries).
    per_query_norm_aligns = [r["norm_align"] for r in results if r["norm_align"] is not None]
    norm_align_per_query_mean = (
        sum(per_query_norm_aligns) / len(per_query_norm_aligns)
        if per_query_norm_aligns else None
    )

    summary = {
        "skill_md": str(skill_md_path),
        "task_name": args.task_name,
        "model_name": args.model_name,
        "checkpoint": args.checkpoint,
        "num_queries": len(queries),
        "measured_avg": measured_avg,
        "oracle_avg": oracle_avg,
        "baseline_avg": baseline_avg,
        "norm_align_aggregate": norm_align_aggregate,
        "norm_align_per_query_mean": norm_align_per_query_mean,
    }

    out_path = Path(args.output)
    out_path.write_text(
        json.dumps({"summary": summary, "per_query": results}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print()
    print("=" * 60)
    print(f"💾 Saved to {out_path}")
    print(f"📈 Measured PrefAlign avg : {measured_avg['total']:.4f}")
    print(f"📉 Baseline PrefAlign avg : {baseline_avg['total']:.4f}")
    print(f"📊 Oracle   PrefAlign avg : {oracle_avg['total']:.4f}")
    na_agg = "n/a" if norm_align_aggregate is None else f"{norm_align_aggregate:.2f}"
    na_pq = "n/a" if norm_align_per_query_mean is None else f"{norm_align_per_query_mean:.2f}"
    print(f"⭐ NormAlign (on means)   : {na_agg}")
    print(f"⭐ NormAlign (per-query)  : {na_pq}")


if __name__ == "__main__":
    main()
