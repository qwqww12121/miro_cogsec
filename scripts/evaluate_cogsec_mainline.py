"""Validate CogSec-MIROFISH acceptance metrics from a JSON file."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Tuple


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


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate CogSec-MIROFISH acceptance metrics.")
    parser.add_argument("metrics_json", help="Path to a JSON file with benchmark metrics.")
    args = parser.parse_args()

    metrics_path = Path(args.metrics_json)
    payload = json.loads(metrics_path.read_text(encoding="utf-8"))

    failed = False
    for key, (operator, threshold) in THRESHOLDS.items():
        if key not in payload:
            print(f"{key}: PENDING (missing from metrics payload)")
            failed = True
            continue
        value = float(payload[key])
        ok = passes(value, operator, threshold)
        print(f"{key}: {value} {operator} {threshold} -> {'PASS' if ok else 'FAIL'}")
        failed = failed or not ok

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
