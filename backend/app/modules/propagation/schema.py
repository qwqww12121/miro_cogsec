"""Propagation runtime schema — Agent, Event, Action, Trace, ForkedResult."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List
import time
import uuid


@dataclass
class PropagationAgent:
    agent_id: str
    role: str
    stance: str
    influence: float
    susceptibility: float
    activity: float
    trust_in_official: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PropagationEvent:
    event_id: str
    scenario_type: str
    seed_text: str
    seed_modalities: Dict[str, Any]
    risk_dimensions: List[str]
    initial_emotion: str
    created_at: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        scenario_type: str,
        seed_text: str,
        risk_dimensions: List[str],
        initial_emotion: str = "confusion",
        seed_modalities: Dict[str, Any] | None = None,
        metadata: Dict[str, Any] | None = None,
    ) -> "PropagationEvent":
        return cls(
            event_id=str(uuid.uuid4()),
            scenario_type=scenario_type,
            seed_text=seed_text,
            seed_modalities=seed_modalities or {"text": seed_text},
            risk_dimensions=risk_dimensions,
            initial_emotion=initial_emotion,
            created_at=time.time(),
            metadata=metadata or {},
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PropagationAction:
    tick: int
    source_agent_id: str
    target_agent_id: str
    action_type: str
    content_summary: str
    influence_delta: float
    risk_delta: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PropagationTrace:
    trace_id: str
    scenario_type: str
    ticks: int
    agents: List[PropagationAgent]
    actions: List[PropagationAction]
    coverage_curve: List[Dict[str, Any]]
    emotion_curve: List[Dict[str, Any]]
    key_nodes: List[Dict[str, Any]]
    final_metrics: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "scenario_type": self.scenario_type,
            "ticks": self.ticks,
            "agents": [a.to_dict() for a in self.agents],
            "actions": [a.to_dict() for a in self.actions],
            "coverage_curve": self.coverage_curve,
            "emotion_curve": self.emotion_curve,
            "key_nodes": self.key_nodes,
            "final_metrics": self.final_metrics,
            "metadata": self.metadata,
        }


@dataclass
class ForkedPropagationResult:
    fork_point: Dict[str, Any]
    branch_a: PropagationTrace
    branch_b: PropagationTrace
    comparison: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fork_point": self.fork_point,
            "branch_a": self.branch_a.to_dict(),
            "branch_b": self.branch_b.to_dict(),
            "comparison": self.comparison,
        }
