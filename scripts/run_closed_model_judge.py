import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List

sys.set_int_max_str_digits(0)  # 解除 Python 3.11+ 大整数字符串限制

from openai import OpenAI
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_ROOT = ROOT / "benchmark"
if os.environ.get("MIRO_DISABLE_DOTENV", "false").lower() != "true":
    load_dotenv(ROOT / ".env", override=False)
DEFAULT_INPUT = BENCHMARK_ROOT / "outputs" / "closed_model_judge" / "judge_requests_v0.1.jsonl"
DEFAULT_OUTPUT = BENCHMARK_ROOT / "outputs" / "closed_model_judge" / "judge_results_v0.1.jsonl"

SYSTEM_PROMPT = """You are an independent closed-model judge for a cognitive-security benchmark.

You will compare Answer A and Answer B for the same original input. The systems are anonymized.

Important evaluation policy:
- If reference_gold is provided, treat it only as a reference annotation, not an absolute truth.
- If reference_gold is null or missing, judge without gold and rely only on the original input, Answer A, Answer B, and any runtime trace summary shown.
- Do not reward an answer merely for matching field names, being longer, or looking more like a template.
- Prefer the answer that solves the safety task: it locates the real problem, recommends concrete action, grounds claims in evidence, explains the mechanism, and avoids unsupported details.
- Judge only the content shown to you. Do not assume hidden capabilities.

Score both answers from 0 to 10 on:
- problem_localization: locates the real risk/problem in the original input.
- actionability: gives specific, early, practical actions that could reduce harm.
- evidence_grounding: grounds claims in the original input or shown runtime trace.
- mechanism_insight: explains the risk, fork, narrative, propagation, or containment mechanism.
- output_reliability: is internally consistent, avoids unsupported details, and follows the requested structure.

Return exactly one JSON object:
{
  "winner": "A|B|tie",
  "answer_a_scores": {
    "problem_localization": 0,
    "actionability": 0,
    "evidence_grounding": 0,
    "mechanism_insight": 0,
    "output_reliability": 0
  },
  "answer_b_scores": {
    "problem_localization": 0,
    "actionability": 0,
    "evidence_grounding": 0,
    "mechanism_insight": 0,
    "output_reliability": 0
  },
  "rationale": "brief reason in Chinese"
}
"""

JUDGE_DIMENSIONS = [
    "problem_localization",
    "actionability",
    "evidence_grounding",
    "mechanism_insight",
    "output_reliability",
]


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
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


def append_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            handle.flush()


def number_from_text(text: str, field: str) -> float:
    pattern = rf'"?{re.escape(field)}"?\s*[:：]\s*([0-9]+(?:\.[0-9]+)?)'
    match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return 0.0
    try:
        return float(match.group(1))
    except (TypeError, ValueError):
        return 0.0


def fallback_parse_judgement(text: str) -> Dict[str, Any]:
    winner_match = re.search(r'"?winner"?\s*[:：]\s*"?\b(A|B|tie)\b"?', text, flags=re.IGNORECASE)
    winner = winner_match.group(1).upper() if winner_match else "tie"
    if winner.upper() == "TIE":
        winner = "tie"

    def scores_for(label: str) -> Dict[str, float]:
        block_match = re.search(
            rf'"?answer_{label.lower()}_scores"?\s*[:：]\s*\{{(?P<body>.*?)\}}',
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        block = block_match.group("body") if block_match else text
        return {dimension: number_from_text(block, dimension) for dimension in JUDGE_DIMENSIONS}

    rationale_match = re.search(r'"?rationale"?\s*[:：]\s*"?(?P<rationale>.*)', text, flags=re.IGNORECASE | re.DOTALL)
    rationale = rationale_match.group("rationale").strip().strip('",} ') if rationale_match else "Parsed from non-strict JSON response."
    return {
        "winner": winner,
        "answer_a_scores": scores_for("a"),
        "answer_b_scores": scores_for("b"),
        "rationale": rationale,
        "parse_warning": "fallback_non_strict_json",
    }


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
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                return fallback_parse_judgement(text[start : end + 1])
        return fallback_parse_judgement(text)


def make_client() -> OpenAI:
    api_key = os.environ.get("JUDGE_API_KEY") or os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("JUDGE_BASE_URL") or os.environ.get("LLM_BASE_URL")
    if not api_key:
        raise RuntimeError("Missing JUDGE_API_KEY / LLM_API_KEY / OPENAI_API_KEY")
    kwargs: Dict[str, Any] = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    return OpenAI(**kwargs)


def public_request(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": row.get("id"),
        "scenario_type": row.get("scenario_type"),
        "input": row.get("input"),
        "reference_gold": row.get("reference_gold"),
        "judge_instruction": row.get("judge_instruction"),
        "answer_a": row.get("answer_a"),
        "answer_b": row.get("answer_b"),
    }


def call_judge(client: OpenAI, *, model: str, request: Dict[str, Any], temperature: float) -> Dict[str, Any]:
    kwargs: Dict[str, Any] = {
        "model": model,
        "temperature": temperature,
        "max_tokens": 900,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(public_request(request), ensure_ascii=False)},
        ],
    }
    thinking_value = os.environ.get("JUDGE_ENABLE_THINKING")
    if thinking_value is not None:
        kwargs["extra_body"] = {"enable_thinking": thinking_value.lower() == "true"}
    try:
        response = client.chat.completions.create(
            **kwargs,
            response_format={"type": "json_object"},
        )
    except Exception:
        response = client.chat.completions.create(**kwargs)
    content = response.choices[0].message.content or ""
    judgement = parse_json_response(content)
    validate_judgement(judgement)
    return judgement


