"""fraud_runtime metrics — lightweight interaction-level measurements.

Records runtime mode, round counts, per-actor action distributions,
and branch comparison statistics.  Does NOT expose hidden prompts or
chain-of-thought.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .schema import FraudInteractionResult


def collect_interaction_metrics(result: FraudInteractionResult) -> Dict[str, Any]:
    """Collect summary metrics from a FraudInteractionResult.

    Returns a compact dict suitable for inclusion in analysis results.
    """
    # Action counts per actor across both branches
    action_counts: Dict[str, Dict[str, int]] = {}
    for step in result.interaction_trace:
        aid = step.actor_id
        if aid not in action_counts:
            action_counts[aid] = {}
        act = step.action
        action_counts[aid][act] = action_counts[aid].get(act, 0) + 1

    # Branch-specific stats
    branch_a_risk_count = len(result.branch_a.get("risk_events", []))
    branch_b_risk_count = len(result.branch_b.get("risk_events", []))

    # Evidence usage
    evidence_used = len(result.evidence_refs)
    evidence_items_with_usage = len([
        ref for ref in result.evidence_refs
        if any(ref in str(step.evidence_refs) for step in result.interaction_trace)
    ])

    return {
        "runtime_mode": result.runtime_mode,
        "round_count": result.round_count,
        "total_steps": len(result.interaction_trace),
        "branch_a_rounds": result.branch_a.get("rounds_executed", 0),
        "branch_b_rounds": result.branch_b.get("rounds_executed", 0),
        "branch_a_user_complied": result.branch_a.get("user_complied", 0),
        "branch_b_user_complied": result.branch_b.get("user_complied", 0),
        "branch_a_user_refused": result.branch_a.get("user_refused", 0),
        "branch_b_user_refused": result.branch_b.get("user_refused", 0),
        "branch_a_risk_events": branch_a_risk_count,
        "branch_b_risk_events": branch_b_risk_count,
        "compliance_delta": result.branch_comparison.get("compliance_delta", 0),
        "threat_action_counts": action_counts.get("threat_actor", {}),
        "user_action_counts": action_counts.get("user_twin", {}),
        "verifier_action_counts": action_counts.get("verifier", {}),
        "evidence_refs_total": evidence_used,
        "evidence_refs_used_in_trace": evidence_items_with_usage,
    }
