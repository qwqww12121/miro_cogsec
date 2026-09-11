"""ID mapping between canonical actor_id and module-specific identifiers.

Every module (RiskGraph, Propagation, OASIS, Frontend) MUST keep a
bidirectional mapping to the canonical ``actor_id`` so that all layers
can trace back to the same actor.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .schema import (
    ActorState,
    PROVENANCE_INPUT,
    PROVENANCE_INFERRED,
    PROVENANCE_SYNTHETIC,
)
from .behavior import actor_state_persona_summary


# ---------------------------------------------------------------------------
# Actor mapping registry
# ---------------------------------------------------------------------------


class ActorMapping:
    """Bidirectional mapping between canonical actor_id and module IDs."""

    def __init__(self):
        # canonical → {module_name: module_id}
        self._forward: Dict[str, Dict[str, str]] = {}
        # module_name → {module_id: canonical}
        self._reverse: Dict[str, Dict[str, str]] = {}

    def register(self, canonical_id: str, module_name: str, module_id: str) -> None:
        """Register a mapping from canonical to module-specific ID."""
        self._forward.setdefault(canonical_id, {})[module_name] = module_id
        self._reverse.setdefault(module_name, {})[module_id] = canonical_id

    def module_id(self, canonical_id: str, module_name: str) -> Optional[str]:
        """Get module-specific ID for a canonical actor."""
        return self._forward.get(canonical_id, {}).get(module_name)

    def canonical_id(self, module_name: str, module_id: str) -> Optional[str]:
        """Get canonical actor ID from a module-specific ID."""
        return self._reverse.get(module_name, {}).get(module_id)

    def all_canonical_ids(self) -> List[str]:
        return list(self._forward.keys())

    def all_module_ids(self, module_name: str) -> List[str]:
        return list(self._reverse.get(module_name, {}).keys())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "canonical_to_module": {k: dict(v) for k, v in self._forward.items()},
            "module_to_canonical": {k: dict(v) for k, v in self._reverse.items()},
        }


# ---------------------------------------------------------------------------
# RiskGraph → SocialState actor extraction
# ---------------------------------------------------------------------------


def extract_actors_from_risk_graph(
    risk_graph: Any,
    start_idx: int = 0,
    id_prefix: str = "actor",
) -> List[ActorState]:
    """Extract identifiable actors from RiskGraph nodes.

    Only nodes that represent real-world actors (not threats/evidence/fork
    points) get an actor_id.
    """
    actors: List[ActorState] = []
    try:
        nodes = getattr(risk_graph, "nodes", []) or []
    except Exception:
        return actors

    # Categories that could represent real actors
    actor_categories = {"agent", "actor", "persona", "primary", "adversary", "victim", "auditor"}

    for i, node in enumerate(nodes):
        try:
            category = getattr(node, "category", "")
            node_id = getattr(node, "id", "")
        except Exception:
            continue

        if category.lower() in actor_categories or "agent" in node_id.lower():
            actors.append(ActorState(
                actor_id=(
                    f"{id_prefix.upper()}_{(i + 1):03d}"
                    if id_prefix.upper() != "ACTOR"
                    else f"actor_{(start_idx + i):04d}"
                ),
                role=category or "unknown",
                display_name=getattr(node, "name", node_id),
                provenance=PROVENANCE_INFERRED,
            ))
    return actors


# ---------------------------------------------------------------------------
# PropagationAgent → ActorState conversion
# ---------------------------------------------------------------------------


def propagation_agent_to_actor(
    agent: Any,
    actor_id: str,
    actor_mapping: Optional[ActorMapping] = None,
) -> ActorState:
    """Convert a PropagationAgent to an ActorState, registering the mapping."""
    try:
        agent_id = getattr(agent, "agent_id", str(id(agent)))
    except Exception:
        agent_id = str(id(agent))

    if actor_mapping is not None:
        actor_mapping.register(actor_id, "propagation", agent_id)

    return ActorState(
        actor_id=actor_id,
        role=getattr(agent, "role", "unknown"),
        influence=getattr(agent, "influence", 0.5),
        susceptibility=getattr(agent, "susceptibility", 0.5),
        activity=getattr(agent, "activity", 0.5),
        trust_in_official=getattr(agent, "trust_in_official", 0.5),
        community_id=getattr(agent, "community_id", "") or getattr(agent, "metadata", {}).get("community_id", ""),
        stance=getattr(agent, "stance", "neutral"),
        prior_belief=getattr(agent, "prior_belief", 0.5),
        belief_strength=getattr(agent, "belief_strength", 0.5),
        topic_involvement=getattr(agent, "topic_involvement", 0.5),
        institutional_trust=getattr(agent, "institutional_trust", None),
        verification_tendency=getattr(agent, "verification_tendency", 0.5),
        confirmation_bias=getattr(agent, "confirmation_bias", 0.5),
        social_proof_sensitivity=getattr(agent, "social_proof_sensitivity", 0.5),
        reactance=getattr(agent, "reactance", 0.5),
        emotional_activation=getattr(agent, "emotional_activation", 0.5),
        share_propensity=getattr(agent, "share_propensity", None),
        exposure_count=getattr(agent, "exposure_count", 0),
        last_exposure_tick=getattr(agent, "last_exposure_tick", None),
        belief_history=list(getattr(agent, "belief_history", []) or []),
        trust_history=list(getattr(agent, "trust_history", []) or []),
        exposure_history=list(getattr(agent, "exposure_history", []) or []),
        narrative_beliefs=dict(getattr(agent, "narrative_beliefs", {}) or {}),
        narrative_exposure_count=dict(getattr(agent, "narrative_exposure_count", {}) or {}),
        narrative_adoption_state=dict(getattr(agent, "narrative_adoption_state", {}) or {}),
        narrative_belief_history=list(getattr(agent, "narrative_belief_history", []) or []),
        dominant_narrative_id=getattr(agent, "dominant_narrative_id", None),
        current_narrative_id=getattr(agent, "current_narrative_id", None),
        narrative_switch_count=int(getattr(agent, "narrative_switch_count", 0) or 0),
        provenance=PROVENANCE_SYNTHETIC,
    )


# ---------------------------------------------------------------------------
# ActorState → PropagationAgent conversion
# ---------------------------------------------------------------------------


def actor_to_propagation_agent(actor: ActorState) -> Any:
    """Convert an ActorState to a PropagationAgent for the simulator."""
    from ..propagation.schema import PropagationAgent

    return PropagationAgent(
        agent_id=actor.actor_id,  # canonical actor_id IS the propagation ID
        role=actor.role,
        stance=actor.stance,
        influence=actor.influence,
        susceptibility=actor.susceptibility,
        activity=actor.activity,
        trust_in_official=actor.trust_in_official,
        community_id=actor.community_id,
        prior_belief=actor.prior_belief,
        belief_strength=actor.belief_strength,
        topic_involvement=actor.topic_involvement,
        institutional_trust=actor.institutional_trust,
        verification_tendency=actor.verification_tendency,
        confirmation_bias=actor.confirmation_bias,
        social_proof_sensitivity=actor.social_proof_sensitivity,
        reactance=actor.reactance,
        emotional_activation=actor.emotional_activation,
        share_propensity=actor.share_propensity,
        exposure_count=actor.exposure_count,
        last_exposure_tick=actor.last_exposure_tick,
        belief_history=list(actor.belief_history),
        trust_history=list(actor.trust_history),
        exposure_history=list(actor.exposure_history),
        narrative_beliefs=dict(actor.narrative_beliefs),
        narrative_exposure_count=dict(actor.narrative_exposure_count),
        narrative_adoption_state=dict(actor.narrative_adoption_state),
        narrative_belief_history=list(actor.narrative_belief_history),
        dominant_narrative_id=actor.dominant_narrative_id,
        current_narrative_id=actor.current_narrative_id,
        narrative_switch_count=actor.narrative_switch_count,
        metadata={
            **actor.metadata,
            "provenance": actor.provenance,
            "display_name": actor.display_name,
            "community_id": actor.community_id,
            # Round 3: OASIS agents are runtime agents
            "entity_kind": "runtime_agent",
            "is_runtime_agent": True,
            "cognitive_features": actor.cognitive_features.to_dict(),
            "evidence_refs": actor.evidence_refs,
            "prior_belief": actor.prior_belief,
            "belief_strength": actor.belief_strength,
            "institutional_trust": actor.institutional_trust,
            "verification_tendency": actor.verification_tendency,
            "confirmation_bias": actor.confirmation_bias,
            "social_proof_sensitivity": actor.social_proof_sensitivity,
            "reactance": actor.reactance,
            "emotional_activation": actor.emotional_activation,
            "topic_involvement": actor.topic_involvement,
            "share_propensity": actor.share_propensity,
            "narrative_beliefs": dict(actor.narrative_beliefs),
            "narrative_exposure_count": dict(actor.narrative_exposure_count),
            "narrative_adoption_state": dict(actor.narrative_adoption_state),
            "dominant_narrative_id": actor.dominant_narrative_id,
        },
    )


# ---------------------------------------------------------------------------
# ActorState → OASIS CSV row
# ---------------------------------------------------------------------------


def actor_to_oasis_row(actor: ActorState, role_chars: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Convert an ActorState to an OASIS CSV row dict.

    The OASIS CSV expects: user_char, username, description
    """
    if role_chars is None:
        role_chars = _DEFAULT_ROLE_CHARS

    base_user_char = role_chars.get(
        actor.role,
        f"你是一名{actor.role}，正在社交平台上浏览内容。",
    )
    user_char = base_user_char + "\n" + actor_state_persona_summary(actor)
    return {
        "user_char": user_char,
        "username": f"{actor.role}_{actor.actor_id}",
        "description": (
            f"影响力={actor.influence:.2f} 易感性={actor.susceptibility:.2f} "
            f"立场={actor.stance} community={actor.community_id or 'unassigned'} "
            f"provenance={actor.provenance}"
        ),
    }


