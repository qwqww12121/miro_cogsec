"""Run LLM-only baseline prompts against benchmark answer-free inputs.

This script intentionally does not import the CogSec backend. It calls an
OpenAI-compatible chat-completions endpoint directly and writes one JSON object
per input case:

    {"id": "...", "scenario_type": "...", "prediction": {...}}
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

from openai import OpenAI


REPO_ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_ROOT = REPO_ROOT / "benchmark"

SCENARIOS: Dict[str, Dict[str, Path]] = {
    "fraud_im": {
        "prompt": BENCHMARK_ROOT / "prompts" / "llm_baseline_fraud_im.md",
        "input": BENCHMARK_ROOT / "data" / "llm_baseline_input_fraud_im_v0.1.jsonl",
        "output": BENCHMARK_ROOT / "outputs" / "llm_baseline" / "fraud_im_llm_baseline_v0.1.jsonl",
    },
    "public_opinion": {
        "prompt": BENCHMARK_ROOT / "prompts" / "llm_baseline_public_opinion.md",
        "input": BENCHMARK_ROOT / "data" / "llm_baseline_input_public_opinion_v0.1.jsonl",
        "output": BENCHMARK_ROOT / "outputs" / "llm_baseline" / "public_opinion_llm_baseline_v0.1.jsonl",
    },
    "event_propagation": {
        "prompt": BENCHMARK_ROOT / "prompts" / "llm_baseline_event_propagation.md",
        "input": BENCHMARK_ROOT / "data" / "llm_baseline_input_event_propagation_v0.1.jsonl",
        "output": BENCHMARK_ROOT / "outputs" / "llm_baseline" / "event_propagation_llm_baseline_v0.1.jsonl",
    },
}


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def clean_json_text(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def parse_response(text: str) -> Dict[str, Any]:
    cleaned = clean_json_text(text)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"model returned invalid JSON: {cleaned[:500]}") from exc
    if isinstance(parsed, list):
        if len(parsed) != 1 or not isinstance(parsed[0], dict):
            raise ValueError("model returned a JSON array, but it must contain exactly one object")
        parsed = parsed[0]
    if not isinstance(parsed, dict):
        raise ValueError("model output must be a JSON object")
    return parsed


def run_case(client: OpenAI, model: str, prompt: str, row: Dict[str, Any], temperature: float) -> Dict[str, Any]:
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": (
                    "Return exactly one JSON object for this single input line. "
                    "Do not include Markdown.\n\n"
                    + json.dumps(row, ensure_ascii=False)
                ),
            },
        ],
        temperature=temperature,
        max_tokens=4096,
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content or ""
    parsed = parse_response(content)
    parsed.setdefault("id", row.get("id"))
    parsed.setdefault("scenario_type", row.get("scenario_type"))
    if "prediction" not in parsed or not isinstance(parsed["prediction"], dict):
        raise ValueError("model output must contain prediction object")
    return parsed


def run_case_with_retries(
    client: OpenAI,
    model: str,
    prompt: str,
    row: Dict[str, Any],
    temperature: float,
    retries: int,
    retry_sleep: float,
) -> Dict[str, Any]:
    last_exc: Exception | None = None
    for attempt in range(1, retries + 2):
        try:
            return run_case(client, model, prompt, row, temperature)
        except Exception as exc:
            last_exc = exc
            if attempt > retries:
                break
            print(
                f"  retry {attempt}/{retries} for {row.get('id')}: {exc}",
                flush=True,
            )
            time.sleep(retry_sleep)
    assert last_exc is not None
    raise last_exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run OpenAI-compatible LLM-only benchmark baselines.")
    parser.add_argument("--scenario", choices=SCENARIOS.keys(), required=True)
    parser.add_argument("--input", type=Path, default=None)
    parser.add_argument("--prompt", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--model", default=os.environ.get("LLM_MODEL_NAME", "deepseek-chat"))
    parser.add_argument("--base-url", default=os.environ.get("LLM_BASE_URL", "https://api.deepseek.com"))
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--retry-sleep", type=float, default=2.0)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    api_key = os.environ.get("LLM_API_KEY")
    if not api_key:
        print("LLM_API_KEY is not set", file=sys.stderr)
        return 2

    config = SCENARIOS[args.scenario]
    input_path = args.input or config["input"]
    prompt_path = args.prompt or config["prompt"]
    output_path = args.output or config["output"]

    rows = load_jsonl(input_path)
    if args.limit is not None:
        rows = rows[: args.limit]

    prompt = prompt_path.read_text(encoding="utf-8")
    client = OpenAI(api_key=api_key, base_url=args.base_url)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    outputs: List[Dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        started = time.perf_counter()
        try:
            parsed = run_case_with_retries(
                client=client,
                model=args.model,
                prompt=prompt,
                row=row,
                temperature=args.temperature,
                retries=args.retries,
                retry_sleep=args.retry_sleep,
            )
            outputs.append(parsed)
            elapsed_ms = (time.perf_counter() - started) * 1000
            print(f"[{index}/{len(rows)}] {row.get('id')} ok {elapsed_ms:.1f} ms", flush=True)
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - started) * 1000
            print(f"[{index}/{len(rows)}] {row.get('id')} failed {elapsed_ms:.1f} ms: {exc}", flush=True)
            raise

    output_path.write_text(
        "\n".join(json.dumps(item, ensure_ascii=False) for item in outputs) + "\n",
        encoding="utf-8",
    )
    print(f"llm baseline output: {output_path} ({len(outputs)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
