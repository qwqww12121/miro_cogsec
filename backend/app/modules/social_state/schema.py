"""Unified social-state schema — canonical actors, edges, and snapshots.

These types are the single source of truth for agent identity across the
entire pipeline: RiskGraph → Propagation → OASIS → Intervention → Frontend.

Every actor, edge, and claim carries an ``actor_id`` that is stable across
all downstream modules.  Modules may *add* data but MUST preserve the
canonical ``actor_id``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from copy import deepcopy
from typing import Any, Dict, List, Optional
import uuid


# ---------------------------------------------------------------------------
# Provenance tag
# ---------------------------------------------------------------------------

PROVENANCE_INPUT = "input"
PROVENANCE_INFERRED = "inferred"
PROVENANCE_SYNTHETIC = "synthetic"
PROVENANCE_UNKNOWN = "unknown"

VALID_PROVENANCE = frozenset({
    PROVENANCE_INPUT, PROVENANCE_INFERRED, PROVENANCE_SYNTHETIC, PROVENANCE_UNKNOWN,
})


def _default_social_provenance() -> Dict[str, Any]:
    """Describe the internal model additions without changing API semantics."""
    return {
        "social_model_version": "actor_state_v2",
        "actor_state_conditioned": True,
        "role_conditioned": True,
        "repeated_exposure_enabled": True,
        "dynamic_belief_enabled": True,
        "dynamic_trust_enabled": True,
        "community_role_decoupled": True,
        "content_semantics_classified": False,
    }


# ---------------------------------------------------------------------------
# ActorState
# ---------------------------------------------------------------------------


@dataclass
class ActorCognitiveFeatures:
    """Behaviour-relevant cognitive dimensions mapped from CognitiveProfile.

    The named fields are the directly used propagation features; the complete
    18-dimension vector is retained in ``profile_dimensions`` for S0 audit and
    persona conditioning.
    """
    trust_tendency: float = 0.5          # 0=highly suspicious, 1=highly trusting
    verification_tendency: float = 0.5   # 0=never verifies, 1=always verifies
    urgency_sensitivity: float = 0.5     # 0=calm under pressure, 1=easily rushed
    compliance_tendency: float = 0.5     # 0=resists authority, 1=highly compliant
    risk_awareness: float = 0.5          # 0=risk-blind, 1=hyper-aware
    profile_ref: str = ""                # reference to source CognitiveProfile
    profile_dimensions: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_profile(cls, profile: Any) -> "ActorCognitiveFeatures":
        """Derive cognitive features from a CognitiveProfile object."""
        try:
            dimension_names = (
                "time_pressure", "financial_pressure", "info_asymmetry",
                "emotional_volatility", "cognitive_load", "authority_intensity",
                "authority_compliance", "social_proof_sensitivity",
                "scarcity_sensitivity", "loss_aversion_threshold",
                "gambler_fallacy", "trust_threshold", "decision_delay",
                "verification_habit", "help_seeking", "link_check_ability",
                "transaction_review", "prior_experience",
            )
            dimensions = {
                key: round(max(0.0, min(1.0, float(getattr(profile, key, 5.0)) / 10.0)), 4)
                for key in dimension_names
            }
            return cls(
                trust_tendency=round(1.0 - getattr(profile, "authority_compliance", 5.0) / 10.0, 3),
                verification_tendency=round(getattr(profile, "verification_habit", 5.0) / 10.0, 3),
                urgency_sensitivity=round(getattr(profile, "time_pressure", 5.0) / 10.0, 3),
                compliance_tendency=round(getattr(profile, "authority_compliance", 5.0) / 10.0, 3),
                risk_awareness=round(getattr(profile, "transaction_review", 5.0) / 10.0, 3),
                profile_ref=getattr(profile, "scenario_type", ""),
                profile_dimensions=dimensions,
            )
        except Exception:
            return cls()


@dataclass
class ActorState:
    """A single actor in the unified social state.

    ``actor_id`` is the canonical identifier used across the entire pipeline.
    """

    actor_id: str
    role: str                                    # e.g. "student_kol", "official_responder"
    display_name: str = ""
    community_id: str = ""

    # propagation parameters (0.0 – 1.0)
    influence: float = 0.5
    susceptibility: float = 0.5
    activity: float = 0.5
    trust_in_official: float = 0.5
    stance: str = "neutral"

    # cognitive mapping
    cognitive_features: ActorCognitiveFeatures = field(default_factory=ActorCognitiveFeatures)

    # evidence & source tracking
    evidence_refs: List[str] = field(default_factory=list)
    source_refs: List[str] = field(default_factory=list)

    # provenance
    provenance: str = PROVENANCE_SYNTHETIC

    # extensibility
    metadata: Dict[str, Any] = field(default_factory=dict)

    # actor-specific cognitive/social state.  All fields are optional from the
    # caller's perspective through defaults so old fixtures remain constructible.
    prior_belief: float = 0.5
    belief_strength: float = 0.5
    topic_involvement: float = 0.5
    institutional_trust: Optional[float] = None
    verification_tendency: float = 0.5
    confirmation_bias: float = 0.5
    social_proof_sensitivity: float = 0.5
    reactance: float = 0.5
    emotional_activation: float = 0.5
    share_propensity: Optional[float] = None
    exposure_count: int = 0
    last_exposure_tick: Optional[int] = None
    belief_history: List[Dict[str, Any]] = field(default_factory=list)
    trust_history: List[Dict[str, Any]] = field(default_factory=list)
    exposure_history: List[Dict[str, Any]] = field(default_factory=list)

    # Used only by the public_opinion scenario extension.  The defaults keep
    # the canonical S0 schema backward-compatible for event/fraud callers.
    narrative_beliefs: Dict[str, float] = field(default_factory=dict)
    narrative_exposure_count: Dict[str, int] = field(default_factory=dict)
    narrative_adoption_state: Dict[str, str] = field(default_factory=dict)
    narrative_belief_history: List[Dict[str, Any]] = field(default_factory=list)
    dominant_narrative_id: Optional[str] = None
    current_narrative_id: Optional[str] = None
    narrative_switch_count: int = 0

    def __post_init__(self):
        if self.provenance not in VALID_PROVENANCE:
            raise ValueError(f"Invalid provenance: {self.provenance}")
        if self.institutional_trust is None:
            self.institutional_trust = self.trust_in_official
        self.trust_in_official = self.institutional_trust
        if self.share_propensity is None:
            self.share_propensity = self.activity

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["cognitive_features"] = self.cognitive_features.to_dict()
        return result

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "ActorState":
        """Load legacy actor JSON while defaulting newly added state fields."""
        known_fields = set(cls.__dataclass_fields__)
        values = {key: value for key, value in payload.items() if key in known_fields}
        cognitive = values.get("cognitive_features")
        if isinstance(cognitive, dict):
            values["cognitive_features"] = ActorCognitiveFeatures(**{
                key: value for key, value in cognitive.items()
                if key in ActorCognitiveFeatures.__dataclass_fields__
            })
        return cls(**values)


# ---------------------------------------------------------------------------
# SocialEdge
# ---------------------------------------------------------------------------


@dataclass
class SocialEdge:
    """A directed relationship between two actors."""

    edge_id: str
    source_actor_id: str
    target_actor_id: str
    relation_type: str   # follow | trust | friend | same_community | official_relation | information_flow
    weight: float = 1.0
    provenance: str = PROVENANCE_SYNTHETIC
    metadata: Dict[str, Any] = field(default_factory=dict)

    VALID_RELATIONS = frozenset({
        "follow", "trust", "friend", "same_community",
        "official_relation", "information_flow",
    })

    def __post_init__(self):
        if self.relation_type not in self.VALID_RELATIONS:
            raise ValueError(f"Invalid relation_type: {self.relation_type}")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# SocialState
# ---------------------------------------------------------------------------


@dataclass
class SocialState:
    """Complete social state for a scenario — actors, edges, claims, evidence.

    This is the *canonical* representation that feeds RiskGraph, Propagation,
    OASIS, and Intervention Search.
    """

    scenario_id: str
    scenario_type: str
    actors: List[ActorState] = field(default_factory=list)
    edges: List[SocialEdge] = field(default_factory=list)  # planned / synthetic edges
    observed_oasis_edges: List[SocialEdge] = field(default_factory=list)  # from real OASIS follow data
    observed_edges_status: str = "unavailable"  # unavailable | available | partial
    claims: List[Dict[str, Any]] = field(default_factory=list)
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    initial_event: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    provenance: Dict[str, Any] = field(default_factory=_default_social_provenance)
    simulation_state_id: str = field(default_factory=lambda: f"SIM_{uuid.uuid4().hex[:12].upper()}")

    def __post_init__(self):
        self.provenance.setdefault("simulation_state_id", self.simulation_state_id)

    # -- helpers --

    def actor_by_id(self, actor_id: str) -> Optional[ActorState]:
        for a in self.actors:
            if a.actor_id == actor_id:
                return a
        return None

    def actor_ids(self) -> List[str]:
        return [a.actor_id for a in self.actors]

    def edges_for(self, actor_id: str) -> List[SocialEdge]:
        return [e for e in self.edges if e.source_actor_id == actor_id]

    def to_adjacency(self) -> Dict[str, List[str]]:
        """Build a lightweight adjacency dict for the propagation simulator."""
        adj: Dict[str, List[str]] = {a.actor_id: [] for a in self.actors}
        for e in self.edges:
            if e.source_actor_id in adj:
                adj[e.source_actor_id].append(e.target_actor_id)
        return adj

    def to_adjacency_observed(self) -> Dict[str, List[str]]:
        """Build adjacency from observed OASIS edges when available."""
        if self.observed_edges_status != "available" or not self.observed_oasis_edges:
            return self.to_adjacency()  # fall back to planned edges
        adj: Dict[str, List[str]] = {a.actor_id: [] for a in self.actors}
        for e in self.observed_oasis_edges:
            if e.source_actor_id in adj:
                adj[e.source_actor_id].append(e.target_actor_id)
        return adj

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "scenario_type": self.scenario_type,
            "actors": [a.to_dict() for a in self.actors],
            "edges": [e.to_dict() for e in self.edges],
            "observed_oasis_edges": [e.to_dict() for e in self.observed_oasis_edges],
            "observed_edges_status": self.observed_edges_status,
            "claims": self.claims,
            "evidence": self.evidence,
            "initial_event": self.initial_event,
            "metadata": self.metadata,
            "provenance": self.provenance,
            "simulation_state_id": self.simulation_state_id,
        }

    def summary(self) -> Dict[str, Any]:
        """Compact summary suitable for API responses."""
        return {
            "scenario_id": self.scenario_id,
            "scenario_type": self.scenario_type,
            "actor_count": len(self.actors),
            "edge_count": len(self.edges),
            "observed_edge_count": len(self.observed_oasis_edges),
            "observed_edges_status": self.observed_edges_status,
            "claim_count": len(self.claims),
            "evidence_count": len(self.evidence),
            "actor_roles": list({a.role for a in self.actors}),
            "provenance": self.provenance,
            "simulation_state_id": self.simulation_state_id,
            "provenance_counts": {
                "input": sum(1 for a in self.actors if a.provenance == "input"),
                "inferred": sum(1 for a in self.actors if a.provenance == "inferred"),
                "synthetic": sum(1 for a in self.actors if a.provenance == "synthetic"),
            },
            "topology_type": (self.metadata or {}).get("topology_type"),
            "agent_count": len(self.actors),
        }

    def to_display_graph(self, max_nodes: int = 24) -> Dict[str, Any]:
        """Compact node/edge payload for the frontend relationship map."""
        degree: Dict[str, int] = {actor.actor_id: 0 for actor in self.actors}
        for edge in self.edges:
            if edge.source_actor_id in degree:
                degree[edge.source_actor_id] += 1
            if edge.target_actor_id in degree:
                degree[edge.target_actor_id] += 1
        ranked = sorted(
            self.actors,
            key=lambda actor: (
                0 if actor.provenance == PROVENANCE_INPUT else 1,
                -degree.get(actor.actor_id, 0),
                -float(actor.influence or 0.0),
            ),
        )
        selected = ranked[:max_nodes]
        selected_ids = {actor.actor_id for actor in selected}
        nodes = []
        for actor in selected:
            label = (actor.display_name or actor.role or actor.actor_id)[:16]
            role = actor.role or ""
            if any(token in role for token in ("official", "responder", "admin")):
                kind = "action"
            elif any(token in role for token in ("kol", "amplifier", "source", "spreader")):
                kind = "risk"
            else:
                kind = "profile"
            hint = actor_behavior_hint(actor)
            nodes.append({
                "id": actor.actor_id,
                "label": label,
                "name": label,
                "desc": hint,
                "kind": kind,
                "source": "轻量传播仿真",
                "type": role,
                "role": role,
                "stance": actor.stance,
                "influence": round(float(actor.influence or 0.0), 3),
                "activity": round(float(actor.activity or 0.0), 3),
                "behavior_hint": hint,
                "behaviors": [],
                "provenance": actor.provenance,
            })
        edges = []
        for edge in self.edges:
            if edge.source_actor_id not in selected_ids or edge.target_actor_id not in selected_ids:
                continue
            source_actor = self.actor_by_id(edge.source_actor_id)
            edges.append({
                "source": edge.source_actor_id,
                "target": edge.target_actor_id,
                "relation": interaction_verb(getattr(source_actor, "role", "") or "", edge.relation_type),
                "type": edge.relation_type,
            })
            if len(edges) >= 60:
                break
        metadata = self.metadata or {}
        return {
            "nodes": nodes,
            "edges": edges,
            "directed": True,
            "source": "lightweight_propagation",
            "engine": "social_state",
            "agent_count": len(self.actors),
            "displayed_nodes": len(nodes),
            "topology_type": metadata.get("topology_type"),
        }


_STANCE_ZH = {
    "supportive": "倾向采信",
    "support": "倾向采信",
    "skeptical": "倾向质疑",
    "oppose": "倾向反对",
    "neutral": "观望",
}

_ACTION_TYPE_ZH = {
    "spread": "转发",
    "exposed": "告知",
    "share": "转发",
    "post": "发布",
    "comment": "评论",
    "repost": "转发",
    "like": "点赞",
    "follow": "关注",
}

_ROLE_VERB = (
    (("fact_check", "checker", "核查"), "澄清"),
    (("official", "responder", "admin", "school"), "通报"),
    (("media", "observer", "journalist"), "报道"),
    (("kol", "repost"), "转发"),
    (("controversy", "amplifier", "spreader"), "扩散"),
    (("source", "origin", "poster"), "发布"),
    (("teacher",), "提醒"),
    (("student", "viewer", "ordinary"), "讨论"),
    (("victim", "twin"), "求助"),
    (("attack", "adversary", "threat"), "施压"),
    (("family",), "劝阻"),
    (("police", "bank", "verify"), "核实"),
    (("moderator", "platform"), "处置"),
)

_RELATION_ZH = {
    "follow": "关注",
    "trust": "信任往来",
    "friend": "好友沟通",
    "same_community": "同群讨论",
    "official_relation": "官方通报",
}


def interaction_verb(source_role: str, relation_type: str = "", action_type: str = "") -> str:
    kind = str(action_type or "").lower()
    if kind in _ACTION_TYPE_ZH and kind != "exposed":
        return _ACTION_TYPE_ZH[kind]
    rel = str(relation_type or "")
    if rel and rel != "information_flow":
        return _RELATION_ZH.get(rel, rel)
    role = str(source_role or "").lower()
    for tokens, verb in _ROLE_VERB:
        if any(token in role for token in tokens):
            return verb
    return "告知"


def outgoing_line(verb: str, other: str) -> str:
    lines = {
        "发布": f"把源头内容发给{other}",
        "转发": f"把内容转发给{other}",
        "扩散": f"把话题扩散给{other}",
        "煽动": f"向{other}放大争议",
        "澄清": f"向{other}澄清事实",
        "通报": f"向{other}通报官方说明",
        "报道": f"向{other}报道此事",
        "提醒": f"提醒{other}先核实再传播",
        "讨论": f"与{other}讨论此事",
        "告知": f"把消息告知{other}",
        "施压": f"向{other}继续施压",
        "求助": f"向{other}求助核验",
        "劝阻": f"劝{other}停下来核实",
        "核实": f"向{other}核实身份或账户",
        "处置": f"限制内容继续传向{other}",
        "评论": f"向{other}评论回应",
        "关注": f"关注{other}",
    }
    return lines.get(verb, f"向{other}{verb}")


def incoming_line(verb: str, other: str) -> str:
    lines = {
        "发布": f"从{other}处看到首发内容",
        "转发": f"从{other}处接到转发",
        "扩散": f"被{other}扩散触达",
        "煽动": f"被{other}带入争议",
        "澄清": f"收到{other}的澄清",
        "通报": f"收到{other}的官方通报",
        "报道": f"看到{other}的报道",
        "提醒": f"被{other}提醒核实",
        "讨论": f"与{other}沟通讨论",
        "告知": f"被{other}告知此事",
        "施压": f"受到{other}的施压",
        "求助": f"{other}向这边求助",
        "劝阻": f"被{other}劝阻",
        "核实": f"配合{other}核实",
        "处置": f"内容被{other}处置",
        "评论": f"收到{other}的评论",
    }
    return lines.get(verb, f"从{other}接到「{verb}」")


def actor_behavior_hint(actor: ActorState) -> str:
    """One-line typical behavior for this role, used when sim actions are sparse."""
    role = str(actor.role or "").lower()
    stance = _STANCE_ZH.get(str(actor.stance or "").lower(), "")
    if any(token in role for token in ("kol", "amplifier", "spreader")):
        action = "更容易转发、评论，把话题放大"
    elif any(token in role for token in ("official", "responder", "admin")):
        action = "更可能澄清、处置或限制扩散"
    elif "media" in role or "observer" in role:
        action = "观察并转述，可能带给更大受众"
    elif "teacher" in role:
        action = "向学生或同事转述、提醒"
    elif "student" in role:
        action = "在同学圈讨论或转发"
    elif "source" in role:
        action = "发出源头内容"
    else:
        action = "按自身活跃度和信任度决定是否转发"
    if stance:
        return f"{stance}，{action}"
    return action


def attach_graph_behaviors(graph: Dict[str, Any], actions: Any, max_per_node: int = 6) -> Dict[str, Any]:
    """Attach compact per-node action lists from a propagation trace."""
    payload = graph if isinstance(graph, dict) else {}
    nodes = payload.get("nodes") or []
    if not isinstance(nodes, list) or not nodes:
        return payload
    records: List[Dict[str, Any]] = []
    for item in actions or []:
        if isinstance(item, dict):
            records.append(item)
        elif hasattr(item, "to_dict"):
            converted = item.to_dict()
            if isinstance(converted, dict):
                records.append(converted)
    label_by_id = {
        str(node.get("id")): str(node.get("label") or node.get("name") or node.get("id") or "")
        for node in nodes
        if isinstance(node, dict)
    }
    role_by_id = {
        str(node.get("id")): str(node.get("role") or node.get("type") or node.get("label") or "")
        for node in nodes
        if isinstance(node, dict)
    }
    buckets: Dict[str, List[Dict[str, Any]]] = {str(node.get("id")): [] for node in nodes if isinstance(node, dict)}
    for record in records[:800]:
        source_id = str(record.get("source_agent_id") or record.get("source") or "")
        target_id = str(record.get("target_agent_id") or record.get("target") or "")
        kind = str(record.get("action_type") or record.get("type") or "exposed")
        tick = record.get("tick", record.get("step", ""))
        time_label = f"第 {tick} 步" if str(tick) != "" else ""
        source_label = label_by_id.get(source_id, source_id)
        target_label = label_by_id.get(target_id, target_id)
        verb = interaction_verb(role_by_id.get(source_id, ""), "", kind)
        if source_id in buckets:
            buckets[source_id].append({
                "time": time_label,
                "action": verb,
                "target": target_label,
                "content": outgoing_line(verb, target_label),
                "kind": kind,
                "tick": tick,
            })
        if target_id in buckets and target_id != source_id:
            buckets[target_id].append({
                "time": time_label,
                "action": verb,
                "target": source_label,
                "content": incoming_line(verb, source_label),
                "kind": "exposed" if kind == "spread" else kind,
                "tick": tick,
            })
    for node in nodes:
        if not isinstance(node, dict):
            continue
        items = buckets.get(str(node.get("id")), [])
        items.sort(key=lambda item: (0 if item.get("kind") in {"spread", "share", "repost", "post"} else 1, item.get("tick") or 99))
        compact = items[:max_per_node]
        node["behaviors"] = compact
        if compact and not node.get("desc"):
            first = compact[0]
            node["desc"] = first.get("content") or first.get("action") or node.get("desc")
    return payload


def propagation_trace_actions(propagation_result: Any) -> List[Any]:
    raw = propagation_result
    if hasattr(raw, "to_dict"):
        raw = raw.to_dict()
    if not isinstance(raw, dict):
        return []
    branch_a = raw.get("branch_a") or {}
    if hasattr(branch_a, "to_dict"):
        branch_a = branch_a.to_dict()
    if isinstance(branch_a, dict):
        return list(branch_a.get("actions") or [])
    return list(raw.get("actions") or [])


# ---------------------------------------------------------------------------
# SocialStateSnapshot — immutable starting point for OASIS
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SocialStateSnapshot:
    """Immutable snapshot of the social state at OASIS start time.

    Branch A and Branch B MUST derive from the same snapshot so that
    differences can be attributed to intervention, not initial conditions.
    """

    snapshot_id: str
    scenario_type: str
    actors: tuple          # tuple of ActorState (immutable)
    edges: tuple           # tuple of SocialEdge (immutable)
    initial_event: Dict[str, Any]
    seed: int
    model_config: Dict[str, Any] = field(default_factory=dict)
    simulation_state_id: str = ""

    @classmethod
    def from_state(cls, state: SocialState, seed: int = 42,
                   model_config: Optional[Dict[str, Any]] = None) -> "SocialStateSnapshot":
        return cls(
            snapshot_id=str(uuid.uuid4()),
            scenario_type=state.scenario_type,
            actors=tuple(deepcopy(state.actors)),
            edges=tuple(deepcopy(state.edges)),
            initial_event=dict(state.initial_event),
            seed=seed,
            model_config=dict(model_config or {}),
            simulation_state_id=state.simulation_state_id,
        )

    def to_actor_list(self) -> List[ActorState]:
        return list(self.actors)

    def to_edge_list(self) -> List[SocialEdge]:
        return list(self.edges)

    def to_adjacency(self) -> Dict[str, List[str]]:
        adj: Dict[str, List[str]] = {a.actor_id: [] for a in self.actors}
        for e in self.edges:
            if e.source_actor_id in adj:
                adj[e.source_actor_id].append(e.target_actor_id)
        return adj

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "scenario_type": self.scenario_type,
            "actor_count": len(self.actors),
            "edge_count": len(self.edges),
            "seed": self.seed,
            "model_config": self.model_config,
            "simulation_state_id": self.simulation_state_id,
        }


# ---------------------------------------------------------------------------
# MetricValue — typed metric with provenance
# ---------------------------------------------------------------------------


@dataclass
class MetricValue:
    """A single metric with explicit provenance so consumers know what to trust."""

    name: str
    value: float
    source_type: str          # native | derived | proxy | estimated
    definition: str = ""
    source_refs: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    VALID_SOURCES = frozenset({"native", "derived", "proxy", "estimated"})

    def __post_init__(self):
        if self.source_type not in self.VALID_SOURCES:
            raise ValueError(f"Invalid source_type: {self.source_type}")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# SimulationActionRecord — canonical OASIS action log
# ---------------------------------------------------------------------------


@dataclass
class SimulationActionRecord:
    """One row in the canonical OASIS action log.

    Used to reconstruct traces without relying on raw SQLite row ordering.
    """

    run_id: str
    branch_id: str
    tick: int
    actor_id: str                # canonical actor_id → maps to OASIS agent
    oasis_agent_id: str = ""     # OASIS-internal agent identifier
    action_type: str = ""        # CREATE_POST | REPOST | LIKE_POST | DO_NOTHING | ...
    target_id: str = ""          # target actor_id or "broadcast"
    content_ref: str = ""        # reference to content (not raw content for privacy)
    timestamp: float = 0.0       # wall clock when action was recorded
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
