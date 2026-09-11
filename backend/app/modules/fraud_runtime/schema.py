"""fraud_runtime schemas — independent state, memory, and interaction traces."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


# ── Actor State Schemas ──────────────────────────────────────────────


@dataclass
class ThreatActorState:
    """Private state of the scammer / threat actor."""

    actor_id: str = "threat_actor"
    claimed_identity: str = ""
    objective: str = ""
    current_tactic: str = ""
    pressure_level: float = 0.5  # 0.0–1.0
    information_requested: List[str] = field(default_factory=list)
    previous_actions: List[str] = field(default_factory=list)
    memory: List[str] = field(default_factory=list)

    # Round 3 agent-type markers
    entity_kind: str = "runtime_agent"
    is_runtime_agent: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "actor_id": self.actor_id,
            "claimed_identity": self.claimed_identity,
            "objective": self.objective,
            "current_tactic": self.current_tactic,
            "pressure_level": round(self.pressure_level, 3),
            "information_requested": self.information_requested,
            "previous_actions": self.previous_actions,
            "memory": list(self.memory),
            "entity_kind": self.entity_kind,
            "is_runtime_agent": self.is_runtime_agent,
        }


@dataclass
class UserTwinState:
    """Private state of the user digital twin in a fraud interaction.

    Initialised from CognitiveProfile via well-defined mapping rules.
    """

    actor_id: str = "user_twin"
    trust: float = 0.5  # 0.0–1.0, from trust_threshold
    verification_tendency: float = 0.5  # from verification_habit
    urgency_sensitivity: float = 0.5  # from time_pressure
    compliance_tendency: float = 0.5  # from authority_compliance
    risk_awareness: float = 0.5  # from risk_recovery_awareness
    cognitive_load: float = 0.5  # from cognitive_load
    previous_actions: List[str] = field(default_factory=list)
    memory: List[str] = field(default_factory=list)

    # Round 3 agent-type markers
    entity_kind: str = "runtime_agent"
    is_runtime_agent: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "actor_id": self.actor_id,
            "trust": round(self.trust, 3),
            "verification_tendency": round(self.verification_tendency, 3),
            "urgency_sensitivity": round(self.urgency_sensitivity, 3),
            "compliance_tendency": round(self.compliance_tendency, 3),
            "risk_awareness": round(self.risk_awareness, 3),
            "cognitive_load": round(self.cognitive_load, 3),
            "previous_actions": self.previous_actions,
            "memory": list(self.memory),
            "entity_kind": self.entity_kind,
            "is_runtime_agent": self.is_runtime_agent,
        }


@dataclass
class VerifierState:
    """Private state of the independent verifier.

    Has access to RiskGraph evidence, RAG evidence, and known scam patterns
    — a different information set from ThreatActor and UserTwin.
    """

    actor_id: str = "verifier"
    evidence_refs: List[str] = field(default_factory=list)
    known_scam_patterns: List[str] = field(default_factory=list)
    claimed_identity_info: Dict[str, Any] = field(default_factory=dict)
    verification_results: List[Dict[str, Any]] = field(default_factory=list)
    memory: List[str] = field(default_factory=list)

    # Round 3 agent-type markers
    entity_kind: str = "runtime_agent"
    is_runtime_agent: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "actor_id": self.actor_id,
            "evidence_refs": self.evidence_refs,
            "known_scam_patterns": self.known_scam_patterns,
            "claimed_identity_info": self.claimed_identity_info,
            "verification_results": self.verification_results,
            "memory": list(self.memory),
            "entity_kind": self.entity_kind,
            "is_runtime_agent": self.is_runtime_agent,
        }


# ── Interaction Trace Schemas ────────────────────────────────────────


@dataclass
class InteractionStep:
    """One step of a single actor within a fraud interaction round."""

    round: int
    actor_id: str
    observation_refs: List[str] = field(default_factory=list)
    action: str = ""
    target_actor_id: str = ""
    state_delta: Dict[str, Any] = field(default_factory=dict)
    evidence_refs: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "round": self.round,
            "actor_id": self.actor_id,
            "observation_refs": self.observation_refs,
            "action": self.action,
            "target_actor_id": self.target_actor_id,
            "state_delta": self.state_delta,
            "evidence_refs": self.evidence_refs,
        }


@dataclass
class FraudInteractionResult:
    """Complete result of a fraud multi-role interaction run."""

    runtime_mode: str = "deterministic_fallback"  # llm_driven | hybrid | deterministic_fallback
    status: str = "degraded"  # "complete" | "degraded"
    round_count: int = 0
    actors: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    interaction_trace: List[InteractionStep] = field(default_factory=list)
    branch_a: Dict[str, Any] = field(default_factory=dict)
    branch_b: Dict[str, Any] = field(default_factory=dict)
    branch_comparison: Dict[str, Any] = field(default_factory=dict)
    evidence_refs: List[str] = field(default_factory=list)
    risk_events: List[Dict[str, Any]] = field(default_factory=list)
    decision_provenance: Dict[str, Any] = field(default_factory=dict)
    degraded_reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "runtime_mode": self.runtime_mode,
            "status": self.status,
            "round_count": self.round_count,
            "actors": self.actors,
            "interaction_trace": [step.to_dict() for step in self.interaction_trace],
            "branch_a": self.branch_a,
            "branch_b": self.branch_b,
            "branch_comparison": self.branch_comparison,
            "evidence_refs": self.evidence_refs,
            "risk_events": self.risk_events,
            "decision_provenance": self.decision_provenance,
            "degraded_reasons": self.degraded_reasons,
        }