_DEFAULT_ROLE_CHARS: Dict[str, str] = {
    "student_kol": "你是一名在校大学生，关注热点话题，粉丝较多，喜欢转发和评论社会新闻；你会根据当前证据和互动判断是否传播。",
    "ordinary_student": "你是一名普通学生，偶尔刷社交媒体，看到感兴趣的内容会点赞，有时会转发给朋友。",
    "teacher": "你是一名高校教师，重视信息准确性，会核实信息来源，不轻易传播未经证实的消息。",
    "school_official": "你是学校官方账号，负责发布权威信息，会及时辟谣和澄清不实消息。",
    "media_observer": "你是一名媒体观察员，关注舆情动态，会分析信息传播路径，有时会撰写评论文章。",
    "anonymous_amplifier": "你是一个匿名账号，常参与争议话题并关注讨论热度；是否传播取决于当前认知状态。",
    "original_poster": "你是这条信息的首发者，会根据自己掌握的证据和互动反馈决定是否继续传播。",
    "repost_kol": "你是一名有影响力的大V，看到重要消息会迅速转发，你的转发会引发大量关注。",
    "ordinary_viewer": "你是普通网民，偶尔刷社交媒体，对感兴趣的内容会点赞，有时也会转发。",
    "fact_checker": "你是一名事实核查员，专门验证网络信息的真实性，发现谣言会及时辟谣。",
    "official_responder": "你是政府或权威机构的官方发言人，负责发布权威声明，澄清虚假信息。",
    "controversy_amplifier": "你是一个喜欢制造争议的账号，会夸大事实，引发情绪化讨论。",
    "victim": "你是诈骗受害者，正在经历一场紧张的诈骗过程，感到困惑和恐慌。",
    "attacker": "你是诈骗者，正在实施诈骗，试图让受害者相信你并按你的要求行动。",
    "family_member": "你是受害者的家人，担心家人的安全，试图联系和劝阻。",
    "platform_moderator": "你是平台审核员，负责监控违规内容，发现违规会及时处理。",
    "police_or_bank": "你是警方或银行工作人员，负责提醒用户注意防范诈骗。",
}