def validate_judgement(value: Dict[str, Any]) -> None:
    """Reject partial/invalid judge payloads instead of silently scoring zero."""
    if not isinstance(value, dict):
        raise ValueError("judge response must be an object")
    raw_winner = str(value.get("winner") or "").strip().upper()
    if raw_winner not in {"A", "B", "TIE", "ANSWER A", "ANSWER B"}:
        raise ValueError("judge winner is invalid")
    for block_name in ("answer_a_scores", "answer_b_scores"):
        block = value.get(block_name)
        if not isinstance(block, dict):
            raise ValueError(f"judge response missing {block_name}")
        for dimension in JUDGE_DIMENSIONS:
            try:
                score = float(block[dimension])
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"judge response missing numeric {block_name}.{dimension}") from exc
            if not 0.0 <= score <= 10.0:
                raise ValueError(f"judge score out of range: {block_name}.{dimension}={score}")
    if len(str(value.get("rationale") or "").strip()) < 6:
        raise ValueError("judge rationale is missing or too short")


def normalize_winner(value: Any) -> str:
    winner = str(value or "").strip().upper()
    if winner in {"A", "ANSWER A"}:
        return "A"
    if winner in {"B", "ANSWER B"}:
        return "B"
    return "tie"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run blind closed-model judging with an OpenAI-compatible chat API.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--model", default=None, help="Defaults to JUDGE_MODEL_NAME, LLM_MODEL_NAME, or gpt-4o")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--resume", action="store_true", help="Skip ids already present in output")
    parser.add_argument("--retries", type=int, default=3)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    requests = load_jsonl(args.input)
    if args.limit is not None:
        requests = requests[: args.limit]
    completed = set()
    if args.resume and args.output.exists():
        completed = {str(row.get("id")) for row in load_jsonl(args.output) if row.get("id")}

    client = make_client()
    model = args.model or os.environ.get("JUDGE_MODEL_NAME") or os.environ.get("LLM_MODEL_NAME") or "gpt-4o"

    for index, request in enumerate(requests, start=1):
        row_id = str(request.get("id"))
        if row_id in completed:
            print(f"[judge {index}/{len(requests)}] {row_id} skip")
            continue
        total_attempts = max(1, args.retries + 1)
        for attempt in range(1, total_attempts + 1):
            try:
                judgement = call_judge(
                    client,
                    model=model,
                    request=request,
                    temperature=args.temperature,
                )
                winner_slot = normalize_winner(judgement.get("winner"))
                key = request.get("private_answer_key", {})
                result = {
                    "id": row_id,
                    "scenario_type": request.get("scenario_type"),
                    "judge_mode": request.get("judge_mode") or (
                        "with_gold" if request.get("reference_gold") is not None else "no_gold"
                    ),
                    "winner": winner_slot,
                    "winner_system": key.get(winner_slot) if winner_slot in {"A", "B"} else "tie",
                    "answer_a_system": key.get("A"),
                    "answer_b_system": key.get("B"),
                    "answer_a_scores": judgement.get("answer_a_scores", {}),
                    "answer_b_scores": judgement.get("answer_b_scores", {}),
                    "rationale": judgement.get("rationale", ""),
                    "judge_model": model,
                }
                if judgement.get("parse_warning"):
                    result["parse_warning"] = judgement["parse_warning"]
                append_jsonl(args.output, [result])
                print(f"[judge {index}/{len(requests)}] {row_id} winner={result['winner_system']}")
                break
            except Exception as exc:
                if attempt >= total_attempts:
                    print(f"[judge {index}/{len(requests)}] {row_id} failed: {exc}", file=sys.stderr)
                    raise
                print(f"[judge {index}/{len(requests)}] {row_id} retry {attempt}/{args.retries}: {exc}", file=sys.stderr)
                time.sleep(min(30, 2 * attempt))
    print(f"closed-model judge results: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
