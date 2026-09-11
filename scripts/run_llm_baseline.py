import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict

from openai import OpenAI
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_ROOT = ROOT / "benchmark"
if os.environ.get("MIRO_DISABLE_DOTENV", "false").lower() != "true":
    load_dotenv(ROOT / ".env", override=False)

SCENARIOS = {
    "fraud_im": {
        "input": BENCHMARK_ROOT / "data" / "llm_baseline_input_fraud_im_v0.1.jsonl",
        "prompt": BENCHMARK_ROOT / "prompts" / "llm_baseline_fraud_im.md",
        "output": BENCHMARK_ROOT / "outputs" / "llm_baseline" / "fraud_im_llm_baseline_v0.1.jsonl",
    },
    "public_opinion": {
        "input": BENCHMARK_ROOT / "data" / "llm_baseline_input_public_opinion_v0.1.jsonl",
        "prompt": BENCHMARK_ROOT / "prompts" / "llm_baseline_public_opinion.md",
        "output": BENCHMARK_ROOT / "outputs" / "llm_baseline" / "public_opinion_llm_baseline_v0.1.jsonl",
    },
    "event_propagation": {
        "input": BENCHMARK_ROOT / "data" / "llm_baseline_input_event_propagation_v0.1.jsonl",
        "prompt": BENCHMARK_ROOT / "prompts" / "llm_baseline_event_propagation.md",
        "output": BENCHMARK_ROOT / "outputs" / "llm_baseline" / "event_propagation_llm_baseline_v0.1.jsonl",
    },
}


def read_jsonl(path: Path) -> list[Dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no} invalid JSON: {exc}") from exc
    return rows


def parse_json_response(text: str) -> Dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start : end + 1])
        raise


def make_client() -> OpenAI:
    api_key = os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("LLM_BASE_URL")
    if not api_key:
        raise RuntimeError("缺少 LLM_API_KEY 或 OPENAI_API_KEY")
    kwargs: Dict[str, Any] = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    return OpenAI(**kwargs)


def call_model(client: OpenAI, *, model: str, prompt: str, row: Dict[str, Any], temperature: float) -> Dict[str, Any]:
    user_payload = {
        "instruction": "Return exactly one JSON object for this single input case. Do not include Markdown.",
        "case": row,
    }
    optional_kwargs: Dict[str, Any] = {}
    thinking_value = os.environ.get("LLM_ENABLE_THINKING")
    if thinking_value is not None:
        optional_kwargs["extra_body"] = {"enable_thinking": thinking_value.lower() == "true"}
    response = client.chat.completions.create(
        model=model,
        temperature=temperature,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ],
        **optional_kwargs,
    )
    content = response.choices[0].message.content or ""
    parsed = parse_json_response(content)
    if parsed.get("id") != row.get("id"):
        parsed["id"] = row.get("id")
    if not isinstance(parsed.get("assistant_message"), str) or not parsed["assistant_message"].strip():
        raise ValueError("model response is missing required canonical assistant_message")
    return parsed


def run_one_scenario(args: argparse.Namespace, scenario: str) -> None:
    config = SCENARIOS[scenario]
    input_path = args.input or config["input"]
    prompt_path = args.prompt or config["prompt"]
    output_path = args.output or config["output"]

    rows = read_jsonl(input_path)
    if args.limit is not None:
        rows = rows[: args.limit]
    prompt = prompt_path.read_text(encoding="utf-8")
    client = make_client()
    model = args.model or os.environ.get("LLM_MODEL_NAME") or "deepseek-chat"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as handle:
        for index, row in enumerate(rows, start=1):
            total_attempts = max(1, args.retries + 1)
            for attempt in range(1, total_attempts + 1):
                try:
                    result = call_model(
                        client,
                        model=model,
                        prompt=prompt,
                        row=row,
                        temperature=args.temperature,
                    )
                    handle.write(json.dumps(result, ensure_ascii=False) + "\n")
                    handle.flush()
                    print(f"[{scenario} {index}/{len(rows)}] {row.get('id')} ok")
                    break
                except Exception as exc:
                    if attempt >= total_attempts:
                        print(f"[{scenario} {index}/{len(rows)}] {row.get('id')} failed: {exc}", file=sys.stderr)
                        raise
                    wait_seconds = min(30, 2 * attempt)
                    print(
                        f"[{scenario} {index}/{len(rows)}] {row.get('id')} retry {attempt}/{args.retries}: {exc}",
                        file=sys.stderr,
                    )
                    time.sleep(wait_seconds)
    print(f"llm baseline output: {output_path} ({len(rows)} rows)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run LLM-only benchmark baseline with an OpenAI-compatible chat API.")
    parser.add_argument("--scenario", choices=["all", *SCENARIOS.keys()], default="all")
    parser.add_argument("--input", type=Path, default=None, help="Override input JSONL; only valid for one scenario")
    parser.add_argument("--prompt", type=Path, default=None, help="Override prompt file; only valid for one scenario")
    parser.add_argument("--output", type=Path, default=None, help="Override output JSONL; only valid for one scenario")
    parser.add_argument("--model", default=None, help="Model name; defaults to LLM_MODEL_NAME or deepseek-chat")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--retries", type=int, default=3)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.scenario == "all" and (args.input or args.prompt or args.output):
        raise SystemExit("--input/--prompt/--output can only be used with one scenario")
    scenarios = list(SCENARIOS) if args.scenario == "all" else [args.scenario]
    for scenario in scenarios:
        run_one_scenario(args, scenario)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
