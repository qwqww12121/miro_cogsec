"""Run all benchmark scenarios through the CogSecService API path.

This runner is intentionally smoke-oriented for v0.1:
- fraud_im can still be scored later with the existing fraud RES script.
- public_opinion / event_propagation are checked for execution, canonical
  scenario resolution, and propagation-extension presence.
"""

from __future__ import annotations

import argparse
import os
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
BENCHMARK_ROOT = REPO_ROOT / "benchmark"

sys.path.insert(0, str(BACKEND_ROOT))
sys.path.insert(0, str(REPO_ROOT))

from benchmark.cogsec_benchmark import (  # noqa: E402
    ANNOTATED_PATH,
    EVENT_PROPAGATION_PATH,
    PUBLIC_OPINION_PATH,
    load_jsonl,
    runtime_prediction,
    write_json,
    write_jsonl,
)

if False:  # pragma: no cover - typing only without importing backend on --help.
    from app.services.cogsec_service import CogSecService


SCENARIOS: Dict[str, Dict[str, Path]] = {
    "fraud_im": {
        "input": ANNOTATED_PATH,
        "run_output": BENCHMARK_ROOT / "outputs" / "api_fraud_im_run_v0.1.jsonl",
        "metrics_output": BENCHMARK_ROOT / "outputs" / "api_fraud_im_smoke_v0.1.json",
    },
    "public_opinion": {
        "input": PUBLIC_OPINION_PATH,
        "run_output": BENCHMARK_ROOT / "outputs" / "api_public_opinion_run_v0.1.jsonl",
        "metrics_output": BENCHMARK_ROOT / "outputs" / "api_public_opinion_smoke_v0.1.json",
    },
    "event_propagation": {
        "input": EVENT_PROPAGATION_PATH,
        "run_output": BENCHMARK_ROOT / "outputs" / "api_event_propagation_run_v0.1.jsonl",
        "metrics_output": BENCHMARK_ROOT / "outputs" / "api_event_propagation_smoke_v0.1.json",
    },
}

PROPAGATION_SCENARIOS = {"public_opinion", "event_propagation"}


def pct(values: Iterable[float]) -> float:
    values = list(values)
    return round((sum(values) / max(1, len(values))) * 100, 2)


