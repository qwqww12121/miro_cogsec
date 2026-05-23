"""Propagation runtime — lightweight tick-based social propagation simulator."""

from .schema import (
    ForkedPropagationResult,
    PropagationAction,
    PropagationAgent,
    PropagationEvent,
    PropagationTrace,
)
from .agent_factory import build_agents
from .topology import build_topology
from .metrics import compute_key_nodes, summarize_trace
from .simulator import run_propagation_simulation, run_forked_propagation
from .oasis_adapter import OasisPropagationAdapter

__all__ = [
    "build_agents",
    "build_topology",
    "compute_key_nodes",
    "ForkedPropagationResult",
    "OasisPropagationAdapter",
    "PropagationAction",
    "PropagationAgent",
    "PropagationEvent",
    "PropagationTrace",
    "run_forked_propagation",
    "run_propagation_simulation",
    "summarize_trace",
]
