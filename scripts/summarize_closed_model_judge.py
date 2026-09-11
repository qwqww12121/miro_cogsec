import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_ROOT = ROOT / "benchmark"
DEFAULT_INPUT = BENCHMARK_ROOT / "outputs" / "closed_model_judge" / "judge_results_v0.1.jsonl"
DEFAULT_OUTPUT = BENCHMARK_ROOT / "outputs" / "closed_model_judge" / "judge_summary_v0.1.json"

SYSTEMS = ["miro_cogsec", "llm_only"]
DIMENSIONS = [
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


def score_value(scores: Dict[str, Any], dimension: str) -> Optional[float]:
    value = scores.get(dimension)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def mean(values: Iterable[float]) -> Optional[float]:
    values = list(values)
    if not values:
        return None
    return round(sum(values) / len(values), 3)


def pct(count: int, total: int) -> float:
    return round((count / max(1, total)) * 100, 2)


def system_scores(row: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    scores: Dict[str, Dict[str, Any]] = {}
    a_system = row.get("answer_a_system")
    b_system = row.get("answer_b_system")
    if a_system:
        scores[str(a_system)] = row.get("answer_a_scores", {}) if isinstance(row.get("answer_a_scores"), dict) else {}
    if b_system:
        scores[str(b_system)] = row.get("answer_b_scores", {}) if isinstance(row.get("answer_b_scores"), dict) else {}
    return scores


def summarize_rows(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(rows)
    wins = {system: 0 for system in SYSTEMS}
    ties = 0
    score_bucket: Dict[str, Dict[str, List[float]]] = {
        system: {dimension: [] for dimension in DIMENSIONS}
        for system in SYSTEMS
    }

    for row in rows:
        winner_system = row.get("winner_system")
        if winner_system in wins:
            wins[str(winner_system)] += 1
        else:
            ties += 1
        scores_by_system = system_scores(row)
        for system in SYSTEMS:
            scores = scores_by_system.get(system, {})
            for dimension in DIMENSIONS:
                value = score_value(scores, dimension)
                if value is not None:
                    score_bucket[system][dimension].append(value)

    return {
        "case_count": total,
        "wins": wins,
        "ties": ties,
        "win_rate": {system: pct(count, total) for system, count in wins.items()},
        "tie_rate": pct(ties, total),
        "average_scores": {
            system: {
                dimension: mean(values)
                for dimension, values in dimensions.items()
            }
            for system, dimensions in score_bucket.items()
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Summarize blind closed-model judge results.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--mode",
        choices=["with_gold", "no_gold"],
        default="no_gold",
        help="The request builder excludes gold by default, so summaries default to no_gold too.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    rows = load_jsonl(args.input)
    by_scenario: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_scenario[str(row.get("scenario_type", "unknown"))].append(row)

    summary = {
        "layer": "closed_model_blind_judge",
        "benchmark_version": "v0.1",
        "judge_mode": args.mode,
        "judge_policy": (
            "In with_gold mode, gold is treated as a reference annotation rather than an absolute truth. "
            "In no_gold mode, the judge uses only the original input, blind Answer A/B outputs, runtime summaries, "
            "practical intervention value, evidence support, and overall task quality."
        ),
        "overall": summarize_rows(rows),
        "by_scenario": {
            scenario: summarize_rows(items)
            for scenario, items in sorted(by_scenario.items())
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"closed-model judge summary: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
