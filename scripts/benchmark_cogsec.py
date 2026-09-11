"""Run a legacy-compatible CogSec benchmark over a JSONL dataset."""

from __future__ import annotations

import argparse
import importlib.util
import json
import statistics
import sys
import time
import tracemalloc
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = PROJECT_ROOT / "data" / "benchmark" / "cogsec_eval_sample.jsonl"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "benchmark" / "metrics.json"
DEFAULT_PREDICTIONS = PROJECT_ROOT / "data" / "benchmark" / "predictions.jsonl"
NEW_BENCHMARK_SCRIPT = PROJECT_ROOT / "benchmark" / "cogsec_benchmark.py"

RISK_VALUE = {"low": 0.0, "medium": 0.5, "high": 1.0, "critical": 1.0}


def load_benchmark_helpers():
    spec = importlib.util.spec_from_file_location("cogsec_benchmark_v01", NEW_BENCHMARK_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load benchmark helpers from {NEW_BENCHMARK_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                rows.append(json.loads(stripped))
    return rows


def write_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def risk_bin(value: str) -> str:
    value = str(value or "").lower()
    if value in {"critical", "high"}:
        return "high"
    if value == "medium":
        return "medium"
    return "low"


def contains_any(text: str, keywords: Iterable[str]) -> int:
    lowered = text.lower()
    return sum(1 for keyword in keywords if str(keyword).lower() in lowered)


def pct(values: Iterable[float]) -> float:
    values = list(values)
    return round((sum(values) / max(1, len(values))) * 100, 2)


def mean(values: Iterable[float], default: Optional[float] = 0.0) -> Optional[float]:
    values = list(values)
    if not values:
        return default
    return round(statistics.mean(values), 3)


def import_runtime():
    sys.path.insert(0, str(PROJECT_ROOT))
    try:
        from backend.app.cogsec_minimal_runtime import run_minimal_cogsec_analysis
    except Exception as exc:  # pragma: no cover - environment dependency guard
        return None, f"{exc.__class__.__name__}: {exc}"
    return run_minimal_cogsec_analysis, None


def score_case(row: Dict[str, Any], run_row: Dict[str, Any]) -> Dict[str, Any]:
    prediction = run_row.get("prediction", {})
    runtime_ok = bool(run_row.get("ok"))
    expected_alert = bool(row.get("expected_alert"))
    expected_risk = risk_bin(row.get("expected_risk_level", "low"))
    expected_fork = row.get("expected_runtime_fork_type") or row.get("expected_fork_type", "no_fork_needed")
    expected_no_fork = expected_fork == "no_fork_needed"

    if not runtime_ok:
        return {
            "id": row.get("id"),
            "runtime_ok": False,
            "latency_ms": run_row.get("latency_ms"),
            "alert_correct": False,
            "risk_correct": False,
            "fork_correct": False,
            "false_positive": False,
            "early_warning_steps": 0,
            "calibration_abs_error": 1.0,
            "evidence_alignment": 0.0,
            "error": run_row.get("error"),
        }

    predicted_risk = prediction.get("risk_bin", "low")
    predicted_alert = predicted_risk in {"medium", "high"} or bool(prediction.get("t0_alert"))
    predicted_no_fork = prediction.get("predicted_fork_family") == "no_fork_needed"
    predicted_step = int(prediction.get("critical_bifurcation_step") or 0)
    expected_window_end = int(row.get("expected_window_end", row.get("expected_min_warning_step", 0)) or 0)
    evidence_keywords = row.get("expected_evidence_keywords", [])
    evidence_hits = contains_any(prediction.get("evidence_text", ""), evidence_keywords)
    evidence_alignment = evidence_hits / max(1, len(evidence_keywords))
    expected_value = RISK_VALUE.get(str(row.get("expected_risk_level", "low")).lower(), 0.0)
    predicted_value = RISK_VALUE.get(str(prediction.get("risk_level", "low")).lower(), 0.0)

    return {
        "id": row.get("id"),
        "runtime_ok": True,
        "latency_ms": run_row.get("latency_ms"),
        "alert_correct": predicted_alert == expected_alert,
        "risk_correct": predicted_risk == expected_risk,
        "fork_correct": predicted_no_fork == expected_no_fork,
        "false_positive": (not expected_alert) and predicted_alert,
        "early_warning_steps": max(0, expected_window_end - predicted_step + 1) if expected_alert else 0,
        "calibration_abs_error": abs(expected_value - predicted_value),
        "evidence_alignment": evidence_alignment,
        "expected_risk": expected_risk,
        "predicted_risk": predicted_risk,
        "expected_fork": expected_fork,
        "predicted_fork_family": prediction.get("predicted_fork_family"),
        "error": None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark CogSec runtime against a JSONL evaluation dataset")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--predictions-output", type=Path, default=DEFAULT_PREDICTIONS)
    args = parser.parse_args()

    rows = load_jsonl(args.dataset)
    helpers = load_benchmark_helpers()
    run_minimal_cogsec_analysis, import_error = import_runtime()
    tracemalloc.start()

    outputs: List[Dict[str, Any]] = []
    for row in rows:
        if run_minimal_cogsec_analysis is None:
            outputs.append({
                "id": row.get("id"),
                "ok": False,
                "latency_ms": None,
                "prediction": {},
                "error": f"runtime_import_failed: {import_error}",
            })
            continue

        started = time.perf_counter()
        try:
            result = run_minimal_cogsec_analysis(
                scenario_text=row.get("scenario", ""),
                scenario_type=row.get("label"),
            )
            latency_ms = (time.perf_counter() - started) * 1000
            outputs.append({
                "id": row.get("id"),
                "ok": True,
                "latency_ms": round(latency_ms, 3),
                "prediction": helpers.runtime_prediction(result),
                "error": None,
            })
        except Exception as exc:  # pragma: no cover - runtime dependency guard
            latency_ms = (time.perf_counter() - started) * 1000
            outputs.append({
                "id": row.get("id"),
                "ok": False,
                "latency_ms": round(latency_ms, 3),
                "prediction": {},
                "error": f"{exc.__class__.__name__}: {exc}",
            })

    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    per_case = [score_case(row, output) for row, output in zip(rows, outputs)]
    latencies = [float(item["latency_ms"]) for item in per_case if item.get("latency_ms") is not None]
    fraud_cases = [item for row, item in zip(rows, per_case) if bool(row.get("expected_alert"))]
    benign_cases = [item for row, item in zip(rows, per_case) if not bool(row.get("expected_alert"))]

    result = {
        "benchmark_version": "legacy-compatible-v0.1",
        "case_count": len(per_case),
        "runtime_success_rate": pct(1.0 if item["runtime_ok"] else 0.0 for item in per_case),
        "t0_latency_ms": None,
        "end_to_end_ms": mean(latencies, default=None),
        "end_to_end_ms_p95": round(statistics.quantiles(latencies, n=20)[18], 3) if len(latencies) >= 20 else None,
        "FSA": pct(1.0 if item["fork_correct"] else 0.0 for item in per_case),
        "CPA": pct(1.0 if item["alert_correct"] and item["risk_correct"] else 0.0 for item in per_case),
        "EWT": mean((item["early_warning_steps"] for item in fraud_cases), default=0.0),
        "FPR": pct(1.0 if item["false_positive"] else 0.0 for item in benign_cases),
        "CAL": mean((item["calibration_abs_error"] for item in per_case), default=0.0),
        "EAR": pct(item["evidence_alignment"] for item in per_case),
        "peak_memory_mb": round(peak / (1024 * 1024), 3),
        "per_case": per_case,
    }

    write_jsonl(args.predictions_output, outputs)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "per_case"}, ensure_ascii=False, indent=2))
    print(f"predictions saved: {args.predictions_output}")
    print(f"benchmark result saved: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
