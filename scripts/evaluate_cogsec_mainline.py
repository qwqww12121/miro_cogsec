"""Validate CogSec-MIROFISH acceptance metrics from a benchmark JSON file."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


THRESHOLDS: Dict[str, Tuple[str, float]] = {
    "t0_latency_ms": ("<=", 500.0),
    "end_to_end_ms": ("<=", 30000.0),
    "FSA": (">=", 70.0),
    "CPA": (">=", 60.0),
    "EWT": (">=", 2.0),
    "FPR": ("<=", 15.0),
    "CAL": ("<=", 0.2),
    "EAR": (">=", 65.0),
}


def passes(value: float, operator: str, threshold: float) -> bool:
    if operator == "<=":
        return value <= threshold
    return value >= threshold


def as_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_metrics(payload: Dict[str, Any]) -> Dict[str, Optional[float]]:
    """Accept both old scripts output and benchmark/ metrics JSON."""
    normalized: Dict[str, Optional[float]] = {
        "t0_latency_ms": as_float(payload.get("t0_latency_ms") or payload.get("t0_avg_latency_ms")),
        "end_to_end_ms": as_float(payload.get("end_to_end_ms")),
        "FSA": as_float(payload.get("FSA") if payload.get("FSA") is not None else payload.get("FPA")),
        "CPA": as_float(payload.get("CPA")),
        "EWT": as_float(payload.get("EWT")),
        "FPR": as_float(payload.get("FPR")),
        "CAL": as_float(payload.get("CAL")),
        "EAR": as_float(payload.get("EAR")),
    }
    if normalized["end_to_end_ms"] is None and payload.get("end_to_end_seconds") is not None:
        seconds = as_float(payload.get("end_to_end_seconds"))
        normalized["end_to_end_ms"] = None if seconds is None else seconds * 1000
    if normalized["CAL"] is None and payload.get("RCA") is not None:
        rca = as_float(payload.get("RCA"))
        normalized["CAL"] = None if rca is None else max(0.0, 1.0 - rca / 100.0)
    return normalized


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate CogSec-MIROFISH acceptance metrics.")
    parser.add_argument("metrics_json", help="Path to a JSON file with benchmark metrics.")
    parser.add_argument("--allow-pending", action="store_true", help="Do not fail when a metric is absent.")
    args = parser.parse_args()

    metrics_path = Path(args.metrics_json)
    payload = json.loads(metrics_path.read_text(encoding="utf-8"))
    metrics = normalize_metrics(payload)

    failed = False
    for key, (operator, threshold) in THRESHOLDS.items():
        value = metrics.get(key)
        if value is None:
            print(f"{key}: PENDING (missing from metrics payload)")
            failed = failed or not args.allow_pending
            continue
        ok = passes(value, operator, threshold)
        print(f"{key}: {value} {operator} {threshold} -> {'PASS' if ok else 'FAIL'}")
        failed = failed or not ok

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
