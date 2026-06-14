"""Metrics — compute key nodes and summarise traces without networkx."""

from __future__ import annotations

from typing import Any, Dict, List

from .schema import PropagationAction, PropagationAgent, PropagationTrace


def compute_key_nodes(
    agents: list[PropagationAgent],
    adjacency: dict[str, list[str]],
    actions: list[PropagationAction],
    top_k: int = 5,
) -> list[dict]:
    """Heuristic key-node scoring.

    score = 0.45 * norm_out_degree + 0.35 * norm_action_count + 0.20 * influence
    """
    n = max(1, len(agents))
    raw_max_deg = max((len(adjacency.get(a.agent_id, [])) for a in agents), default=0)
    max_deg = max(raw_max_deg, 1)  # guard against empty adjacency → division by zero
    action_counts: dict[str, int] = {}
    for act in actions:
        action_counts[act.source_agent_id] = action_counts.get(act.source_agent_id, 0) + 1
    max_actions = max(action_counts.values(), default=1)

    scores: list[dict] = []
    for a in agents:
        deg = len(adjacency.get(a.agent_id, []))
        cnt = action_counts.get(a.agent_id, 0)
        score = 0.45 * (deg / max_deg) + 0.35 * (cnt / max_actions) + 0.20 * a.influence
        scores.append({
            "agent_id": a.agent_id,
            "role": a.role,
            "score": round(score, 3),
            "out_degree": deg,
            "action_count": cnt,
            "intervention_reason": _reason(a.role, score, deg, cnt),
        })

    scores.sort(key=lambda x: x["score"], reverse=True)
    return scores[:top_k]


def summarize_trace(trace: PropagationTrace) -> dict:
    """Return a compact summary dict for a PropagationTrace."""
    peak_risk = 0.0
    peak_emotion = "confusion"
    if trace.emotion_curve:
        max_item = max(trace.emotion_curve, key=lambda e: e.get("risk", 0.0))
        peak_risk = round(max_item.get("risk", 0.0), 3)
        peak_emotion = _dominant_emotion(max_item)

    coverage_final = 0.0
    if trace.coverage_curve:
        coverage_final = trace.coverage_curve[-1].get("coverage", 0.0)

    return {
        "coverage_final": round(coverage_final, 3),
        "peak_risk": peak_risk,
        "peak_emotion": peak_emotion,
        "key_node_count": len(trace.key_nodes),
        "total_actions": len(trace.actions),
    }


def _reason(role: str, score: float, deg: int, cnt: int) -> str:
    if score > 0.6:
        return f"high influence and high repost activity ({role})"
    if cnt > deg:
        return f"frequent action originator ({role})"
    return f"structural hub ({role})"


def _dominant_emotion(item: dict) -> str:
    best = "confusion"
    best_v = item.get("confusion", 0.0)
    for k in ("panic", "anger", "trust"):
        v = item.get(k, 0.0)
        if v > best_v:
            best_v = v
            best = k
    return best
