"""Orchestrator — build RoleReportPayload from result_dict and invoke the right renderer."""

from __future__ import annotations

from typing import Any, Dict, List

from .registry import get_renderer
from .schema import RoleReportPayload


def build_role_payload(
    result_dict: dict,
    user_role: str = "individual",
    scenario_type: str | None = None,
) -> RoleReportPayload:
    """Extract a RoleReportPayload from the CogSecAnalysisResult dict."""

    # scenario_type
    resolved_scenario = _resolve_scenario(result_dict, scenario_type)

    # risk_scores
    risk = _extract_risk_scores(result_dict)

    # key_findings
    findings = _extract_key_findings(result_dict, resolved_scenario)

    # fork_comparison
    fork_comp = result_dict.get("fork_comparison", {})

    # propagation (safe against scenario_extension=None from fraud_im)
    scenario_extension = result_dict.get("scenario_extension") or {}
    propagation = scenario_extension.get("propagation") if isinstance(scenario_extension, dict) else None

    # timeline
    timeline = _extract_timeline(result_dict, propagation)

    return RoleReportPayload(
        scenario_type=resolved_scenario,
        user_role=user_role,
        source_result=result_dict,
        risk_scores=risk,
        key_findings=findings,
        fork_comparison=fork_comp,
        propagation=propagation,
        timeline=timeline,
        metadata={},
    )


def render_role_report(
    result_dict: dict,
    user_role: str = "individual",
    scenario_type: str | None = None,
) -> dict:
    payload = build_role_payload(result_dict, user_role, scenario_type)
    renderer = get_renderer(user_role)
    return renderer.render(payload).to_dict()


# ---------------------------------------------------------------------------
# internal extractors
# ---------------------------------------------------------------------------


def _resolve_scenario(result_dict: dict, scenario_type: str | None) -> str:
    if scenario_type:
        return scenario_type
    sc_meta = result_dict.get("scenario_metadata", {})
    if isinstance(sc_meta, dict):
        for key in ("canonical", "canonical_scenario_type"):
            if sc_meta.get(key):
                return str(sc_meta[key])
    profile = result_dict.get("profile", {})
    if isinstance(profile, dict) and profile.get("scenario_type"):
        return str(profile["scenario_type"])
    return "fraud_im"


def _extract_risk_scores(result_dict: dict) -> Dict[str, float]:
    scores: dict[str, float] = {
        "final_risk": 0.0,
        "trajectory_gap": 0.0,
        "irreversibility_loss": 0.0,
        "evidence_consistency": 0.0,
    }

    metrics = result_dict.get("metrics", {})
    if isinstance(metrics, dict):
        rb = metrics.get("risk_breakdown", {})
        if isinstance(rb, dict):
            scores["final_risk"] = float(rb.get("final_risk", 0.0))
            scores["trajectory_gap"] = float(rb.get("trajectory_gap", 0.0))
            scores["irreversibility_loss"] = float(rb.get("irreversibility_loss", 0.0))
            scores["evidence_consistency"] = float(rb.get("evidence_consistency", 0.0))

    cf_report = result_dict.get("counterfactual_report", {})
    if isinstance(cf_report, dict):
        sc = cf_report.get("score_comparison", {})
        if isinstance(sc, dict) and scores["final_risk"] == 0.0:
            scores["final_risk"] = float(sc.get("final_risk", 0.0))

    return scores


def _extract_key_findings(result_dict: dict, scenario: str) -> list[dict]:
    findings: list[dict] = []

    # from recommendations
    cf_report = result_dict.get("counterfactual_report", {})
    recs = cf_report.get("recommendations", [])
    for rec in (recs or [])[:3]:
        if isinstance(rec, dict):
            findings.append({
                "title": rec.get("action", rec.get("title", "")),
                "evidence": [rec.get("reason", "")],
                "severity": "medium",
            })

    # from bifurcation step
    if cf_report.get("critical_bifurcation_reason"):
        findings.append({
            "title": f"关键分叉: step {cf_report.get('critical_bifurcation_step', '?')}",
            "evidence": [cf_report["critical_bifurcation_reason"]],
            "severity": "high",
        })

    # from anomalies
    anomalies = result_dict.get("anomalies", [])
    for a in (anomalies or []):
        findings.append({
            "title": f"异常标记: {a}",
            "evidence": [f"系统检测到异常信号: {a}"],
            "severity": "medium",
        })

    # from propagation comparison (safe against None)
    sc_ext = result_dict.get("scenario_extension") or {}
    prop = sc_ext.get("propagation", {}) if isinstance(sc_ext, dict) else {}
    if isinstance(prop, dict):
        comp = prop.get("comparison", {})
        if comp:
            findings.append({
                "title": f"传播仿真: 干预{'有效' if comp.get('intervention_effective') else '无效'}",
                "evidence": [
                    f"coverage_delta={comp.get('coverage_delta', 0)}",
                    f"action_delta={comp.get('action_delta', 0)}",
                    f"peak_risk_delta={comp.get('peak_risk_delta', 0)}",
                ],
                "severity": "high" if comp.get("coverage_delta", 0) > 0.1 else "medium",
            })

    return findings


def _extract_timeline(result_dict: dict, propagation: dict | None) -> list[dict]:
    timeline: list[dict] = []

    for branch_key in ("branch_a_log", "branch_b_log"):
        branch_log = result_dict.get(branch_key, [])
        for item in (branch_log or []):
            if isinstance(item, dict):
                ws = item.get("world_state", {})
                timeline.append({
                    "branch": "A" if "a" in branch_key else "B",
                    "step": item.get("step", 0),
                    "action": item.get("action", item.get("agent_action", "")),
                    "risk": ws.get("posterior_risk", 0.0) if isinstance(ws, dict) else 0.0,
                    "reversibility": ws.get("reversibility", 0.0) if isinstance(ws, dict) else 0.0,
                })

    if isinstance(propagation, dict):
        for branch_key in ("branch_a", "branch_b"):
            branch = propagation.get(branch_key, {})
            if isinstance(branch, dict):
                for item in branch.get("coverage_curve", []) or []:
                    if isinstance(item, dict):
                        timeline.append({
                            "branch": f"propagation_{branch_key[-1].upper()}",
                            "tick": item.get("tick", 0),
                            "coverage": item.get("coverage", 0.0),
                            "risk": item.get("risk", 0.0),
                        })

    return timeline
