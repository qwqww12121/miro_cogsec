"""Run all benchmark scenarios through CogSecService with benchmark adapters."""

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
    compute_prediction_scores,
    load_jsonl,
    runtime_prediction,
    write_json,
    write_jsonl,
)

if False:  # pragma: no cover
    from app.services.cogsec_service import CogSecService


SCENARIOS: Dict[str, Dict[str, Path]] = {
    "fraud_im": {
        "input": ANNOTATED_PATH,
        "run_output": BENCHMARK_ROOT / "outputs" / "api_fraud_im_after_adapter_v0.1.jsonl",
        "metrics_output": BENCHMARK_ROOT / "outputs" / "api_fraud_im_answer_scores_after_adapter_v0.1.json",
        "smoke_output": BENCHMARK_ROOT / "outputs" / "api_fraud_im_smoke_after_adapter_v0.1.json",
    },
    "public_opinion": {
        "input": PUBLIC_OPINION_PATH,
        "run_output": BENCHMARK_ROOT / "outputs" / "api_public_opinion_after_adapter_v0.1.jsonl",
        "metrics_output": BENCHMARK_ROOT / "outputs" / "api_public_opinion_answer_scores_after_adapter_v0.1.json",
        "smoke_output": BENCHMARK_ROOT / "outputs" / "api_public_opinion_smoke_after_adapter_v0.1.json",
    },
    "event_propagation": {
        "input": EVENT_PROPAGATION_PATH,
        "run_output": BENCHMARK_ROOT / "outputs" / "api_event_propagation_after_adapter_v0.1.jsonl",
        "metrics_output": BENCHMARK_ROOT / "outputs" / "api_event_propagation_answer_scores_after_adapter_v0.1.json",
        "smoke_output": BENCHMARK_ROOT / "outputs" / "api_event_propagation_smoke_after_adapter_v0.1.json",
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
    search = extension.get("propagation_intervention_search")
    if not isinstance(propagation, dict):
        return {
            "present": False,
            "error": extension.get("propagation_error"),
            "intervention_search_present": isinstance(search, dict),
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
        "intervention_search_present": isinstance(search, dict),
        "counterfactual_branch_count": len(search.get("counterfactual_branches", [])) if isinstance(search, dict) else 0,
        "selected_best_branch": search.get("selected_best_branch", {}) if isinstance(search, dict) else {},
    }


def compact_result(result_dict: Dict[str, Any], expected_scenario: str) -> Dict[str, Any]:
    scenario_metadata = result_dict.get("scenario_metadata") or {}
    scenario_extension = result_dict.get("scenario_extension") or {}
    detection = scenario_extension.get("detection") or {}
    resolved = scenario_metadata.get("canonical") or detection.get("canonical")
    propagation_summary = summarize_propagation(scenario_extension)
    return {
        "expected_scenario_type": expected_scenario,
        "resolved_scenario_type": resolved,
        "scenario_match": resolved == expected_scenario,
        "scenario_metadata": scenario_metadata,
        "scenario_extension": scenario_extension,
        "scenario_extension_keys": sorted(scenario_extension.keys()),
        "has_propagation": propagation_summary.get("present", False),
        "has_intervention_search": propagation_summary.get("intervention_search_present", False),
        "propagation_summary": propagation_summary,
        "prediction": runtime_prediction(result_dict),
        "benchmark_prediction": result_dict.get("benchmark_prediction", {}),
        "cogsec_analysis": result_dict.get("cogsec_analysis", {}),
        "adapter_diagnostics": result_dict.get("adapter_diagnostics", {}),
        "metrics": result_dict.get("metrics", {}),
        "anomalies": result_dict.get("anomalies", []),
    }


def smoke_metrics(scenario: str, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    ok_rows = [row for row in rows if row.get("ok")]
    scenario_matches = [1.0 if row.get("scenario_match") else 0.0 for row in ok_rows]
    propagation_values = [1.0 if row.get("has_propagation") else 0.0 for row in ok_rows] if scenario in PROPAGATION_SCENARIOS else []
    search_values = [1.0 if row.get("has_intervention_search") else 0.0 for row in ok_rows] if scenario in PROPAGATION_SCENARIOS else []
    branch_counts = [
        row.get("propagation_summary", {}).get("counterfactual_branch_count", 0)
        for row in ok_rows
        if scenario in PROPAGATION_SCENARIOS
    ]
    errors = [{"id": row.get("id"), "error": row.get("error")} for row in rows if not row.get("ok")]
    return {
        "layer": "api_scenario_runtime_after_adapter",
        "benchmark_version": "v0.1",
        "scenario_type": scenario,
        "case_count": len(rows),
        "runtime_success_rate": pct(1.0 if row.get("ok") else 0.0 for row in rows),
        "scenario_resolution_accuracy": pct(scenario_matches) if ok_rows else 0.0,
        "propagation_presence_rate": pct(propagation_values) if propagation_values else None,
        "intervention_search_presence_rate": pct(search_values) if search_values else None,
        "mean_counterfactual_branch_count": round(sum(branch_counts) / max(1, len(branch_counts)), 2) if branch_counts else None,
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
                "has_intervention_search": row.get("has_intervention_search"),
                "counterfactual_branch_count": row.get("propagation_summary", {}).get("counterfactual_branch_count"),
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
    smoke_output: Path,
    limit: int | None,
) -> int:
    rows = load_jsonl(input_path)
    if limit is not None:
        rows = rows[:limit]

    outputs: List[Dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        started = time.perf_counter()
        row_id = row.get("id", f"{scenario}-{index}")
        declared_type = row.get("answer", {}).get("fraud_type") if scenario == "fraud_im" else scenario
        try:
            result = service.analyze_text(
                scenario_text=row["input"]["text"],
                scenario_type=declared_type,
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
                f"propagation={compact['has_propagation']} search={compact['has_intervention_search']}",
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
                    "has_intervention_search": False,
                    "propagation_summary": {},
                    "prediction": {},
                    "benchmark_prediction": {},
                    "cogsec_analysis": {},
                    "adapter_diagnostics": {},
                    "metrics": {},
                    "anomalies": [],
                }
            )
            print(f"[{scenario} {index}/{len(rows)}] {row_id} failed: {exc.__class__.__name__}: {exc}", flush=True)

    write_jsonl(run_output, outputs)
    smoke = smoke_metrics(scenario, outputs)
    write_json(smoke_output, smoke)
    scores = compute_prediction_scores(
        truth_rows=rows,
        prediction_rows=outputs,
        scenario_type=scenario,
        layer="api_answer_score_after_adapter",
    )
    write_json(metrics_output, scores)
    summary = {key: value for key, value in scores.items() if key != "per_case"}
    print(f"api scenario output: {run_output} ({len(outputs)} rows)", flush=True)
    print(f"api smoke metrics: {smoke_output}", flush=True)
    print(f"api answer metrics: {metrics_output}", flush=True)
    print(summary, flush=True)
    return 0 if not smoke["errors"] else 1


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
            smoke_output=args.smoke_output or config["smoke_output"],
            limit=args.limit,
        )
        exit_code = max(exit_code, code)
    return exit_code


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run CogSec API benchmark for three scenario types.")
    parser.add_argument("--scenario", choices=["all", *SCENARIOS.keys()], default="all")
    parser.add_argument("--input", type=Path, default=None, help="Override input JSONL; only valid for one scenario")
    parser.add_argument("--output", type=Path, default=None, help="Override run output JSONL; only valid for one scenario")
    parser.add_argument("--metrics-output", type=Path, default=None, help="Override answer score JSON; only valid for one scenario")
    parser.add_argument("--smoke-output", type=Path, default=None, help="Override smoke metric JSON; only valid for one scenario")
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
    if args.scenario == "all" and (args.input or args.output or args.metrics_output or args.smoke_output):
        parser.error("--input/--output/--metrics-output/--smoke-output overrides can only be used with a single --scenario")
    return run_cases(args)


if __name__ == "__main__":
    raise SystemExit(main())
