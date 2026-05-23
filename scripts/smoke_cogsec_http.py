"""Smoke test one CogSec HTTP API request and save the response."""

from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path
from typing import Any, Dict


DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "benchmark" / "outputs" / "api_one_result.json"
DEFAULT_SCENARIO = "来电者自称公安机关，称账户涉嫌洗钱，要求全程保密并把资金转入安全账户接受核查。"


def first_number(*values: Any) -> Any:
    for value in values:
        if isinstance(value, (int, float)):
            return value
    return ""


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test CogSec HTTP API.")
    parser.add_argument("--url", default="http://127.0.0.1:5001/api/cogsec/analyze")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--scenario", default=DEFAULT_SCENARIO)
    parser.add_argument("--scenario-type", default="authority_impersonation")
    args = parser.parse_args()

    payload = {
        "scenario": args.scenario,
        "scenario_type": args.scenario_type,
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        args.url,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=180) as response:
        raw = response.read().decode("utf-8")
    result: Dict[str, Any] = json.loads(raw)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    data = result.get("data") or {}
    profile = data.get("profile") or data.get("cognitive_profile") or {}
    metrics = data.get("metrics") or data.get("risk_evaluation") or {}
    t0 = data.get("t0_fast_response") or data.get("t0_response") or {}
    report = data.get("counterfactual_report") or {}
    score_comparison = report.get("score_comparison") or {}

    summary = {
        "success": result.get("success"),
        "scenario_type": profile.get("scenario_type", ""),
        "profile_score": first_number(profile.get("overall_vulnerability_score")),
        "risk_level": metrics.get("risk_level", ""),
        "final_risk": first_number(metrics.get("final_risk"), metrics.get("risk_score")),
        "t0_action": t0.get("immediate_action", "") or t0.get("recommended_action", ""),
        "trajectory_gap": first_number(
            score_comparison.get("trajectory_gap"),
            report.get("trajectory_gap"),
        ),
        "output": str(args.output),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
