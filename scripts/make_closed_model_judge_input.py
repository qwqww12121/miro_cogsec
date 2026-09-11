"""Build randomized blind-judge requests from actual model answers.

Natural-language judging never reconstructs prose from benchmark fields.  Both
systems must provide the exact ``assistant_message`` (or ``canonical_answer``)
that a user would have seen.  Structured judging remains available as a
separate, explicit mode.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path
from typing import Any, Dict, Iterable, List


ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_ROOT = ROOT / "benchmark"

SCENARIOS = {
    "fraud_im": {
        "gold": BENCHMARK_ROOT / "data" / "cogsec_v0.1.jsonl",
        "llm": BENCHMARK_ROOT / "outputs" / "llm_baseline" / "fraud_im_llm_baseline_v0.1.jsonl",
        "miro": BENCHMARK_ROOT / "outputs" / "api_fraud_im_after_adapter_v0.1.jsonl",
    },
    "public_opinion": {
        "gold": BENCHMARK_ROOT / "data" / "public_opinion_v0.1.jsonl",
        "llm": BENCHMARK_ROOT / "outputs" / "llm_baseline" / "public_opinion_llm_baseline_v0.1.jsonl",
        "miro": BENCHMARK_ROOT / "outputs" / "api_public_opinion_after_adapter_v0.1.jsonl",
    },
    "event_propagation": {
        "gold": BENCHMARK_ROOT / "data" / "event_propagation_v0.1.jsonl",
        "llm": BENCHMARK_ROOT / "outputs" / "llm_baseline" / "event_propagation_llm_baseline_v0.1.jsonl",
        "miro": BENCHMARK_ROOT / "outputs" / "api_event_propagation_after_adapter_v0.1.jsonl",
    },
}

DEFAULT_OUTPUT = BENCHMARK_ROOT / "outputs" / "closed_model_judge" / "judge_requests_v0.2.jsonl"


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no} invalid JSON: {exc}") from exc
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_no} must contain a JSON object")
            rows.append(value)
    return rows


def by_id(rows: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {str(row["id"]): row for row in rows if row.get("id")}


def prediction_from(row: Dict[str, Any]) -> Dict[str, Any]:
    for key in ("benchmark_prediction", "prediction"):
        value = row.get(key)
        if isinstance(value, dict):
            return value
    return {}


def canonical_text_from(row: Dict[str, Any], *, system_label: str) -> str:
    for key in ("assistant_message", "canonical_answer"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    raise ValueError(
        f"{system_label} row has no canonical assistant_message; "
        "regenerate the model output or use --structured"
    )


def llm_text_from(row: Dict[str, Any], scenario: str = "fraud_im") -> str:
    del scenario
    return canonical_text_from(row, system_label="LLM-only")


def miro_text_from(row: Dict[str, Any], scenario: str = "fraud_im") -> str:
    del scenario
    return canonical_text_from(row, system_label="Miro-CogSec")


def stable_shuffle_seed(row_id: str, seed: int) -> int:
    digest = hashlib.sha256(f"{seed}:{row_id}".encode("utf-8")).hexdigest()
    return int(digest[:12], 16)


def build_request(
    *,
    scenario: str,
    truth: Dict[str, Any],
    llm_row: Dict[str, Any],
    miro_row: Dict[str, Any],
    seed: int,
    include_gold: bool,
    structured: bool = False,
) -> Dict[str, Any]:
    row_id = str(truth.get("id"))
    answer_key = "prediction" if structured else "text"
    answers = [
        {
            "system": "llm_only",
            answer_key: prediction_from(llm_row) if structured else llm_text_from(llm_row, scenario),
        },
        {
            "system": "miro_cogsec",
            answer_key: prediction_from(miro_row) if structured else miro_text_from(miro_row, scenario),
        },
    ]
    random.Random(stable_shuffle_seed(row_id, seed)).shuffle(answers)

    if include_gold:
        reference_gold = truth.get("answer", {})
        instruction = (
            "Gold is a reference annotation, not absolute truth. Prefer the answer that is better grounded in "
            "the original input, explains the mechanism, and gives proportional actionable intervention."
        )
    else:
        reference_gold = None
        instruction = (
            "No gold/reference answer is provided. Judge only from the original input and the two candidate "
            "answers. Prefer the answer that is grounded, mechanism-aware, natural, and actionable."
        )

    return {
        "id": row_id,
        "scenario_type": scenario,
        "judge_mode": "with_gold" if include_gold else "no_gold",
        "input": truth.get("input", {}),
        "reference_gold": reference_gold,
        "judge_instruction": instruction,
        "rendering_provenance": {
            "mode": "structured_prediction" if structured else "canonical_assistant_message",
            "reconstructed_text": False,
            "gold_included": include_gold,
        },
        "answer_a": {answer_key: answers[0][answer_key]},
        "answer_b": {answer_key: answers[1][answer_key]},
        "private_answer_key": {"A": answers[0]["system"], "B": answers[1]["system"]},
    }


def write_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create blind closed-model judge requests.")
    parser.add_argument("--scenario", choices=["all", *SCENARIOS.keys()], default="all")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--miro-fraud", type=Path, default=None)
    parser.add_argument("--miro-public", type=Path, default=None)
    parser.add_argument("--miro-event", type=Path, default=None)
    parser.add_argument("--llm-fraud", type=Path, default=None)
    parser.add_argument("--llm-public", type=Path, default=None)
    parser.add_argument("--llm-event", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--include-gold", action="store_true", help="Explicitly include reference Gold")
    parser.add_argument("--structured", action="store_true", help="Judge machine fields instead of actual answers")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    configs = {name: dict(config) for name, config in SCENARIOS.items()}
    overrides = {
        "fraud_im": args.miro_fraud,
        "public_opinion": args.miro_public,
        "event_propagation": args.miro_event,
    }
    for scenario, path in overrides.items():
        if path:
            configs[scenario]["miro"] = path
    llm_overrides = {
        "fraud_im": args.llm_fraud,
        "public_opinion": args.llm_public,
        "event_propagation": args.llm_event,
    }
    for scenario, path in llm_overrides.items():
        if path:
            configs[scenario]["llm"] = path

    scenarios = list(SCENARIOS) if args.scenario == "all" else [args.scenario]
    requests: List[Dict[str, Any]] = []
    for scenario in scenarios:
        config = configs[scenario]
        truth_rows = load_jsonl(config["gold"])
        llm_rows = by_id(load_jsonl(config["llm"]))
        miro_rows = by_id(load_jsonl(config["miro"]))
        if args.limit is not None:
            truth_rows = truth_rows[: args.limit]
        for truth in truth_rows:
            row_id = str(truth.get("id"))
            if row_id not in llm_rows or row_id not in miro_rows:
                raise ValueError(f"missing candidate output for {row_id}")
            requests.append(build_request(
                scenario=scenario,
                truth=truth,
                llm_row=llm_rows[row_id],
                miro_row=miro_rows[row_id],
                seed=args.seed,
                include_gold=args.include_gold,
                structured=args.structured,
            ))

    write_jsonl(args.output, requests)
    print(f"closed-model judge requests: {args.output} ({len(requests)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
