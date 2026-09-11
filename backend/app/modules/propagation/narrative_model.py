"""Lightweight public-opinion narrative competition model.

This module models interpretations of one canonical event.  It deliberately
does not create actors or edges: callers must provide the canonical S0 actors
and adjacency.  The model is public-opinion-only and is intentionally small,
deterministic, and provenance-aware so it can sit beside the legacy
propagation metrics without changing event or fraud semantics.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass, field
import math
import re
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

from ..social_state.behavior import (
    derive_stance_from_actor_state,
    social_proof_from_exposure,
)


NARRATIVE_MODEL_VERSION = "narrative_competition_v1"
VALID_NARRATIVE_PROVENANCE = frozenset({"observed", "inferred", "synthetic"})


def _clamp(value: Any, default: float = 0.5) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = default
    return max(0.0, min(1.0, number))


@dataclass(frozen=True)
class NarrativeDynamicsConfig:
    """Centralized knobs for explainable narrative dynamics."""

    max_narratives: int = 4
    learning_rate: float = 0.12
    competition_strength: float = 0.32
    social_proof_saturation: int = 4
    adopted_threshold: float = 0.65
    rejected_threshold: float = 0.25
    switch_margin: float = 0.08
    idle_share_threshold: float = 0.16
    max_history: int = 20


DEFAULT_NARRATIVE_CONFIG = NarrativeDynamicsConfig()


@dataclass
class NarrativeState:
    narrative_id: str
    label: str
    summary: str
    stance_direction: str
    source_claim_ids: List[str] = field(default_factory=list)
    provenance: str = "inferred"
    credibility: float = 0.5
    emotional_intensity: float = 0.5
    institutional_alignment: float = 0.5
    novelty: float = 0.5
    current_share: float = 0.0
    adoption_count: int = 0
    rejection_count: int = 0
    active: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.provenance not in VALID_NARRATIVE_PROVENANCE:
            raise ValueError(f"Invalid narrative provenance: {self.provenance}")
        for name in (
            "credibility", "emotional_intensity", "institutional_alignment",
            "novelty", "current_share",
        ):
            setattr(self, name, round(_clamp(getattr(self, name)), 6))
        self.adoption_count = max(0, int(self.adoption_count))
        self.rejection_count = max(0, int(self.rejection_count))

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "NarrativeState":
        known = {
            key: value for key, value in dict(payload).items()
            if key in cls.__dataclass_fields__
        }
        return cls(**known)


@dataclass(frozen=True)
class NarrativeRelation:
    narrative_a: str
    narrative_b: str
    relation: str = "orthogonal"  # supports | competes | orthogonal
    strength: float = 0.0

    def __post_init__(self) -> None:
        if self.relation not in {"supports", "competes", "orthogonal"}:
            raise ValueError(f"Invalid narrative relation: {self.relation}")
        object.__setattr__(self, "strength", round(_clamp(self.strength, 0.0), 6))

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


_FRAME_RULES: Sequence[tuple[str, str, str, tuple[str, ...]]] = (
    ("institutional_concealment", "institutional concealment concern", "skeptical", ("隐瞒", "掩盖", "不透明", "压下", "不公开")),
    ("rumor_exaggeration", "rumor exaggeration concern", "skeptical", ("夸大", "炒作", "断章取义", "谣言", "网传失实")),
    ("governance_procedure", "governance procedure concern", "neutral", ("治理程序", "程序不透明", "处理流程", "问责机制")),
    ("official_correction", "official evidence and correction", "corrective", ("辟谣", "澄清", "更正", "官方声明", "权威回应", "调查结果")),
    ("uncertainty_wait_evidence", "uncertainty and wait-for-evidence", "neutral", ("证据不足", "尚不清楚", "原因未知", "等待证据", "待核实", "无法确认")),
)


def _as_text(value: Any) -> str:
    return str(value or "").strip()


def _claim_value(item: Any, key: str, default: Any = None) -> Any:
    if isinstance(item, Mapping):
        return item.get(key, default)
    return getattr(item, key, default)


def _case_value(case: Any, key: str, default: Any = None) -> Any:
    if isinstance(case, Mapping):
        return case.get(key, default)
    return getattr(case, key, default)


def _unique_text(items: Iterable[str]) -> List[str]:
    result: List[str] = []
    seen: set[str] = set()
    for item in items:
        value = " ".join(_as_text(item).split())
        if value and value not in seen:
            result.append(value)
            seen.add(value)
    return result


def _split_source_text(text: str) -> List[str]:
    return _unique_text(re.split(r"[\n。！？；;，,]+", text or ""))


def _frame_for_text(text: str) -> Optional[tuple[str, str, str]]:
    lowered = text.lower()
    for direction, label, stance, tokens in _FRAME_RULES:
        if any(token.lower() in lowered for token in tokens):
            return direction, label, stance
    return None


def _candidate_from_text(
    *,
    text: str,
    source_claim_ids: Optional[List[str]] = None,
    provenance: str = "observed",
    evidence_state: str = "unclear",
    evidence_spans: Optional[List[str]] = None,
    index: int = 1,
) -> Optional[NarrativeState]:
    clean = _as_text(text)
    if not clean:
        return None
    frame = _frame_for_text(clean)
    if frame is None:
        direction, label, stance = (
            "reported_claim_concern",
            "reported claim and public concern",
            "neutral",
        )
    else:
        direction, label, stance = frame

    state_score = {
        "confirmed": 0.78,
        "unverified": 0.38,
        "contested": 0.48,
        "unclear": 0.52,
    }.get(_as_text(evidence_state).lower(), 0.52)
    if any(token in clean for token in ("愤怒", "恐慌", "焦虑", "危险", "震惊", "夸大")):
        intensity = 0.82
    elif frame and frame[0] in {"institutional_concealment", "rumor_exaggeration"}:
        intensity = 0.68
    else:
        intensity = 0.34
    alignment = 0.82 if stance == "corrective" else 0.26 if direction == "institutional_concealment" else 0.42
    if direction == "uncertainty_wait_evidence":
        alignment = 0.52
    if provenance not in VALID_NARRATIVE_PROVENANCE:
        provenance = "inferred"

    metadata: Dict[str, Any] = {"grounding": "exact_source_text" if evidence_spans else "source_claim_or_clause"}
    if evidence_spans:
        metadata["evidence_spans"] = _unique_text(evidence_spans)
    return NarrativeState(
        narrative_id=f"NARRATIVE_{index:03d}",
        label=label,
        summary=f"对材料中“{clean[:180]}”的解释框架",
        stance_direction=direction,
        source_claim_ids=list(source_claim_ids or []),
        provenance=provenance,
        credibility=state_score,
        emotional_intensity=intensity,
        institutional_alignment=alignment,
        novelty=0.55 if provenance == "observed" else 0.75,
        metadata=metadata,
    )


def _candidate_key(state: NarrativeState) -> str:
    return f"{state.stance_direction}|{state.label}"


def extract_public_opinion_narratives(
    canonical_case: Any,
    max_narratives: int = DEFAULT_NARRATIVE_CONFIG.max_narratives,
) -> List[NarrativeState]:
    """Extract a stable, bounded narrative set from a CanonicalCase.

    Canonical claims and evidence are the only observed inputs.  Synthetic
    entries are used only for counterfactual uncertainty or corrective context.
    """
    limit = max(2, min(5, int(max_narratives or DEFAULT_NARRATIVE_CONFIG.max_narratives)))
    summary = _as_text(_case_value(canonical_case, "summary", ""))
    claims = list(_case_value(canonical_case, "claims", []) or [])
    evidence_items = list(_case_value(canonical_case, "evidence_items", []) or [])
    source_texts = [_as_text(_claim_value(item, "content", "")) for item in evidence_items]
    source_texts = [text for text in source_texts if text]
    full_text = "\n".join(source_texts) or summary
    claim_ids = {
        _as_text(_claim_value(item, "claim_id", "")): _as_text(_claim_value(item, "text", ""))
        for item in claims
    }

    candidates: List[NarrativeState] = []
    seen: set[str] = set()

    # Canonical claims are the preferred observed/inferred source.
    for claim_id, claim_text in claim_ids.items():
        state = _candidate_from_text(
            text=claim_text,
            source_claim_ids=[claim_id],
            provenance="observed" if claim_text and claim_text in full_text else "inferred",
            index=len(candidates) + 1,
        )
        if state and _candidate_key(state) not in seen:
            candidates.append(state)
            seen.add(_candidate_key(state))

    # Rich input can contain multiple posts/statements even when the generic
    # claim extractor produced only one claim.
    for clause in _split_source_text(full_text):
        state = _candidate_from_text(
            text=clause,
            provenance="observed",
            index=len(candidates) + 1,
        )
        if state and _candidate_key(state) not in seen and _frame_for_text(clause):
            candidates.append(state)
            seen.add(_candidate_key(state))
        if len(candidates) >= limit:
            break

    # Keep a generic interpretation grounded in the source if the input is
    # sparse and no explicit frame was found.
    if not candidates and full_text:
        state = _candidate_from_text(
            text=_split_source_text(full_text)[0] if _split_source_text(full_text) else full_text[:180],
            provenance="inferred",
            index=1,
        )
        if state:
            candidates.append(state)
            seen.add(_candidate_key(state))

    # A wait-for-evidence frame is a safe fallback interpretation, not a fact.
    if len(candidates) < 2:
        candidates.append(NarrativeState(
            narrative_id=f"NARRATIVE_{len(candidates) + 1:03d}",
            label="uncertainty and wait-for-evidence",
            summary="对当前材料保持不确定，等待更多可核验信息",
            stance_direction="uncertainty_wait_evidence",
            provenance="synthetic" if full_text else "inferred",
            credibility=0.58,
            emotional_intensity=0.24,
            institutional_alignment=0.52,
            novelty=0.88,
            metadata={"counterfactual_only": True, "grounding": "no_new_fact"},
        ))

    # Add at most one source-grounded procedural frame before synthetic ones
    # when rich material explicitly discusses governance or transparency.
    if len(candidates) < limit:
        for clause in _split_source_text(full_text):
            state = _candidate_from_text(
                text=clause,
                provenance="observed",
                index=len(candidates) + 1,
            )
            if state and state.stance_direction == "governance_procedure" and _candidate_key(state) not in seen:
                candidates.append(state)
                seen.add(_candidate_key(state))
                break

    candidates = candidates[:limit]
    for index, state in enumerate(candidates, start=1):
        state.narrative_id = f"NARRATIVE_{index:03d}"
    return candidates


def build_narrative_relations(narratives: Sequence[NarrativeState]) -> List[NarrativeRelation]:
    relations: List[NarrativeRelation] = []
    for index, left in enumerate(narratives):
        for right in narratives[index + 1:]:
            left_dir = left.stance_direction
            right_dir = right.stance_direction
            competing_pairs = {
                frozenset({"institutional_concealment", "official_correction"}),
                frozenset({"institutional_concealment", "rumor_exaggeration"}),
                frozenset({"rumor_exaggeration", "official_correction"}),
            }
            relation = "competes" if frozenset({left_dir, right_dir}) in competing_pairs else "orthogonal"
            strength = 0.68 if relation == "competes" else 0.12
            relations.append(NarrativeRelation(left.narrative_id, right.narrative_id, relation, strength))
    return relations


def _narrative_direction_signal(narrative: NarrativeState, actor: Any) -> float:
    trust = _clamp(getattr(actor, "institutional_trust", getattr(actor, "trust_in_official", 0.5)))
    verification = _clamp(getattr(actor, "verification_tendency", 0.5))
    involvement = _clamp(getattr(actor, "topic_involvement", 0.5))
    direction = narrative.stance_direction
    if direction in {"institutional_concealment", "rumor_exaggeration"}:
        return 0.28 + 0.56 * (1.0 - trust)
    if direction in {"official_correction", "governance_procedure"}:
        return 0.28 + 0.56 * trust
    if direction == "uncertainty_wait_evidence":
        return 0.30 + 0.42 * verification + 0.14 * (1.0 - involvement)
    return 0.30 + 0.28 * _clamp(getattr(actor, "prior_belief", 0.5))


def compute_narrative_affinity(
    actor: Any,
    narrative: NarrativeState,
    scene_state: Optional[Mapping[str, Any]] = None,
) -> float:
    """Return actor × narrative affinity in [0, 1]."""
    scene = scene_state if isinstance(scene_state, Mapping) else {}
    prior = _clamp(getattr(actor, "prior_belief", 0.5))
    trust = _clamp(getattr(actor, "institutional_trust", getattr(actor, "trust_in_official", 0.5)))
    bias = _clamp(getattr(actor, "confirmation_bias", 0.5))
    verification = _clamp(getattr(actor, "verification_tendency", 0.5))
    involvement = _clamp(getattr(actor, "topic_involvement", 0.5))
    emotion = _clamp(getattr(actor, "emotional_activation", scene.get("emotional_activation", 0.5)))
    direction_signal = _narrative_direction_signal(narrative, actor)
    belief_match = 1.0 - abs(prior - direction_signal)
    credibility = _clamp(narrative.credibility)
    emotion_match = 0.55 + 0.45 * (emotion if narrative.emotional_intensity >= 0.6 else 1.0 - emotion)
    trust_alignment = 1.0 - abs(trust - narrative.institutional_alignment)
    verification_match = (
        verification if narrative.stance_direction == "uncertainty_wait_evidence"
        else 1.0 - verification * (1.0 - credibility)
    )
    stance = str(getattr(actor, "stance", "neutral"))
    if narrative.stance_direction in {"institutional_concealment", "rumor_exaggeration"}:
        stance_match = {"skeptical": 0.82, "amplifying": 0.78, "supportive": 0.58}.get(stance, 0.48)
    elif narrative.stance_direction == "official_correction":
        stance_match = {"corrective": 0.84, "supportive": 0.76, "skeptical": 0.36}.get(stance, 0.50)
    elif narrative.stance_direction == "uncertainty_wait_evidence":
        stance_match = {"neutral": 0.82, "skeptical": 0.68, "corrective": 0.62}.get(stance, 0.50)
    else:
        stance_match = 0.55
    affinity = (
        0.15 * direction_signal
        + 0.17 * belief_match
        + 0.15 * trust_alignment
        + 0.14 * credibility
        + 0.12 * involvement
        + 0.09 * emotion_match
        + 0.08 * bias
        + 0.05 * verification_match
        + 0.05 * stance_match
    )
    return round(_clamp(affinity), 6)


def narrative_share_probability(
    actor: Any,
    narrative: NarrativeState,
    *,
    social_proof: float = 0.0,
    share_multiplier: Optional[float] = None,
) -> float:
    """Compute P_share(N) without changing belief directly."""
    if share_multiplier is None:
        metadata = getattr(actor, "metadata", {})
        share_multiplier = (
            metadata.get("narrative_share_multiplier", 1.0)
            if isinstance(metadata, Mapping) else 1.0
        )
    beliefs = getattr(actor, "narrative_beliefs", {}) or {}
    belief = _clamp(beliefs.get(narrative.narrative_id, getattr(actor, "belief_strength", 0.5)))
    emotion = _clamp(getattr(actor, "emotional_activation", 0.5))
    topic = _clamp(getattr(actor, "topic_involvement", 0.5))
    propensity = _clamp(getattr(actor, "share_propensity", getattr(actor, "activity", 0.5)))
    verification = _clamp(getattr(actor, "verification_tendency", 0.5))
    probability = (
        0.05
        + 0.42 * belief
        + 0.16 * narrative.emotional_intensity * emotion
        + 0.13 * topic
        + 0.12 * propensity
        + 0.08 * _clamp(social_proof)
        - 0.14 * verification * (1.0 - narrative.credibility)
    )
    multiplier = _clamp(share_multiplier, 1.0)
    return round(_clamp(probability * multiplier), 6)


def actor_knows_narrative(actor: Any, narrative_id: str) -> bool:
    """Return whether an actor has an explicit exposure/adoption signal."""
    exposure = getattr(actor, "narrative_exposure_count", {}) or {}
    if int(exposure.get(narrative_id, 0) or 0) > 0:
        return True
    adoption = getattr(actor, "narrative_adoption_state", {}) or {}
    return adoption.get(narrative_id, "unaware") != "unaware"


def select_active_narrative(
    actor: Any,
    available_narratives: Sequence[NarrativeState],
    *,
    config: NarrativeDynamicsConfig = DEFAULT_NARRATIVE_CONFIG,
) -> Optional[NarrativeState]:
    """Select at most one narrative for a share decision; idle is allowed."""
    # Latent affinity is not knowledge.  An actor can only publish a frame
    # after explicit exposure, except where a caller explicitly seeded or
    # injected that exposure through register_narrative_exposure().
    active = [
        item for item in available_narratives
        if item.active and actor_knows_narrative(actor, item.narrative_id)
    ]
    if not active:
        return None
    proof_map = getattr(actor, "narrative_exposure_count", {}) or {}
    metadata = getattr(actor, "metadata", {})
    share_multiplier = _clamp(metadata.get("narrative_share_multiplier", 1.0), 1.0) if isinstance(metadata, Mapping) else 1.0
    ranked = sorted(
        active,
        key=lambda item: narrative_share_probability(
            actor,
            item,
            social_proof=social_proof_from_exposure(
                int(proof_map.get(item.narrative_id, 0)),
                config.social_proof_saturation,
            ),
            share_multiplier=share_multiplier,
        ),
        reverse=True,
    )
    best = ranked[0]
    best_probability = narrative_share_probability(
        actor,
        best,
        social_proof=social_proof_from_exposure(
            int(proof_map.get(best.narrative_id, 0)),
            config.social_proof_saturation,
        ),
        share_multiplier=share_multiplier,
    )
    return best if best_probability >= config.idle_share_threshold else None


def _ensure_actor_narrative_maps(actor: Any) -> None:
    if not isinstance(getattr(actor, "narrative_beliefs", None), dict):
        actor.narrative_beliefs = {}
    if not isinstance(getattr(actor, "narrative_exposure_count", None), dict):
        actor.narrative_exposure_count = {}
    if not isinstance(getattr(actor, "narrative_adoption_state", None), dict):
        actor.narrative_adoption_state = {}


def initialize_actor_narratives(
    actors: Sequence[Any],
    narratives: Sequence[NarrativeState],
    *,
    scene_state: Optional[Mapping[str, Any]] = None,
) -> None:
    for actor in actors:
        _ensure_actor_narrative_maps(actor)
        for narrative in narratives:
            if not narrative.active:
                continue
            if narrative.narrative_id not in actor.narrative_beliefs:
                actor.narrative_beliefs[narrative.narrative_id] = compute_narrative_affinity(actor, narrative, scene_state)
            actor.narrative_exposure_count.setdefault(narrative.narrative_id, 0)
            actor.narrative_adoption_state.setdefault(narrative.narrative_id, "unaware")


def register_narrative_exposure(
    actor: Any,
    narrative_id: str,
    *,
    tick: int,
    source_id: str = "",
    content_ref: str = "",
) -> int:
    _ensure_actor_narrative_maps(actor)
    count = max(0, int(actor.narrative_exposure_count.get(narrative_id, 0))) + 1
    actor.narrative_exposure_count[narrative_id] = count
    return count


def narrative_adoption_state(
    actor: Any,
    narrative_id: str,
    config: NarrativeDynamicsConfig = DEFAULT_NARRATIVE_CONFIG,
) -> str:
    _ensure_actor_narrative_maps(actor)
    belief = _clamp(actor.narrative_beliefs.get(narrative_id, 0.0))
    exposure = int(actor.narrative_exposure_count.get(narrative_id, 0))
    # Belief is intentionally latent until the narrative is known.  This
    # prevents initialization affinity from becoming a synthetic adoption.
    if exposure <= 0:
        state = "unaware"
    elif belief >= config.adopted_threshold:
        state = "adopted"
    elif belief <= config.rejected_threshold and exposure > 0:
        state = "rejected"
    elif exposure > 0:
        state = "exposed" if belief < 0.5 else "considering"
    else:
        state = "unaware"
    actor.narrative_adoption_state[narrative_id] = state
    return state


def update_narrative_belief_after_exposure(
    actor: Any,
    narrative: NarrativeState,
    *,
    source_credibility: float = 0.5,
    social_proof: float = 0.0,
    topic_involvement: Optional[float] = None,
    emotional_activation: Optional[float] = None,
    confirmation_bias: Optional[float] = None,
    verification_tendency: Optional[float] = None,
    tick: int = 0,
    verified: bool = False,
    relations: Sequence[NarrativeRelation] = (),
    config: NarrativeDynamicsConfig = DEFAULT_NARRATIVE_CONFIG,
) -> float:
    """Update one narrative belief and apply small competition penalties."""
    _ensure_actor_narrative_maps(actor)
    current = _clamp(actor.narrative_beliefs.get(narrative.narrative_id, compute_narrative_affinity(actor, narrative)))
    affinity = compute_narrative_affinity(actor, narrative)
    credibility = _clamp(source_credibility)
    topic = _clamp(topic_involvement if topic_involvement is not None else getattr(actor, "topic_involvement", 0.5))
    emotion = _clamp(emotional_activation if emotional_activation is not None else getattr(actor, "emotional_activation", 0.5))
    bias = _clamp(confirmation_bias if confirmation_bias is not None else getattr(actor, "confirmation_bias", 0.5))
    verification = _clamp(verification_tendency if verification_tendency is not None else getattr(actor, "verification_tendency", 0.5))
    signal = _clamp(0.48 * credibility + 0.34 * affinity + 0.10 * narrative.novelty + 0.08 * narrative.emotional_intensity)
    alignment = 1.0 - abs(current - affinity)
    confirmation_factor = 1.0 + bias * (0.42 if alignment >= 0.5 else -0.32)
    verification_factor = 1.0 if verified else max(0.22, 1.0 - 0.48 * verification * (1.0 - credibility))
    social_factor = 0.45 + 0.55 * social_proof_from_exposure(int(round(_clamp(social_proof) * config.social_proof_saturation)), config.social_proof_saturation)
    magnitude = (
        config.learning_rate
        * max(0.25, credibility)
        * (0.35 + 0.65 * alignment)
        * (0.45 + 0.55 * topic)
        * (0.50 + 0.50 * emotion)
        * max(0.20, confirmation_factor)
        * verification_factor
        * social_factor
    )
    new_value = _clamp(current + (signal - current) * magnitude)
    delta = new_value - current
    actor.narrative_beliefs[narrative.narrative_id] = round(new_value, 6)

    # Competing interpretations can coexist; competition only nudges the
    # counterpart and never applies a probability-conserving softmax.
    current_narrative_id = narrative.narrative_id
    for relation in relations:
        if relation.relation != "competes" or current_narrative_id not in {relation.narrative_a, relation.narrative_b}:
            continue
        other_id = (
            relation.narrative_b
            if current_narrative_id == relation.narrative_a
            else relation.narrative_a
        )
        other = _clamp(actor.narrative_beliefs.get(other_id, 0.5))
        actor.narrative_beliefs[other_id] = round(_clamp(other - max(0.0, delta) * relation.strength * config.competition_strength), 6)

    narrative_adoption_state(actor, narrative.narrative_id, config)
    # The full narrative set is supplied by the simulator at tick boundaries;
    # deriving the legacy stance here keeps scalar state bounded without
    # counting a temporary single-narrative view as a real switch.
    actor.stance = derive_stance_from_actor_state(actor)
    history = list(getattr(actor, "narrative_belief_history", []) or [])
    history.append({
        "tick": tick,
        "narrative_id": narrative.narrative_id,
        "belief": actor.narrative_beliefs[narrative.narrative_id],
        "delta": round(delta, 6),
        "social_proof": round(_clamp(social_proof), 4),
        "verified": bool(verified),
    })
    actor.narrative_belief_history = history[-config.max_history:]
    return actor.narrative_beliefs[narrative.narrative_id]


def refresh_actor_public_stance(actor: Any, narratives: Sequence[NarrativeState]) -> str:
    """Keep legacy stance aligned with the current dominant narrative state."""
    _ensure_actor_narrative_maps(actor)
    active = [item for item in narratives if item.active]
    if active:
        dominant = max(active, key=lambda item: _clamp(actor.narrative_beliefs.get(item.narrative_id, 0.0)))
        dominant_id = dominant.narrative_id
        previous = getattr(actor, "dominant_narrative_id", None)
        if previous and previous != dominant_id:
            actor.narrative_switch_count = max(0, int(getattr(actor, "narrative_switch_count", 0))) + 1
        actor.dominant_narrative_id = dominant_id
        actor.current_narrative_id = dominant_id
        actor.narrative_adoption_state[dominant_id] = narrative_adoption_state(actor, dominant_id)
    beliefs = list(actor.narrative_beliefs.values())
    if beliefs:
        aggregate = sum(beliefs) / len(beliefs)
        dominant_belief = _clamp(actor.narrative_beliefs.get(getattr(actor, "dominant_narrative_id", ""), aggregate))
        actor.belief_strength = round(_clamp(0.65 * dominant_belief + 0.35 * aggregate), 6)
    actor.stance = derive_stance_from_actor_state(actor)
    return actor.stance


def update_narrative_adoption_counts(actors: Sequence[Any], narratives: Sequence[NarrativeState], config: NarrativeDynamicsConfig = DEFAULT_NARRATIVE_CONFIG) -> None:
    for narrative in narratives:
        adoption = 0
        rejection = 0
        for actor in actors:
            state = narrative_adoption_state(actor, narrative.narrative_id, config)
            adoption += state == "adopted"
            rejection += state == "rejected"
        narrative.adoption_count = adoption
        narrative.rejection_count = rejection


def _distribution(actors: Sequence[Any], narratives: Sequence[NarrativeState]) -> tuple[Dict[str, float], Dict[str, str]]:
    active = [item for item in narratives if item.active]
    counts: Dict[str, int] = {item.narrative_id: 0 for item in active}
    dominant_by_actor: Dict[str, str] = {}
    aware_count = 0
    for actor in actors:
        if not active:
            continue
        known = [item for item in active if actor_knows_narrative(actor, item.narrative_id)]
        if not known:
            continue
        beliefs = getattr(actor, "narrative_beliefs", {}) or {}
        dominant = max(known, key=lambda item: _clamp(beliefs.get(item.narrative_id, 0.0)) if isinstance(beliefs, Mapping) else 0.0)
        counts[dominant.narrative_id] = counts.get(dominant.narrative_id, 0) + 1
        dominant_by_actor[str(getattr(actor, "agent_id", getattr(actor, "actor_id", id(actor))))] = dominant.narrative_id
        aware_count += 1
    # Narrative share is normalized over actors who know at least one active
    # narrative; unaware population is reported separately by the metrics.
    total = max(1, aware_count)
    return {key: round(value / total, 6) for key, value in counts.items()}, dominant_by_actor


def _aware_actor_count(actors: Sequence[Any], narratives: Sequence[NarrativeState]) -> int:
    active = [item for item in narratives if item.active]
    return sum(
        1
        for actor in actors
        if any(actor_knows_narrative(actor, item.narrative_id) for item in active)
    )


def _entropy(distribution: Mapping[str, float]) -> float:
    values = [value for value in distribution.values() if value > 0.0]
    if len(values) <= 1:
        return 0.0
    value = -sum(prob * math.log(prob) for prob in values)
    return round(value / math.log(len(distribution)), 6) if len(distribution) > 1 else 0.0


def compute_narrative_metrics(
    actors: Sequence[Any],
    narratives: Sequence[NarrativeState],
    *,
    relations: Sequence[NarrativeRelation] = (),
    narrative_share_history: Optional[List[Dict[str, Any]]] = None,
    config: NarrativeDynamicsConfig = DEFAULT_NARRATIVE_CONFIG,
) -> Dict[str, Any]:
    """Return bounded global/community narrative competition metrics."""
    update_narrative_adoption_counts(actors, narratives, config)
    distribution, dominant_by_actor = _distribution(actors, narratives)
    aware_actor_count = _aware_actor_count(actors, narratives)
    unaware_share = round(1.0 - aware_actor_count / max(1, len(actors)), 6)
    for narrative in narratives:
        narrative.current_share = distribution.get(narrative.narrative_id, 0.0)

    communities: Dict[str, List[Any]] = defaultdict(list)
    for actor in actors:
        community = str(getattr(actor, "community_id", "") or "community_unassigned")
        communities[community].append(actor)
    community_distribution: Dict[str, Dict[str, float]] = {}
    for community, members in sorted(communities.items()):
        community_distribution[community], _ = _distribution(members, narratives)

    community_values = list(community_distribution.values())
    distances: List[float] = []
    for index, left in enumerate(community_values):
        for right in community_values[index + 1:]:
            keys = set(left) | set(right)
            distances.append(0.5 * sum(abs(left.get(key, 0.0) - right.get(key, 0.0)) for key in keys))
    fragmentation = round(sum(distances) / len(distances), 6) if distances else 0.0
    scores = {
        "skeptical": 0.0,
        "neutral": 0.5,
        "supportive": 0.72,
        "corrective": 0.86,
        "amplifying": 1.0,
    }
    stance_values = [scores.get(str(getattr(actor, "stance", "neutral")), 0.5) for actor in actors]
    stance_mean = sum(stance_values) / len(stance_values) if stance_values else 0.5
    stance_extremity = sum(abs(value - 0.5) * 2.0 for value in stance_values) / len(stance_values) if stance_values else 0.0
    stance_polarization = round(min(1.0, 4.0 * sum((value - stance_mean) ** 2 for value in stance_values) / max(1, len(stance_values))), 6)
    switch_count = sum(max(0, int(getattr(actor, "narrative_switch_count", 0))) for actor in actors)
    switching_actors = sum(1 for actor in actors if int(getattr(actor, "narrative_switch_count", 0) or 0) > 0)
    switch_rate = round(switching_actors / max(1, len(actors)), 6)
    max_share = max(distribution.values(), default=0.0)
    narrative_polarization = round(_clamp(0.35 * (1.0 - max_share) + 0.35 * fragmentation + 0.30 * (0.5 * stance_polarization + 0.5 * stance_extremity)), 6)
    dominant_id = max(distribution, key=distribution.get) if aware_actor_count and distribution else None
    return {
        "narrative_share": distribution,
        "narrative_share_semantics": "share among narrative-aware/adopting actors",
        "narrative_share_denominator": "narrative-aware actors",
        "aware_actor_count": aware_actor_count,
        "unaware_share": unaware_share,
        "narrative_entropy": _entropy(distribution),
        "dominant_narrative": dominant_id,
        "community_narrative_distribution": community_distribution,
        "community_fragmentation": fragmentation,
        "stance_polarization": stance_polarization,
        "cross_community_disagreement": fragmentation,
        "narrative_switch_count": switch_count,
        "narrative_switch_rate": switch_rate,
        "narrative_polarization": narrative_polarization,
        "metric_semantics": "simulation_proxy",
        "narrative_share_history": list(narrative_share_history or []),
        "dominant_narrative_by_actor": dominant_by_actor,
        "narrative_count": len([item for item in narratives if item.active]),
        "relation_count": len(list(relations)),
    }


def build_narrative_analysis(
    actors: Sequence[Any],
    narratives: Sequence[NarrativeState],
    *,
    relations: Sequence[NarrativeRelation] = (),
    narrative_share_history: Optional[List[Dict[str, Any]]] = None,
    model_provenance: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    metrics = compute_narrative_metrics(
        actors,
        narratives,
        relations=relations,
        narrative_share_history=narrative_share_history,
    )
    # Keep the regular response compact: actor-level matrices stay in the
    # trace/debug payload, while this summary exposes only top narratives and
    # community differences.
    compact_metrics = {key: value for key, value in metrics.items() if key != "dominant_narrative_by_actor"}
    return {
        "model_version": NARRATIVE_MODEL_VERSION,
        "narratives": [item.to_dict() for item in narratives[:5]],
        "relations": [item.to_dict() for item in relations],
        **compact_metrics,
        "provenance": {
            "public_opinion_model": NARRATIVE_MODEL_VERSION,
            "narrative_state_model": "lightweight",
            "actor_state_conditioned": True,
            "community_conditioned": True,
            "shared_initial_world": True,
            "metric_semantics": "simulation_proxy",
            "narrative_provenance_counts": {
                "observed": sum(1 for item in narratives if item.provenance == "observed"),
                "inferred": sum(1 for item in narratives if item.provenance == "inferred"),
                "synthetic": sum(1 for item in narratives if item.provenance == "synthetic"),
            },
            **dict(model_provenance or {}),
        },
    }


def add_counterfactual_narrative(narratives: List[NarrativeState], kind: str) -> NarrativeState:
    """Introduce an intervention narrative without rewriting observed input."""
    if kind == "official_response":
        narrative_id, label, direction, summary = "N_OFFICIAL", "official evidence and corrective response", "official_correction", "干预提供权威证据状态与纠正性回应"
        credibility, intensity, alignment = 0.76, 0.22, 0.88
    else:
        narrative_id, label, direction, summary = "N_CORRECTIVE", "verified context and corrective note", "official_correction", "干预提供核验上下文与纠正性说明"
        credibility, intensity, alignment = 0.68, 0.28, 0.78
    for item in narratives:
        if item.narrative_id == narrative_id:
            item.active = True
            return item
    state = NarrativeState(
        narrative_id=narrative_id,
        label=label,
        summary=summary,
        stance_direction=direction,
        provenance="synthetic",
        credibility=credibility,
        emotional_intensity=intensity,
        institutional_alignment=alignment,
        novelty=0.35,
        metadata={"counterfactual_only": True, "introduced_by": kind},
    )
    narratives.append(state)
    return state


def apply_narrative_intervention(
    agents: Sequence[Any],
    narratives: List[NarrativeState],
    *,
    intervention_type: str,
    tick: int,
    target_ids: Optional[Iterable[str]] = None,
    config: NarrativeDynamicsConfig = DEFAULT_NARRATIVE_CONFIG,
) -> Dict[str, Any]:
    """Apply differentiated intervention semantics to the lightweight model."""
    target_set = {str(item) for item in (target_ids or []) if item}
    touched: List[str] = []
    if intervention_type in {"official_response", "official_clarification"}:
        corrective = add_counterfactual_narrative(narratives, "official_response")
        initialize_actor_narratives(agents, [corrective])
        for actor in agents:
            register_narrative_exposure(actor, corrective.narrative_id, tick=tick, content_ref="official_response")
            update_narrative_belief_after_exposure(
                actor,
                corrective,
                source_credibility=corrective.credibility,
                social_proof=0.25,
                verified=True,
                tick=tick,
                relations=build_narrative_relations(narratives),
                config=config,
            )
            touched.append(str(getattr(actor, "agent_id", "")))
        return {"introduced_narrative_id": corrective.narrative_id, "touched_agents": touched, "belief_rewrite": "actor_conditioned_exposure"}

    if intervention_type in {"clarification", "debunking", "community_note", "source_verification"}:
        corrective = add_counterfactual_narrative(narratives, "corrective_context")
        initialize_actor_narratives(agents, [corrective])
        target = target_set or {str(getattr(actor, "agent_id", "")) for actor in agents}
        for actor in agents:
            actor_id = str(getattr(actor, "agent_id", ""))
            if actor_id not in target and intervention_type != "clarification":
                continue
            register_narrative_exposure(actor, corrective.narrative_id, tick=tick, content_ref=intervention_type)
            if intervention_type != "community_note":
                update_narrative_belief_after_exposure(
                    actor,
                    corrective,
                    source_credibility=corrective.credibility,
                    social_proof=0.18,
                    verified=intervention_type in {"clarification", "source_verification"},
                    tick=tick,
                    relations=build_narrative_relations(narratives),
                    config=config,
                )
            touched.append(actor_id)
        if intervention_type == "debunking":
            target_narrative = max(
                (item for item in narratives if item.active and item.narrative_id not in {corrective.narrative_id}),
                key=lambda item: item.emotional_intensity * (1.0 - item.credibility),
                default=None,
            )
            if target_narrative is not None:
                target_narrative.credibility = round(_clamp(target_narrative.credibility - 0.15), 6)
        return {"introduced_narrative_id": corrective.narrative_id, "touched_agents": touched, "belief_rewrite": "none_for_community_note" if intervention_type == "community_note" else "targeted_exposure"}

    if intervention_type == "friction_prompt":
        for actor in agents:
            metadata = getattr(actor, "metadata", None)
            if isinstance(metadata, dict):
                metadata["narrative_share_multiplier"] = 0.62
            touched.append(str(getattr(actor, "agent_id", "")))
        return {"touched_agents": touched, "belief_rewrite": "none", "mechanism": "share_probability_only"}

    if intervention_type == "downranking":
        for actor in agents:
            actor_id = str(getattr(actor, "agent_id", ""))
            if target_set and actor_id not in target_set:
                continue
            metadata = getattr(actor, "metadata", None)
            if isinstance(metadata, dict):
                metadata["narrative_outbound_reach_multiplier"] = 0.45
            touched.append(actor_id)
        return {"touched_agents": touched, "belief_rewrite": "none", "mechanism": "source_outbound_reach_only"}

    return {"touched_agents": touched, "belief_rewrite": "none"}


__all__ = [
    "DEFAULT_NARRATIVE_CONFIG",
    "NARRATIVE_MODEL_VERSION",
    "NarrativeDynamicsConfig",
    "NarrativeRelation",
    "NarrativeState",
    "add_counterfactual_narrative",
    "apply_narrative_intervention",
    "build_narrative_analysis",
    "build_narrative_relations",
    "compute_narrative_affinity",
    "compute_narrative_metrics",
    "extract_public_opinion_narratives",
    "actor_knows_narrative",
    "initialize_actor_narratives",
    "narrative_adoption_state",
    "narrative_share_probability",
    "select_active_narrative",
    "refresh_actor_public_stance",
    "register_narrative_exposure",
    "update_narrative_adoption_counts",
    "update_narrative_belief_after_exposure",
]
