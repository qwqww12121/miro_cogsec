"""Causal target selection for intervention candidates.

The selector is a deterministic, inspectable proxy over the already executed
baseline trace.  It uses observed source-to-target action flow, role, influence
and activity; centrality is retained as a diagnostic feature, not as the
selection objective.  A full simulator/OASIS counterfactual can replace this
implementation behind the same contract.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Dict, Iterable, List


def select_causal_targets(
    baseline_trace: Any,
    *,
    target_limit: int = 3,
    mode: str = "causal_targeting",
) -> Dict[str, Any]:
    nodes = list(getattr(baseline_trace, "key_nodes", []) or [])
    agents = {str(getattr(agent, "agent_id", "")): agent for agent in (getattr(baseline_trace, "agents", []) or [])}
    actions = list(getattr(baseline_trace, "actions", []) or [])
    outbound = Counter(str(getattr(action, "source_agent_id", "")) for action in actions)
    inbound = Counter(str(getattr(action, "target_agent_id", "")) for action in actions)
    downstream: Dict[str, set[str]] = defaultdict(set)
    for action in actions:
        source = str(getattr(action, "source_agent_id", ""))
        target = str(getattr(action, "target_agent_id", ""))
        if source and target:
            downstream[source].add(target)

    scored: List[Dict[str, Any]] = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_id = str(node.get("agent_id") or node.get("id") or "")
        if not node_id:
            continue
        agent = agents.get(node_id)
        influence = _number(node.get("influence"), getattr(agent, "influence", 0.0))
        activity = _number(node.get("activity"), getattr(agent, "activity", 0.0))
        centrality = _number(node.get("centrality"), influence)
        flow = float(outbound.get(node_id, 0) + inbound.get(node_id, 0))
        downstream_count = len(downstream.get(node_id, set()))
        role = str(node.get("role") or getattr(agent, "role", ""))
        role_bonus = 1.15 if role in {"repost_kol", "media_observer", "student_kol", "controversy_amplifier"} else 1.0
        if mode == "centrality_only":
            utility = centrality
            reason = "ablation: sorted by centrality diagnostic only"
        else:
            # Counterfactual utility proxy: how much observed flow is exposed
            # if this node is changed, discounted by influence/activity.
            utility = (0.45 * flow + 0.35 * downstream_count + 0.20 * influence * activity) * role_bonus
            reason = "observed action flow + downstream reach + agent state"
        scored.append({
            "node_id": node_id,
            "centrality_score": round(centrality, 6),
            "causal_utility": round(float(utility), 6),
            "observed_flow": int(flow),
            "downstream_reach": downstream_count,
            "role": role,
            "reason": reason,
        })
    scored.sort(key=lambda item: (item["causal_utility"], item["centrality_score"], item["node_id"]), reverse=True)
    selected = scored[: max(0, int(target_limit))]
    return {
        "mode": mode if mode in {"centrality_only", "causal_targeting"} else "causal_targeting",
        "selected_node_ids": [item["node_id"] for item in selected],
        "ranked_nodes": scored,
        "provenance": {
            "source": "baseline_trace_action_flow",
            "selector": "causal_proxy_v1" if mode != "centrality_only" else "centrality_only_ablation",
            "counterfactual_execution": False,
            "metric_valid": bool(scored),
        },
    }


def _number(value: Any, fallback: Any = 0.0) -> float:
    return float(value) if isinstance(value, (int, float)) else float(fallback or 0.0)
