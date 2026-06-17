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

DEFAULT_OUTPUT = BENCHMARK_ROOT / "outputs" / "closed_model_judge" / "judge_requests_v0.1.jsonl"


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


def by_id(rows: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {str(row.get("id")): row for row in rows if row.get("id")}


def prediction_from(row: Dict[str, Any]) -> Dict[str, Any]:
    prediction = row.get("benchmark_prediction")
    if isinstance(prediction, dict) and prediction:
        return prediction
    prediction = row.get("prediction")
    if isinstance(prediction, dict):
        return prediction
    return {}


def runtime_summary_from(row: Dict[str, Any]) -> Dict[str, Any]:
    propagation_summary = row.get("propagation_summary") if isinstance(row.get("propagation_summary"), dict) else {}
    metrics = row.get("metrics") if isinstance(row.get("metrics"), dict) else {}
    return {
        "ok": row.get("ok"),
        "latency_ms": row.get("latency_ms"),
        "scenario_match": row.get("scenario_match"),
        "has_propagation": row.get("has_propagation"),
        "has_intervention_search": row.get("has_intervention_search"),
        "propagation_summary": {
            "present": propagation_summary.get("present"),
            "branch_a_final_metrics": propagation_summary.get("branch_a_final_metrics"),
            "branch_b_final_metrics": propagation_summary.get("branch_b_final_metrics"),
            "comparison": propagation_summary.get("comparison"),
            "counterfactual_branch_count": propagation_summary.get("counterfactual_branch_count"),
            "selected_best_branch": propagation_summary.get("selected_best_branch"),
        },
        "runtime_metrics": {
            "t0_latency_ms": metrics.get("t0_latency_ms"),
            "end_to_end_ms": metrics.get("end_to_end_ms"),
            "benchmarks": metrics.get("benchmarks"),
        },
    }


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
) -> Dict[str, Any]:
    row_id = str(truth.get("id"))
    answers = [
        {
            "slot": "A",
            "system": "llm_only",
            "prediction": prediction_from(llm_row),
            "runtime_summary": None,
        },
        {
            "slot": "B",
            "system": "miro_cogsec",
            "prediction": prediction_from(miro_row),
            "runtime_summary": runtime_summary_from(miro_row),
        },
    ]
    rng = random.Random(stable_shuffle_seed(row_id, seed))
    rng.shuffle(answers)
    for index, item in enumerate(answers):
        item["slot"] = "A" if index == 0 else "B"

    if include_gold:
        reference_gold = truth.get("answer", {})
        judge_instruction = (
            "Gold is a reference annotation, not an absolute truth. Prefer the answer that is better grounded in "
            "the original input, offers more useful safety intervention, and gives stronger evidence. Do not "
            "penalize reasonable alternative interpretations merely because they differ from gold wording."
        )
    else:
        reference_gold = None
        judge_instruction = (
            "No gold/reference answer is provided. Judge only from the original input, the two candidate answers, "
            "their evidence grounding, and any runtime trace summary shown. Prefer the answer that is more useful "
            "for real safety work, even if it uses a different structure or terminology."
        )

    return {
        "id": row_id,
        "scenario_type": scenario,
        "input": truth.get("input", {}),
        "reference_gold": reference_gold,
        "judge_instruction": judge_instruction,
        "answer_a": {
            "prediction": answers[0]["prediction"],
            "runtime_summary": answers[0]["runtime_summary"],
        },
        "answer_b": {
            "prediction": answers[1]["prediction"],
            "runtime_summary": answers[1]["runtime_summary"],
        },
        "private_answer_key": {
            "A": answers[0]["system"],
            "B": answers[1]["system"],
        },
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
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--no-gold", action="store_true", help="Do not include reference_gold in judge requests")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    scenarios = list(SCENARIOS) if args.scenario == "all" else [args.scenario]
    requests: List[Dict[str, Any]] = []
    for scenario in scenarios:
        config = SCENARIOS[scenario]
        truth_rows = load_jsonl(config["gold"])
        llm_rows = by_id(load_jsonl(config["llm"]))
        miro_rows = by_id(load_jsonl(config["miro"]))
        if args.limit is not None:
            truth_rows = truth_rows[: args.limit]
        for truth in truth_rows:
            row_id = str(truth.get("id"))
            if row_id not in llm_rows:
                raise ValueError(f"missing LLM-only prediction for {row_id}")
            if row_id not in miro_rows:
                raise ValueError(f"missing Miro-CogSec prediction for {row_id}")
            requests.append(
                build_request(
                    scenario=scenario,
                    truth=truth,
                    llm_row=llm_rows[row_id],
                    miro_row=miro_rows[row_id],
                    seed=args.seed,
                    include_gold=not args.no_gold,
                )
            )
    write_jsonl(args.output, requests)
    print(f"closed-model judge requests: {args.output} ({len(requests)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
