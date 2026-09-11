"""Event-only claim fidelity model for lightweight propagation.

This module intentionally stays separate from ``narrative_model``.  Narrative
competition models public-opinion frames; this module models the fidelity of
canonical event claims as they travel through the existing actor graph.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


CLAIM_METRIC_SOURCE = "lightweight_claim_model"
CLAIM_METRIC_SEMANTICS = "simulation_proxy"
MATERIAL_DISTORTION_FLAGS = frozenset({
    "content_mutation",
    "source_loss",
    "context_loss",
    "certainty_inflation",
    "unsupported_extension",
    "causal_fabrication",
})
_BROADCAST_CLAIM_INTERVENTIONS = frozenset({"official_response", "clarification"})


def _clamp(value: Any, default: float = 0.5) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = default
    return max(0.0, min(1.0, number))


@dataclass(frozen=True)
class ClaimDynamicsConfig:
    """Centralized, explainable weights and thresholds for claim fidelity."""

    fidelity_content_weight: float = 0.40
    fidelity_source_weight: float = 0.20
    fidelity_context_weight: float = 0.20
    fidelity_evidence_weight: float = 0.20
    source_loss_threshold: float = 0.60
    unsupported_evidence_threshold: float = 0.45
    unsupported_certainty_threshold: float = 0.70
    certainty_inflation_flag_threshold: float = 0.15
    causal_certainty_threshold: float = 0.78


DEFAULT_CLAIM_CONFIG = ClaimDynamicsConfig()


@dataclass
class ClaimState:
    """Actor-local mutable state for one canonical claim."""

    claim_id: str
    canonical_text: str
    canonical_status: str = "reported"
    provenance: str = "inferred"
    evidence_refs: List[str] = field(default_factory=list)
    content_integrity: float = 1.0
    source_attribution: float = 1.0
    context_retention: float = 1.0
    certainty: float = 0.55
    evidential_support: float = 0.50
    mutation_count: int = 0
    generation: int = 0
    distortion_flags: List[str] = field(default_factory=list)
    origin_actor_id: Optional[str] = None
    last_source_actor_id: Optional[str] = None
    corrected: bool = False
    verified: bool = False

    def __post_init__(self) -> None:
        for name in (
            "content_integrity",
            "source_attribution",
            "context_retention",
            "certainty",
            "evidential_support",
        ):
            setattr(self, name, round(_clamp(getattr(self, name)), 6))
        self.mutation_count = max(0, int(self.mutation_count))
        self.generation = max(0, int(self.generation))
        self.evidence_refs = [str(item) for item in self.evidence_refs if item]
        self.distortion_flags = sorted({str(item) for item in self.distortion_flags if item})

    @property
    def fidelity(self) -> float:
        config = DEFAULT_CLAIM_CONFIG
        return round(_clamp(
            config.fidelity_content_weight * self.content_integrity
            + config.fidelity_source_weight * self.source_attribution
            + config.fidelity_context_weight * self.context_retention
            + config.fidelity_evidence_weight * self.evidential_support
        ), 6)

    @property
    def certainty_inflation(self) -> float:
        return round(max(0.0, self.certainty - self.evidential_support), 6)

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["fidelity"] = self.fidelity
        payload["certainty_inflation"] = self.certainty_inflation
        return payload


def _claim_value(claim: Any, key: str, default: Any = None) -> Any:
    if isinstance(claim, Mapping):
        return claim.get(key, default)
    return getattr(claim, key, default)


def normalize_claim_records(claims: Optional[Iterable[Any]], seed_text: str = "") -> List[Dict[str, Any]]:
    """Normalize CanonicalClaim objects without creating a second claim schema."""
    records: List[Dict[str, Any]] = []
    for index, claim in enumerate(claims or [], start=1):
        claim_id = str(_claim_value(claim, "claim_id", "") or f"CLAIM_{index:03d}")
        text = str(_claim_value(claim, "text", "") or seed_text or "event claim")
        records.append({
            "claim_id": claim_id,
            "text": text,
            "status": str(_claim_value(claim, "status", "reported") or "reported"),
            "provenance": str(_claim_value(claim, "provenance", "inferred") or "inferred"),
            "evidence_refs": [
                str(item) for item in (_claim_value(claim, "evidence_refs", []) or []) if item
            ],
        })
    if records:
        return records
    if seed_text:
        return [{
            "claim_id": "RUNTIME_CLAIM_001",
            "text": str(seed_text)[:500],
            "status": "reported",
            "provenance": "inferred",
            "evidence_refs": [],
            "runtime_fallback": True,
        }]
    return []


def _initial_state(record: Mapping[str, Any], origin_actor_id: str) -> ClaimState:
    status = str(record.get("status", "reported")).lower()
    provenance = str(record.get("provenance", "inferred"))
    evidence_refs = list(record.get("evidence_refs", []) or [])
    verified = status in {"verified", "confirmed", "fact"}
    if verified:
        support = 0.90
        certainty = 0.86
    elif provenance == "observed" and evidence_refs:
        support = 0.68
        certainty = 0.62
    elif evidence_refs:
        support = 0.52
        certainty = 0.56
    else:
        support = 0.35
        certainty = 0.48
    return ClaimState(
        claim_id=str(record["claim_id"]),
        canonical_text=str(record.get("text", "")),
        canonical_status=status,
        provenance=provenance,
        evidence_refs=evidence_refs,
        content_integrity=1.0,
        source_attribution=0.96 if evidence_refs else 0.62,
        context_retention=0.92 if evidence_refs else 0.76,
        certainty=certainty,
        evidential_support=support,
        origin_actor_id=origin_actor_id,
        verified=verified,
    )


def initialize_claim_states(
    claims: Optional[Iterable[Any]],
    seed_actor_ids: Sequence[str],
    *,
    seed_text: str = "",
) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, ClaimState]]]:
    """Create identical initial claim states for the initial active seeds."""
    records = normalize_claim_records(claims, seed_text=seed_text)
    actor_claim_states: Dict[str, Dict[str, ClaimState]] = {}
    for actor_id in seed_actor_ids:
        actor_key = str(actor_id)
        actor_claim_states[actor_key] = {
            record["claim_id"]: _initial_state(record, actor_key)
            for record in records
        }
    return records, actor_claim_states


def _actor_value(actor: Any, name: str, default: float = 0.5) -> float:
    return _clamp(getattr(actor, name, default), default)


def intervention_applies_to_actor(
    intervention: Optional[Mapping[str, Any]],
    actor_id: str,
) -> bool:
    """Return whether a Claim intervention directly targets one actor.

    Non-empty target lists are always strict.  An empty list retains the
    existing broadcast semantics only for official/clarification injections;
    other intervention types do not acquire implicit global scope.
    """
    intervention = intervention or {}
    intervention_type = str(intervention.get("intervention_type", ""))
    target_nodes = {
        str(item) for item in (intervention.get("target_nodes", []) or [])
    }
    if target_nodes:
        return str(actor_id) in target_nodes
    return intervention_type in _BROADCAST_CLAIM_INTERVENTIONS


def _refresh_flags(state: ClaimState, config: ClaimDynamicsConfig) -> None:
    flags = set()
    if state.content_integrity < 0.72:
        flags.add("content_mutation")
    if state.source_attribution < config.source_loss_threshold:
        flags.add("source_loss")
    if state.context_retention < 0.65:
        flags.add("context_loss")
    if state.certainty_inflation >= config.certainty_inflation_flag_threshold:
        flags.add("certainty_inflation")
    if (
        state.evidential_support < config.unsupported_evidence_threshold
        and state.certainty >= config.unsupported_certainty_threshold
    ):
        flags.add("unsupported_extension")
    if (
        "unsupported_extension" in flags
        and state.certainty >= config.causal_certainty_threshold
    ):
        flags.add("causal_fabrication")
    state.distortion_flags = sorted(flags)


def transmit_claim_states(
    source_actor: Any,
    target_actor: Any,
    source_states: Mapping[str, ClaimState],
    target_states: Dict[str, ClaimState],
    *,
    tick: int,
    source_id: str,
    target_id: str,
    exposure_count: int = 1,
    social_proof: float = 0.0,
    intervention: Optional[Mapping[str, Any]] = None,
    config: ClaimDynamicsConfig = DEFAULT_CLAIM_CONFIG,
) -> List[Dict[str, Any]]:
    """Transmit every source claim alongside one existing propagation action."""
    lineage: List[Dict[str, Any]] = []
    intervention = intervention or {}
    intervention_type = str(intervention.get("intervention_type", ""))
    social_proof = _clamp(social_proof)
    verification = _actor_value(target_actor, "verification_tendency")
    emotion = _actor_value(target_actor, "emotional_activation")
    confirmation = _actor_value(target_actor, "confirmation_bias")
    topic = _actor_value(target_actor, "topic_involvement")
    reactance = _actor_value(target_actor, "reactance")
    proof_sensitivity = _actor_value(target_actor, "social_proof_sensitivity")
    belief_strength = _actor_value(target_actor, "belief_strength")
    institutional_trust = _actor_value(target_actor, "institutional_trust")
    share_propensity = _actor_value(target_actor, "share_propensity")
    repeated_exposure = _clamp(max(0, int(exposure_count) - 1) / 5.0)
    for claim_id, source_state in sorted(source_states.items()):
        previous = target_states.get(claim_id)
        before = deepcopy(previous or source_state)
        state = deepcopy(previous or source_state)
        if previous is None:
            state.generation = max(state.generation, source_state.generation)
            state.mutation_count = max(state.mutation_count, source_state.mutation_count)
        else:
            incoming_corrective = bool(source_state.corrected or source_state.verified)
            state.content_integrity = min(previous.content_integrity, source_state.content_integrity)
            state.source_attribution = min(previous.source_attribution, source_state.source_attribution)
            state.context_retention = min(previous.context_retention, source_state.context_retention)
            # Repetition can raise subjective certainty, never evidential support.
            # A verified/corrected local state is retained when later traffic
            # comes from a less-evidenced source.  Repetition still cannot
            # create evidence for an unverified state.
            state.evidential_support = (
                max(previous.evidential_support, source_state.evidential_support)
                if incoming_corrective
                else previous.evidential_support
                if previous.verified or previous.corrected
                else min(previous.evidential_support, source_state.evidential_support)
            )
            state.certainty = max(previous.certainty, source_state.certainty)
            state.generation = max(previous.generation, source_state.generation)
            state.mutation_count = max(previous.mutation_count, source_state.mutation_count)
            state.corrected = bool(previous.corrected or source_state.corrected)
            state.verified = bool(previous.verified or source_state.verified)
        state.generation += 1
        state.mutation_count += 1
        state.last_source_actor_id = str(source_id)
        state.origin_actor_id = state.origin_actor_id or source_state.origin_actor_id

        content_loss = (
            0.012 + 0.035 * (1.0 - verification)
            + 0.025 * emotion + 0.018 * confirmation
            + 0.012 * (1.0 - topic)
            + 0.012 * share_propensity
        )
        source_loss = 0.012 + 0.085 * (1.0 - verification) + 0.030 * emotion
        context_loss = (
            0.015 + 0.070 * (1.0 - verification)
            + 0.075 * emotion + 0.030 * reactance
            + 0.015 * repeated_exposure
        )
        state.content_integrity = _clamp(state.content_integrity - content_loss)
        state.source_attribution = _clamp(state.source_attribution - source_loss)
        state.context_retention = _clamp(state.context_retention - context_loss)
        state.certainty = _clamp(
            state.certainty
            + 0.024 * emotion
            + 0.038 * social_proof * proof_sensitivity
            + 0.018 * repeated_exposure * proof_sensitivity
            + 0.030 * confirmation * (0.5 + 0.5 * belief_strength)
            - 0.035 * verification
        )
        # Evidential support is copied conservatively; repetition alone never
        # creates evidence.
        state.evidential_support = _clamp(state.evidential_support)

        target_is_targeted = intervention_applies_to_actor(intervention, target_id)
        claim_correction = False
        if intervention_type == "source_verification" and target_is_targeted:
            official_context = 0.6 + 0.4 * institutional_trust
            state.source_attribution = _clamp(state.source_attribution + 0.14 * verification * official_context)
            state.evidential_support = _clamp(state.evidential_support + 0.12 * verification * official_context)
            state.certainty = _clamp(state.certainty - 0.08 * verification * official_context)
            state.verified = True
        elif intervention_type in {"content_labeling", "community_note"} and target_is_targeted:
            official_context = 0.6 + 0.4 * institutional_trust
            state.context_retention = _clamp(state.context_retention + 0.14 * verification * official_context)
            state.source_attribution = _clamp(state.source_attribution + 0.05 * verification * official_context)
            state.certainty = _clamp(state.certainty - 0.06 * verification * official_context)
        elif intervention_type in {"official_response", "clarification", "debunking"} and target_is_targeted:
            official_context = 0.6 + 0.4 * institutional_trust
            state.source_attribution = _clamp(state.source_attribution + 0.08 * verification * official_context)
            state.evidential_support = _clamp(state.evidential_support + 0.10 * verification * official_context)
            state.certainty = _clamp(state.certainty - (0.12 if intervention_type != "debunking" else 0.18) * verification * official_context)
            state.verified = True
            state.corrected = True
            claim_correction = True

        _refresh_flags(state, config)
        target_states[claim_id] = state
        lineage.append({
            "claim_id": claim_id,
            "source_actor_id": str(source_id),
            "target_actor_id": str(target_id),
            "tick": int(tick),
            "generation": state.generation,
            "claim_fidelity_before": before.fidelity,
            "claim_fidelity_after": state.fidelity,
            "content_integrity": state.content_integrity,
            "source_attribution": state.source_attribution,
            "context_retention": state.context_retention,
            "certainty": state.certainty,
            "evidential_support": state.evidential_support,
            "certainty_inflation": state.certainty_inflation,
            "distortion_flags": list(state.distortion_flags),
            "corrected": bool(state.corrected or claim_correction),
            "verified": bool(state.verified),
        })
    return lineage


def _state_values(actor_claim_states: Mapping[str, Mapping[str, ClaimState]]) -> List[ClaimState]:
    return [state for claims in actor_claim_states.values() for state in claims.values()]


def build_claim_analysis(
    claim_records: Sequence[Mapping[str, Any]],
    actor_claim_states: Mapping[str, Mapping[str, ClaimState]],
    lineage: Sequence[Mapping[str, Any]],
    *,
    config: ClaimDynamicsConfig = DEFAULT_CLAIM_CONFIG,
) -> Dict[str, Any]:
    """Aggregate actor-local claim states and transmission lineage."""
    states = _state_values(actor_claim_states)
    reached_count = len(states)
    transmissions = list(lineage)
    fidelity_by_claim: Dict[str, float] = {}
    distortion_by_claim: Dict[str, Dict[str, Any]] = {}
    for claim in claim_records:
        claim_id = str(claim.get("claim_id"))
        claim_states = [
            state for claims in actor_claim_states.values()
            for state in claims.values() if state.claim_id == claim_id
        ]
        fidelity_by_claim[claim_id] = round(
            sum(state.fidelity for state in claim_states) / max(1, len(claim_states)), 6
        )
        flags = sorted({flag for state in claim_states for flag in state.distortion_flags})
        distortion_by_claim[claim_id] = {
            "fidelity": fidelity_by_claim[claim_id],
            "distortion_flags": flags,
            "actor_count": len(claim_states),
        }
    claim_fidelity = round(
        sum(state.fidelity for state in states) / max(1, reached_count), 6
    ) if states else 0.0
    distortion_rate = round(
        sum(bool(set(item.get("distortion_flags", [])) & MATERIAL_DISTORTION_FLAGS) for item in transmissions)
        / max(1, len(transmissions)),
        6,
    )
    source_loss_rate = round(
        sum(state.source_attribution < config.source_loss_threshold for state in states)
        / max(1, reached_count),
        6,
    )
    certainty_inflation = round(
        sum(state.certainty_inflation for state in states) / max(1, reached_count), 6
    ) if states else 0.0
    unsupported_claim_share = round(
        sum(
            "unsupported_extension" in state.distortion_flags
            or (
                state.evidential_support < config.unsupported_evidence_threshold
                and state.certainty >= config.unsupported_certainty_threshold
            )
            for state in states
        ) / max(1, reached_count),
        6,
    )
    verified_claim_reach = round(
        sum(state.verified for state in states) / max(1, reached_count), 6
    )
    correction_reach = round(
        sum(state.corrected and state.generation > 0 for state in states)
        / max(1, reached_count),
        6,
    )
    distortion_index = round(_clamp(
        0.35 * (1.0 - claim_fidelity)
        + 0.25 * distortion_rate
        + 0.15 * source_loss_rate
        + 0.15 * certainty_inflation
        + 0.10 * unsupported_claim_share
    ), 6)
    lineage_by_claim: Dict[str, int] = {}
    for item in transmissions:
        claim_id = str(item.get("claim_id", ""))
        lineage_by_claim[claim_id] = lineage_by_claim.get(claim_id, 0) + 1
    return {
        "supported": True,
        "claim_count": len(claim_records),
        "claim_fidelity": claim_fidelity,
        "claim_fidelity_by_claim": fidelity_by_claim,
        "distortion_index": distortion_index,
        "distortion_rate": distortion_rate,
        "distortion_by_claim": distortion_by_claim,
        "source_loss_rate": source_loss_rate,
        "certainty_inflation": certainty_inflation,
        "unsupported_claim_share": unsupported_claim_share,
        "verified_claim_reach": verified_claim_reach,
        "correction_reach": correction_reach,
        "claim_generation_depth": max((state.generation for state in states), default=0),
        "claim_lineage_summary": {
            "transmission_count": len(transmissions),
            "transmissions_by_claim": lineage_by_claim,
            "actor_claim_state_count": reached_count,
        },
        "claim_lineage": [dict(item) for item in transmissions],
        "actor_claim_states": {
            str(actor_id): {
                str(claim_id): state.to_dict()
                for claim_id, state in claims.items()
            }
            for actor_id, claims in actor_claim_states.items()
        },
        "metric_semantics": CLAIM_METRIC_SEMANTICS,
        "claim_metric_source": CLAIM_METRIC_SOURCE,
        "provenance": {
            "claim_model": CLAIM_METRIC_SOURCE,
            "canonical_claims_preserved": True,
            "reality_status": "stylized_simulation_proxy",
        },
    }


__all__ = [
    "CLAIM_METRIC_SEMANTICS",
    "CLAIM_METRIC_SOURCE",
    "ClaimDynamicsConfig",
    "ClaimState",
    "DEFAULT_CLAIM_CONFIG",
    "build_claim_analysis",
    "initialize_claim_states",
    "intervention_applies_to_actor",
    "normalize_claim_records",
    "transmit_claim_states",
]
