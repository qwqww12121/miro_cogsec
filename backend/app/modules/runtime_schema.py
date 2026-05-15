"""CogSec-MIROFISH mainline runtime schemas."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


def _rounded(value: Any, digits: int = 3) -> float:
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return 0.0


@dataclass
class PersonaStateVector:
    """Structured digital-twin state used by the runtime."""

    authority_compliance: float
    time_pressure_sensitivity: float
    financial_stress: float
    loss_aversion: float
    fomo_susceptibility: float
    verification_habit: float
    help_seeking_tendency: float
    analytic_control: float
    emotional_volatility: float
    digital_trust_boundary: float
    asset_sensitivity: float
    risk_recovery_awareness: float
    confidence_level: float
    system1_bias: float
    system2_control: float
    cognitive_mode: str
    switch_policy: Dict[str, Any] = field(default_factory=dict)
    storage_policy: Dict[str, Any] = field(default_factory=dict)
    source_profile: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        for key, value in list(payload.items()):
            if isinstance(value, float):
                payload[key] = _rounded(value, 2)
        return payload


@dataclass
class RiskGraphNode:
    """Renderable graph node."""

    id: str
    name: str
    category: str
    value: float = 0.0
    risk: float = 0.0
    symbol_size: float = 40.0
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "value": _rounded(self.value, 2),
            "risk": _rounded(self.risk, 2),
            "symbolSize": _rounded(self.symbol_size, 1),
            "description": self.description,
            "metadata": self.metadata,
        }
        return payload


@dataclass
class RiskGraphEdge:
    """Renderable graph edge."""

    source: str
    target: str
    relation: str
    value: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "relation": self.relation,
            "label": self.relation,
            "value": _rounded(self.value, 2),
            "metadata": self.metadata,
        }


@dataclass
class RiskGraphBundle:
    """Threat-persona-context graph plus retrieval evidence."""

    schema_version: str
    threat_template_nodes: List[Dict[str, Any]]
    evidence_items: List[Dict[str, Any]]
    persuasion_principles: List[str]
    persona_weakness_hits: List[Dict[str, Any]]
    asset_targets: List[Dict[str, Any]]
    environment_context: Dict[str, Any]
    fork_points: List[Dict[str, Any]]
    nodes: List[RiskGraphNode]
    edges: List[RiskGraphEdge]
    attack_strategy_chain: List[Dict[str, Any]] = field(default_factory=list)
    consistency_score: float = 0.0
    hallucination_rollback: bool = False
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        categories = []
        seen = set()
        for node in self.nodes:
            if node.category in seen:
                continue
            categories.append({"name": node.category})
            seen.add(node.category)
        return {
            "schema_version": self.schema_version,
            "threat_template_nodes": self.threat_template_nodes,
            "evidence_items": self.evidence_items,
            "persuasion_principles": self.persuasion_principles,
            "persona_weakness_hits": self.persona_weakness_hits,
            "asset_targets": self.asset_targets,
            "environment_context": self.environment_context,
            "fork_points": self.fork_points,
            "attack_strategy_chain": self.attack_strategy_chain,
            "consistency_score": _rounded(self.consistency_score, 3),
            "hallucination_rollback": self.hallucination_rollback,
            "warnings": self.warnings,
            "nodes": [node.to_dict() for node in self.nodes],
            "links": [edge.to_dict() for edge in self.edges],
            "categories": categories,
        }


@dataclass
class WorldStateSnapshot:
    """Single state of the MIRO-FISH mainline world."""

    step: int
    stage: str
    action: str
    trust_score: float
    cognitive_mode: str
    asset_exposure: float
    intervention_window: float
    posterior_risk: float
    reversibility: float
    evidence_hits: List[str] = field(default_factory=list)
    persona_hits: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step": self.step,
            "stage": self.stage,
            "action": self.action,
            "trust_score": _rounded(self.trust_score, 2),
            "cognitive_mode": self.cognitive_mode,
            "asset_exposure": _rounded(self.asset_exposure, 3),
            "intervention_window": _rounded(self.intervention_window, 3),
            "posterior_risk": _rounded(self.posterior_risk, 3),
            "reversibility": _rounded(self.reversibility, 3),
            "evidence_hits": self.evidence_hits,
            "persona_hits": self.persona_hits,
            "notes": self.notes,
        }


@dataclass
class BranchTraceStep:
    """Step in a branch trace."""

    branch: str
    step: int
    action: str
    action_type: str
    fork_point_type: str
    world_state: WorldStateSnapshot
    posterior_updates: Dict[str, Any]
    evidence_refs: List[str] = field(default_factory=list)
    persona_hit_chain: List[str] = field(default_factory=list)
    irreversible: bool = False
    audit_flag: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "branch": self.branch,
            "step": self.step,
            "action": self.action,
            "action_type": self.action_type,
            "fork_point_type": self.fork_point_type,
            "world_state": self.world_state.to_dict(),
            "posterior_updates": self.posterior_updates,
            "evidence_refs": self.evidence_refs,
            "persona_hit_chain": self.persona_hit_chain,
            "irreversible": self.irreversible,
            "audit_flag": self.audit_flag,
            "agent_action": self.action,
            "victim_response": self.posterior_updates.get("victim_response", ""),
            "triggered_principles": self.posterior_updates.get("triggered_principles", []),
            "asset_exposure_coefficient": self.world_state.asset_exposure,
            "is_protection_action": self.branch.upper() == "B",
            "scores_after": {
                "posterior_risk": self.world_state.posterior_risk,
                "reversibility": self.world_state.reversibility,
                "trust_score": self.world_state.trust_score,
            },
        }


@dataclass
class InterventionPrescription:
    """Actionable and node-bound intervention advice."""

    title: str
    priority: int
    target_failure_node: str
    trigger_step: int
    window_open_step: int
    window_close_step: int
    rationale: str
    recommended_actions: List[str]
    channel: str
    expected_effect: str
    fallback: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ForkComparisonResult:
    """Branch comparison and mainline risk evidence."""

    fork_point_type: str
    fork_node_id: str
    branch_a_state_trace: List[BranchTraceStep]
    branch_b_state_trace: List[BranchTraceStep]
    posterior_updates: List[Dict[str, Any]]
    reversibility_curve: List[Dict[str, Any]]
    persona_hit_chain: List[str]
    evidence_graph_consistency: float
    trajectory_gap: float
    irreversibility_loss: float
    low_discriminability: bool = False
    anomaly_flags: List[str] = field(default_factory=list)
    best_intervention_window: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fork_point_type": self.fork_point_type,
            "fork_node_id": self.fork_node_id,
            "branch_a_state_trace": [step.to_dict() for step in self.branch_a_state_trace],
            "branch_b_state_trace": [step.to_dict() for step in self.branch_b_state_trace],
            "posterior_updates": self.posterior_updates,
            "reversibility_curve": self.reversibility_curve,
            "persona_hit_chain": self.persona_hit_chain,
            "evidence_graph_consistency": _rounded(self.evidence_graph_consistency, 3),
            "trajectory_gap": _rounded(self.trajectory_gap, 3),
            "irreversibility_loss": _rounded(self.irreversibility_loss, 3),
            "low_discriminability": self.low_discriminability,
            "anomaly_flags": self.anomaly_flags,
            "best_intervention_window": self.best_intervention_window,
        }