def latency_summary(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    latencies = [float(row["latency_ms"]) for row in rows if row.get("latency_ms") is not None]
    if not latencies:
        return {"p50": None, "p95": None, "max": None}
    return {
        "p50": round(statistics.median(latencies), 3),
        "p95": round(statistics.quantiles(latencies, n=20)[18], 3) if len(latencies) >= 20 else None,
        "max": round(max(latencies), 3),
    }


def summarize_propagation(extension: Dict[str, Any]) -> Dict[str, Any]:
    propagation = extension.get("propagation")
    if not isinstance(propagation, dict):
        return {
            "present": False,
            "error": extension.get("propagation_error"),
        }

    branch_a = propagation.get("branch_a") if isinstance(propagation.get("branch_a"), dict) else {}
    branch_b = propagation.get("branch_b") if isinstance(propagation.get("branch_b"), dict) else {}
    comparison = propagation.get("comparison") if isinstance(propagation.get("comparison"), dict) else {}
    return {
        "present": True,
        "branch_a_final_metrics": branch_a.get("final_metrics", {}),
        "branch_b_final_metrics": branch_b.get("final_metrics", {}),
        "comparison": comparison,
        "fork_point": propagation.get("fork_point", {}),
    }


def compact_result(result_dict: Dict[str, Any], expected_scenario: str) -> Dict[str, Any]:
    scenario_metadata = result_dict.get("scenario_metadata") or {}
    scenario_extension = result_dict.get("scenario_extension") or {}
    resolved = scenario_metadata.get("canonical") or (scenario_extension.get("detection") or {}).get("canonical")
    propagation_summary = summarize_propagation(scenario_extension)

    return {
        "expected_scenario_type": expected_scenario,
        "resolved_scenario_type": resolved,
        "scenario_match": resolved == expected_scenario,
        "scenario_metadata": scenario_metadata,
        "scenario_extension": scenario_extension,
        "scenario_extension_keys": sorted(scenario_extension.keys()),
        "has_propagation": propagation_summary.get("present", False),
        "propagation_summary": propagation_summary,
        "prediction": runtime_prediction(result_dict),
        "metrics": result_dict.get("metrics", {}),
        "anomalies": result_dict.get("anomalies", []),
    }


def smoke_metrics(scenario: str, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    ok_rows = [row for row in rows if row.get("ok")]
    scenario_matches = [1.0 if row.get("scenario_match") else 0.0 for row in ok_rows]
    propagation_values = [
        1.0 if row.get("has_propagation") else 0.0
        for row in ok_rows
    ] if scenario in PROPAGATION_SCENARIOS else []
    errors = [
        {"id": row.get("id"), "error": row.get("error")}
        for row in rows
        if not row.get("ok")
    ]
    return {
        "layer": "api_scenario_smoke",
        "benchmark_version": "v0.1",
        "scenario_type": scenario,
        "case_count": len(rows),
        "runtime_success_rate": pct(1.0 if row.get("ok") else 0.0 for row in rows),
        "scenario_resolution_accuracy": pct(scenario_matches) if ok_rows else 0.0,
        "propagation_presence_rate": pct(propagation_values) if propagation_values else None,
        "latency_ms": latency_summary(rows),
        "error_count": len(errors),
        "errors": errors,
        "per_case": [
            {
                "id": row.get("id"),
                "ok": row.get("ok"),
                "latency_ms": row.get("latency_ms"),
                "scenario_match": row.get("scenario_match"),
                "resolved_scenario_type": row.get("resolved_scenario_type"),
                "has_propagation": row.get("has_propagation"),
                "error": row.get("error"),
            }
            for row in rows
        ],
    }


def run_one_scenario(
    service: "CogSecService",
    scenario: str,
    input_path: Path,
    run_output: Path,
    metrics_output: Path,
    limit: int | None,
) -> int:
    rows = load_jsonl(input_path)
    if limit is not None:
        rows = rows[:limit]

    outputs: List[Dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        started = time.perf_counter()
        row_id = row.get("id", f"{scenario}-{index}")
        try:
            result = service.analyze_text(
                scenario_text=row["input"]["text"],
                scenario_type=scenario,
            )
            latency_ms = (time.perf_counter() - started) * 1000
            compact = compact_result(result.to_dict(), scenario)
            outputs.append(
                {
                    "id": row_id,
                    "ok": True,
                    "latency_ms": round(latency_ms, 3),
                    "error": None,
                    **compact,
                }
            )
            print(
                f"[{scenario} {index}/{len(rows)}] {row_id} ok "
                f"{latency_ms:.1f} ms scenario={compact['resolved_scenario_type']} "
                f"propagation={compact['has_propagation']}",
                flush=True,
            )
        except Exception as exc:
            latency_ms = (time.perf_counter() - started) * 1000
            outputs.append(
                {
                    "id": row_id,
                    "ok": False,
                    "latency_ms": round(latency_ms, 3),
                    "error": f"{exc.__class__.__name__}: {exc}",
                    "expected_scenario_type": scenario,
                    "resolved_scenario_type": None,
                    "scenario_match": False,
                    "has_propagation": False,
                    "propagation_summary": {},
                    "prediction": {},
                    "metrics": {},
                    "anomalies": [],
                }
            )
            print(f"[{scenario} {index}/{len(rows)}] {row_id} failed: {exc.__class__.__name__}: {exc}", flush=True)

    write_jsonl(run_output, outputs)
    metrics = smoke_metrics(scenario, outputs)
    write_json(metrics_output, metrics)
    print(f"api scenario output: {run_output} ({len(outputs)} rows)", flush=True)
    print(f"api scenario smoke metrics: {metrics_output}", flush=True)
    print(
        f"summary {scenario}: success={metrics['runtime_success_rate']} "
        f"scenario_match={metrics['scenario_resolution_accuracy']} "
        f"propagation={metrics['propagation_presence_rate']}",
        flush=True,
    )
    return 0 if not metrics["errors"] else 1


def run_cases(args: argparse.Namespace) -> int:
    if args.no_local_gemma:
        os.environ["COGSEC_USE_LOCAL_GEMMA"] = "false"

    from app.services import cogsec_service as cogsec_service_module

    if args.disable_chroma:
        from app.modules.threat_rag import ThreatKnowledgeRAG

        def build_non_chroma_rag(chroma_path: str) -> ThreatKnowledgeRAG:
            return ThreatKnowledgeRAG(chroma_path, enable_chroma=False)

        cogsec_service_module.ThreatKnowledgeRAG = build_non_chroma_rag

    CogSecService = cogsec_service_module.CogSecService

    selected = list(SCENARIOS) if args.scenario == "all" else [args.scenario]
    service = CogSecService()
    exit_code = 0
    for scenario in selected:
        config = SCENARIOS[scenario]
        code = run_one_scenario(
            service=service,
            scenario=scenario,
            input_path=args.input or config["input"],
            run_output=args.output or config["run_output"],
            metrics_output=args.metrics_output or config["metrics_output"],
            limit=args.limit,
        )
        exit_code = max(exit_code, code)
    return exit_code


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run three-scenario CogSec API benchmark smoke tests.")
    parser.add_argument("--scenario", choices=["all", *SCENARIOS.keys()], default="all")
    parser.add_argument("--input", type=Path, default=None, help="Override input JSONL; only valid for one scenario")
    parser.add_argument("--output", type=Path, default=None, help="Override run output JSONL; only valid for one scenario")
    parser.add_argument("--metrics-output", type=Path, default=None, help="Override smoke metrics JSON; only valid for one scenario")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--disable-chroma",
        action="store_true",
        help="Use lexical fallback RAG without Chroma embeddings; useful for local smoke tests.",
    )
    parser.add_argument(
        "--no-local-gemma",
        action="store_true",
        help="Disable local Gemma loading and use heuristic profile extraction.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.scenario == "all" and (args.input or args.output or args.metrics_output):
        parser.error("--input/--output/--metrics-output overrides can only be used with a single --scenario")
    return run_cases(args)


if __name__ == "__main__":
    raise SystemExit(main())
