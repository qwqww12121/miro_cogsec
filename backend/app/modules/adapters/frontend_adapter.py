"""FrontendAdapter — converts Core Result to graph_payload / UI fields.

Reads from core_analysis and risk_graph_bundle — does not add new
analysis facts.
"""

from __future__ import annotations

from typing import Any, Dict

from ..response_planner import build_graph_payload, build_latency_profile


def build_frontend_payload(
    core_result: Dict[str, Any],
    response_plan: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Build a frontend-ready graph payload from a Core Result.

    Returns a dict with ``graph_payload`` and ``latency_profile``.
    Does NOT modify the Core Result.
    """
    plan = response_plan or {}
    graph = build_graph_payload(result=core_result, response_plan=plan)
    latency = build_latency_profile(result=core_result)

    return {
        "graph_payload": graph,
        "latency_profile": latency,
    }
