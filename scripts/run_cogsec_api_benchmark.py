"""Run benchmark cases through the full CogSecService API path."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any, Dict, List


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
BENCHMARK_ROOT = REPO_ROOT / "benchmark"

sys.path.insert(0, str(BACKEND_ROOT))
sys.path.insert(0, str(REPO_ROOT))

from app.services.cogsec_service import CogSecService  # noqa: E402
from benchmark.cogsec_benchmark import (  # noqa: E402
    ANNOTATED_PATH,
    evaluate_runtime,
    load_jsonl,
    runtime_prediction,
    write_jsonl,
)


DEFAULT_RUN_OUTPUT = BENCHMARK_ROOT / "outputs" / "api_run_v0.1.jsonl"
DEFAULT_METRICS_OUTPUT = BENCHMARK_ROOT / "outputs" / "api_metrics_v0.1.json"


def run_cases(args: argparse.Namespace) -> int:
    rows = load_jsonl(args.annotated)
    if args.limit is not None:
        rows = rows[: args.limit]

    service = CogSecService()
    outputs: List[Dict[str, Any]] = []

    for index, row in enumerate(rows, start=1):
        started = time.perf_counter()
        row_id = row.get("id", f"row-{index}")
        try:
            result = service.analyze_text(
                scenario_text=row["input"]["text"],
                scenario_type=row.get("answer", {}).get("fraud_type"),
            )
            latency_ms = (time.perf_counter() - started) * 1000
            result_dict = result.to_dict()
            outputs.append(
                {
                    "id": row_id,
                    "ok": True,
                    "latency_ms": round(latency_ms, 3),
                    "prediction": runtime_prediction(result_dict),
                    "benchmark_prediction": result_dict.get("benchmark_prediction", {}),
                    "cogsec_analysis": result_dict.get("cogsec_analysis", {}),
                    "adapter_diagnostics": result_dict.get("adapter_diagnostics", {}),
                    "error": None,
                }
            )
            print(f"[{index}/{len(rows)}] {row_id} ok {latency_ms:.1f} ms", flush=True)
        except Exception as exc:
            latency_ms = (time.perf_counter() - started) * 1000
            outputs.append(
                {
                    "id": row_id,
                    "ok": False,
                    "latency_ms": round(latency_ms, 3),
                    "prediction": {},
                    "error": f"{exc.__class__.__name__}: {exc}",
                }
            )
            print(f"[{index}/{len(rows)}] {row_id} failed: {exc.__class__.__name__}: {exc}", flush=True)

    write_jsonl(args.output, outputs)
    print(f"api runtime output: {args.output} ({len(outputs)} rows)", flush=True)

    if args.evaluate:
        return evaluate_runtime(
            argparse.Namespace(
                annotated=args.annotated,
                run_output=args.output,
                output=args.metrics_output,
            )
        )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run CogSec benchmark through CogSecService.")
    parser.add_argument("--annotated", type=Path, default=ANNOTATED_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_RUN_OUTPUT)
    parser.add_argument("--metrics-output", type=Path, default=DEFAULT_METRICS_OUTPUT)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--no-evaluate", action="store_true")
    parser.set_defaults(func=run_cases)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    args.evaluate = not args.no_evaluate
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
