"""Actor-conditioned cognitive and social behaviour helpers.

This module deliberately stays small and dependency-free.  ``ActorState`` and
``PropagationAgent`` remain the canonical schemas; these helpers only provide
the shared initialization and update rules used by both lightweight
propagation and OASIS persona conditioning.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import random
from typing import Any, Dict, Mapping, Optional


MAX_STATE_HISTORY = 20
SOCIAL_PROOF_SATURATION = 4
COGNITIVE_PROFILE_DIMENSIONS = (
    "time_pressure", "financial_pressure", "info_asymmetry",
    "emotional_volatility", "cognitive_load", "authority_intensity",
    "authority_compliance", "social_proof_sensitivity",
    "scarcity_sensitivity", "loss_aversion_threshold", "gambler_fallacy",
    "trust_threshold", "decision_delay", "verification_habit", "help_seeking",
    "link_check_ability", "transaction_review", "prior_experience",
)


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(value)))


def _as_unit(value: Any, default: float = 0.5) -> float:
    """Read either a 0-1 value or the existing CognitiveProfile 0-10 scale."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if number > 1.0:
        number /= 10.0
    return _clamp(number)


def _profile_value(profile: Any, key: str, default: float = 0.5) -> float:
    if profile is None:
        return default
    if isinstance(profile, Mapping):
        return _as_unit(profile.get(key, default), default)
    return _as_unit(getattr(profile, key, default), default)


@dataclass(frozen=True)
class PropagationBehaviorConfig:
    """Centralized, explainable weights for lightweight sharing behaviour."""

    base_probability: float = 0.04
    source_influence_weight: float = 0.20
    target_susceptibility_weight: float = 0.16
    belief_alignment_weight: float = 0.14
    emotion_weight: float = 0.10
    social_proof_weight: float = 0.12
    topic_involvement_weight: float = 0.08
    share_propensity_weight: float = 0.08
    verification_penalty: float = 0.18
    learning_rate: float = 0.12
    trust_update_rate: float = 0.10
    social_proof_saturation: int = SOCIAL_PROOF_SATURATION
    max_history: int = MAX_STATE_HISTORY
    scenario_overrides: Dict[str, Dict[str, float]] = field(default_factory=lambda: {
        "public_opinion": {
            "emotion": 1.25,
            "social_proof": 1.25,
            "belief_alignment": 1.15,
            "verification": 0.85,
        },
        "event_propagation": {
            "verification": 1.35,
            "social_proof": 1.20,
            "belief_alignment": 1.05,
            "emotion": 0.90,
        },
        # FraudMultiRoleRuntime is intentionally separate.  These values only
        # keep the generic lightweight fallback backward-compatible if called.
        "fraud_im": {
            "verification": 1.0,
            "social_proof": 1.0,
            "belief_alignment": 1.0,
            "emotion": 1.0,
        },
    })


DEFAULT_BEHAVIOR_CONFIG = PropagationBehaviorConfig()


_SCENE_PRIORS: Dict[str, Dict[str, float]] = {
    "public_opinion": {
        "prior_belief": 0.50,
        "emotional_activation": 0.55,
        "institutional_trust": 0.50,
        "verification_tendency": 0.50,
        "topic_involvement": 0.55,
        "social_proof_sensitivity": 0.65,
    },
    "event_propagation": {
        "prior_belief": 0.50,
        "emotional_activation": 0.50,
        "institutional_trust": 0.45,
        "verification_tendency": 0.60,
        "topic_involvement": 0.50,
        "social_proof_sensitivity": 0.60,
    },
    "fraud_im": {
        "prior_belief": 0.50,
        "emotional_activation": 0.60,
        "institutional_trust": 0.50,
        "verification_tendency": 0.50,
        "topic_involvement": 0.60,
        "social_proof_sensitivity": 0.55,
    },
}


# These are tendencies, not deterministic role labels.  In particular, no
# role directly selects a stance; stance is derived after scene + actor state.
_ROLE_PRIORS: Dict[str, Dict[str, float]] = {
    "official": {"verification_tendency": 0.82, "institutional_trust": 0.72,
                 "share_propensity": 0.28, "emotional_activation": 0.32},
    "fact_checker": {"verification_tendency": 0.90, "confirmation_bias": 0.25,
                     "reactance": 0.25, "share_propensity": 0.38},
    "media": {"topic_involvement": 0.72, "verification_tendency": 0.68,
              "share_propensity": 0.68, "social_proof_sensitivity": 0.65},
    "kol": {"influence": 0.78, "activity": 0.75, "share_propensity": 0.78,
            "social_proof_sensitivity": 0.72},
    "directly_affected": {"topic_involvement": 0.86,
                          "emotional_activation": 0.76, "confirmation_bias": 0.62},
    "ordinary": {"verification_tendency": 0.50, "share_propensity": 0.50},
}


def _role_prior(role: str) -> Dict[str, float]:
    normalized = (role or "ordinary").lower()
    if any(token in normalized for token in ("official", "police", "bank", "moderator")):
        key = "official"
    elif "fact" in normalized or "checker" in normalized:
        key = "fact_checker"
    elif any(token in normalized for token in ("media", "reporter")):
        key = "media"
    elif any(token in normalized for token in ("kol", "amplifier", "poster")):
        key = "kol"
    elif any(token in normalized for token in ("victim", "affected")):
        key = "directly_affected"
    else:
        key = "ordinary"
    return _ROLE_PRIORS[key]


def build_scene_cognitive_prior(
    scene_profile: Any = None,
    *,
    scenario_type: str = "",
    scenario_text: str = "",
) -> Dict[str, Any]:
    """Create a scene prior without copying it as every actor's final state."""
    prior = dict(_SCENE_PRIORS.get(scenario_type, _SCENE_PRIORS["public_opinion"]))
    profile_keys = (
        "emotional_activation", "institutional_trust", "verification_tendency",
        "topic_involvement", "social_proof_sensitivity", "prior_belief",
    )
    for key in profile_keys:
        if scene_profile is not None:
            aliases = {
                "institutional_trust": "authority_compliance",
                "verification_tendency": "verification_habit",
                "social_proof_sensitivity": "social_proof_sensitivity",
                "emotional_activation": "emotional_volatility",
            }
            alias = aliases.get(key, key)
            if isinstance(scene_profile, Mapping):
                raw = scene_profile.get(key, scene_profile.get(alias, prior[key]))
            else:
                raw = getattr(scene_profile, key, getattr(scene_profile, alias, prior[key]))
            prior[key] = _as_unit(raw, prior[key])

    # Keep the complete 18D input attached to S0 and let every dimension
    # contribute to at least one behaviour-relevant scene prior.  The full
    # vector is retained for audit/persona conditioning; actors still receive
    # role-conditioned copies below rather than one identical profile.
    if scene_profile is not None:
        dimensions = {
            key: _profile_value(scene_profile, key)
            for key in COGNITIVE_PROFILE_DIMENSIONS
        }
        prior["profile_dimensions"] = dimensions
        prior["emotional_activation"] = _clamp(
            0.44 * prior["emotional_activation"]
            + 0.12 * dimensions["time_pressure"]
            + 0.16 * dimensions["emotional_volatility"]
            + 0.08 * dimensions["financial_pressure"]
            + 0.06 * dimensions["info_asymmetry"]
            + 0.06 * dimensions["cognitive_load"]
            + 0.04 * dimensions["scarcity_sensitivity"]
            + 0.04 * dimensions["loss_aversion_threshold"]
        )
        prior["institutional_trust"] = _clamp(
            0.40 * prior["institutional_trust"]
            + 0.10 * dimensions["authority_intensity"]
            + 0.12 * dimensions["authority_compliance"]
            + 0.12 * dimensions["trust_threshold"]
            + 0.06 * dimensions["prior_experience"]
            + 0.05 * dimensions["help_seeking"]
            + 0.05 * dimensions["social_proof_sensitivity"]
            + 0.05 * dimensions["decision_delay"]
            + 0.03 * dimensions["link_check_ability"]
            + 0.02 * dimensions["transaction_review"]
        )
        prior["verification_tendency"] = _clamp(
            0.30 * prior["verification_tendency"]
            + 0.15 * dimensions["verification_habit"]
            + 0.12 * dimensions["link_check_ability"]
            + 0.10 * dimensions["transaction_review"]
            + 0.08 * dimensions["prior_experience"]
            + 0.08 * dimensions["help_seeking"]
            + 0.05 * dimensions["decision_delay"]
            + 0.04 * dimensions["cognitive_load"]
            + 0.04 * dimensions["info_asymmetry"]
            + 0.02 * dimensions["authority_intensity"]
            + 0.02 * dimensions["trust_threshold"]
        )
        prior["topic_involvement"] = _clamp(
            0.35 * prior["topic_involvement"]
            + 0.12 * dimensions["info_asymmetry"]
            + 0.10 * dimensions["financial_pressure"]
            + 0.10 * dimensions["loss_aversion_threshold"]
            + 0.08 * dimensions["help_seeking"]
            + 0.06 * dimensions["prior_experience"]
            + 0.05 * dimensions["emotional_volatility"]
            + 0.05 * dimensions["gambler_fallacy"]
            + 0.09 * dimensions["scarcity_sensitivity"]
        )
        prior["social_proof_sensitivity"] = _clamp(
            0.35 * prior["social_proof_sensitivity"]
            + 0.18 * dimensions["social_proof_sensitivity"]
            + 0.10 * dimensions["scarcity_sensitivity"]
            + 0.10 * dimensions["gambler_fallacy"]
            + 0.08 * dimensions["authority_compliance"]
            + 0.08 * dimensions["trust_threshold"]
            + 0.05 * dimensions["loss_aversion_threshold"]
            + 0.04 * dimensions["info_asymmetry"]
            + 0.02 * dimensions["emotional_volatility"]
        )
        prior["prior_belief"] = _clamp(
            0.50 * prior["prior_belief"]
            + 0.10 * dimensions["authority_intensity"]
            + 0.10 * dimensions["trust_threshold"]
            + 0.10 * dimensions["social_proof_sensitivity"]
            + 0.05 * dimensions["loss_aversion_threshold"]
            + 0.05 * dimensions["gambler_fallacy"]
            + 0.05 * dimensions["prior_experience"]
            + 0.05 * dimensions["verification_habit"]
        )

    text = (scenario_text or "").lower()
    if any(word in text for word in ("紧张", "恐慌", "焦虑", "愤怒", "危险", "威胁")):
        prior["emotional_activation"] += 0.12
    if any(word in text for word in ("求证", "核实", "事实核查", "辟谣")):
        prior["verification_tendency"] += 0.10
    if any(word in text for word in ("质疑", "不信", "失信", "不透明")):
        prior["institutional_trust"] -= 0.10
    if any(word in text for word in ("官方", "权威", "公告")):
        prior["institutional_trust"] += 0.04
    if any(word in text for word in ("大家都", "群里都", "很多人", "朋友也")):
        prior["social_proof_sensitivity"] += 0.10

    return {
        key: (value if key == "profile_dimensions" else round(_clamp(value), 4))
        for key, value in prior.items()
    }


def build_actor_cognitive_state(
    scene_profile: Any,
    role: str,
    actor_metadata: Optional[Mapping[str, Any]] = None,
    rng: Optional[random.Random] = None,
) -> Dict[str, Any]:
    """Transform scene prior + role tendencies into one actor-specific state."""
    metadata = dict(actor_metadata or {})
    rng = rng or random.Random(0)
    if isinstance(scene_profile, Mapping):
        scene = dict(scene_profile)
    else:
        scene = build_scene_cognitive_prior(scene_profile)
    role_prior = _role_prior(role)

    def value(key: str, scene_key: Optional[str] = None, noise: float = 0.04) -> float:
        explicit = metadata.get(key)
        if explicit is not None:
            return _clamp(_as_unit(explicit))
        scene_value = float(scene.get(scene_key or key, 0.5))
        role_value = role_prior.get(key, scene_value)
        return _clamp(0.62 * scene_value + 0.33 * role_value + rng.uniform(-noise, noise))

    prior_belief = _clamp(_as_unit(metadata.get(
        "prior_belief", metadata.get("belief", scene.get("prior_belief", 0.5))
    )) + rng.uniform(-0.05, 0.05))
    institutional_trust = value("institutional_trust", noise=0.035)
    topic_involvement = value("topic_involvement", noise=0.045)
    verification = value("verification_tendency", noise=0.035)
    confirmation_bias = value("confirmation_bias", noise=0.04)
    social_proof = value("social_proof_sensitivity", noise=0.04)
    reactance = value("reactance", noise=0.04)
    emotional = value("emotional_activation", noise=0.045)
    activity = _as_unit(metadata.get("activity", 0.5))
    share_propensity = value("share_propensity", noise=0.045)

    # Stance is a consequence of the state.  The small noise term is only
    # heterogeneity; it is not the primary source of actor differences.
    stance = derive_stance_from_actor_state({
        "belief_strength": prior_belief,
        "institutional_trust": institutional_trust,
        "topic_involvement": topic_involvement,
        "emotional_activation": emotional,
        "verification_tendency": verification,
        "confirmation_bias": confirmation_bias,
        "share_propensity": share_propensity,
    }, noise=rng.uniform(-0.025, 0.025))

    return {
        "prior_belief": round(prior_belief, 4),
        "belief_strength": round(prior_belief, 4),
        "topic_involvement": round(topic_involvement, 4),
        "institutional_trust": round(institutional_trust, 4),
        "verification_tendency": round(verification, 4),
        "confirmation_bias": round(confirmation_bias, 4),
        "social_proof_sensitivity": round(social_proof, 4),
        "reactance": round(reactance, 4),
        "emotional_activation": round(emotional, 4),
        "share_propensity": round(share_propensity, 4),
        "stance": stance,
        "exposure_count": 0,
        "last_exposure_tick": None,
        "belief_history": [],
        "trust_history": [],
        "exposure_history": [],
        "activity": round(activity, 4),
    }


def apply_actor_cognitive_state(actor: Any, state: Mapping[str, Any]) -> Any:
    """Apply a state mapping to either ActorState or PropagationAgent."""
    for key, value in state.items():
        if key == "institutional_trust":
            setattr(actor, key, _clamp(value))
            setattr(actor, "trust_in_official", _clamp(value))
        elif hasattr(actor, key):
            setattr(actor, key, value)
    return actor


def assign_communities(
    actors: list[Any],
    scenario_type: str,
    seed: int = 42,
    community_count: Optional[int] = None,
) -> list[Any]:
    """Assign communities from affinity features, not role buckets."""
    if not actors:
        return actors
    rng = random.Random(seed)
    count = community_count or max(2, min(4, (len(actors) + 3) // 4))
    for index, actor in enumerate(actors):
        stance_values = {
            "skeptical": 0.15, "neutral": 0.40, "supportive": 0.60,
            "corrective": 0.70, "amplifying": 0.85,
        }
        stance_value = stance_values.get(getattr(actor, "stance", "neutral"), 0.5)
        belief = _as_unit(getattr(actor, "prior_belief", 0.5))
        topic = _as_unit(getattr(actor, "topic_involvement", 0.5))
        # Role contributes only a weak stable perturbation.  Stance, topic and
        # seeded jitter dominate, allowing mixed-role communities and splitting
        # same-role actors with different states.
        role_text = str(getattr(actor, "role", "ordinary"))
        role_signal = sum(ord(char) for char in role_text) % 11 / 100.0
        jitter = rng.randrange(count) / max(1, count * 5)
        affinity = 0.46 * stance_value + 0.34 * belief + 0.20 * topic + role_signal + jitter
        cluster = int(affinity * 17 + index * 0.37) % count
        actor.community_id = f"{scenario_type}_cluster_{cluster}"

    # Keep the low-risk assignment useful even for tiny deterministic fixtures:
    # repeated same-role actors may split, and if all initial clusters happen
    # to be role-pure, place one actor with a different role in an existing
    # cluster.  These are safeguards, not the primary grouping rule.
    role_groups: Dict[str, list[Any]] = {}
    for actor in actors:
        role_groups.setdefault(str(getattr(actor, "role", "ordinary")), []).append(actor)
    for group in role_groups.values():
        if len(group) > 1 and len({item.community_id for item in group}) == 1:
            current = group[-1].community_id.rsplit("_", 1)[-1]
            next_cluster = (int(current) + 1) % count
            group[-1].community_id = f"{scenario_type}_cluster_{next_cluster}"
    if len(role_groups) > 1:
        community_roles: Dict[str, set[str]] = {}
        for actor in actors:
            community_roles.setdefault(actor.community_id, set()).add(str(actor.role))
        if not any(len(roles) > 1 for roles in community_roles.values()):
            first, second = actors[0], actors[1]
            second.community_id = first.community_id
    return actors


def social_proof_from_exposure(
    exposure_count: int,
    saturation: int = SOCIAL_PROOF_SATURATION,
) -> float:
    """Return bounded repeated-exposure social proof with saturation."""
    return _clamp(max(0, int(exposure_count)) / max(1, int(saturation)))


def register_exposure(
    actor: Any,
    *,
    tick: int,
    source_id: str = "",
    content_ref: str = "",
    max_history: int = MAX_STATE_HISTORY,
) -> int:
    """Record an encounter independently from whether the actor shares."""
    actor.exposure_count = max(0, int(getattr(actor, "exposure_count", 0))) + 1
    actor.last_exposure_tick = tick
    history = list(getattr(actor, "exposure_history", []) or [])
    history.append({
        "tick": tick,
        "exposure_count": actor.exposure_count,
        "source_id": source_id,
        "content_ref": content_ref,
    })
    actor.exposure_history = history[-max_history:]
    return actor.exposure_count


def _content_signal(content_state: Any, source: Any = None) -> float:
    if isinstance(content_state, Mapping):
        for key in ("belief_signal", "claim_signal", "information_signal"):
            if key in content_state:
                return _clamp(_as_unit(content_state[key]))
        stance = content_state.get("stance")
    else:
        stance = getattr(content_state, "stance", None)
    if stance is None and source is not None:
        stance = getattr(source, "stance", None)
    return {
        "skeptical": 0.20,
        "corrective": 0.25,
        "neutral": 0.50,
        "supportive": 0.70,
        "amplifying": 0.82,
    }.get(str(stance), 0.50)


def _scenario_factor(config: PropagationBehaviorConfig, scenario: str, key: str) -> float:
    return float(config.scenario_overrides.get(scenario, {}).get(key, 1.0))


def compute_share_probability(
    source: Any,
    target: Any,
    content_state: Any = None,
    scene_state: Any = None,
    exposure_context: Any = None,
    config: PropagationBehaviorConfig = DEFAULT_BEHAVIOR_CONFIG,
) -> float:
    """Compute a bounded, interpretable share probability."""
    scene = scene_state if isinstance(scene_state, Mapping) else {}
    context = exposure_context if isinstance(exposure_context, Mapping) else {}
    scenario = str(scene.get("scenario_type", context.get("scenario_type", "")))
    exposure_count = int(context.get("exposure_count", getattr(target, "exposure_count", 0)))
    social_proof = social_proof_from_exposure(exposure_count, config.social_proof_saturation)
    social_proof_effect = social_proof * _as_unit(
        getattr(target, "social_proof_sensitivity", 0.5)
    )
    signal = _content_signal(content_state, source)
    current_belief = _clamp(getattr(target, "belief_strength", getattr(target, "prior_belief", 0.5)))
    belief_alignment = 1.0 - abs(current_belief - signal)
    scene_emotion = _as_unit(scene.get("emotional_activation", 0.0), 0.0)
    emotion = _clamp(0.65 * _as_unit(getattr(target, "emotional_activation", 0.5)) + 0.35 * scene_emotion)
    source_credibility = _as_unit(context.get(
        "source_credibility",
        0.55 * getattr(source, "influence", 0.5)
        + 0.45 * getattr(source, "institutional_trust", getattr(source, "trust_in_official", 0.5)),
    ))
    weights = config
    probability = (
        weights.base_probability
        + weights.source_influence_weight * _as_unit(getattr(source, "influence", 0.5))
        + weights.target_susceptibility_weight * _as_unit(getattr(target, "susceptibility", 0.5))
        + weights.belief_alignment_weight * belief_alignment * _scenario_factor(config, scenario, "belief_alignment")
        + weights.emotion_weight * emotion * _scenario_factor(config, scenario, "emotion")
        + weights.social_proof_weight * social_proof_effect * _scenario_factor(config, scenario, "social_proof")
        + weights.topic_involvement_weight * _as_unit(getattr(target, "topic_involvement", 0.5))
        + weights.share_propensity_weight * _as_unit(getattr(target, "share_propensity", 0.5))
        - weights.verification_penalty * _as_unit(getattr(target, "verification_tendency", 0.5)) * _scenario_factor(config, scenario, "verification")
    )
    return round(_clamp(probability), 6)


def update_belief_after_exposure(
    target: Any,
    source: Any = None,
    content_state: Any = None,
    scene_state: Any = None,
    *,
    tick: int,
    verified: bool = False,
    config: PropagationBehaviorConfig = DEFAULT_BEHAVIOR_CONFIG,
) -> float:
    """Apply one small confirmation-biased belief update and record history."""
    current = _clamp(getattr(target, "belief_strength", getattr(target, "prior_belief", 0.5)))
    signal = _content_signal(content_state, source)
    alignment = 1.0 - abs(current - signal)
    confirmation_bias = _as_unit(getattr(target, "confirmation_bias", 0.5))
    verification = _as_unit(getattr(target, "verification_tendency", 0.5))
    source_credibility = _as_unit(
        (content_state or {}).get("source_credibility", 0.5)
        if isinstance(content_state, Mapping)
        else 0.5
    )
    confirmation_factor = 1.0 + confirmation_bias * (0.55 if alignment >= 0.5 else -0.55)
    verification_factor = 1.0 if verified else max(0.15, 1.0 - 0.55 * verification)
    signal_strength = max(0.20, abs(signal - 0.5) * 2.0)
    magnitude = (
        config.learning_rate
        * max(0.25, source_credibility)
        * (0.35 + 0.65 * alignment)
        * max(0.15, confirmation_factor)
        * verification_factor
        * signal_strength
    )
    if abs(signal - current) < 1e-9:
        direction = 1.0 if signal >= 0.5 else -1.0
    else:
        direction = 1.0 if signal > current else -1.0
    new_value = _clamp(current + direction * magnitude)
    target.belief_strength = round(new_value, 6)
    target.stance = derive_stance_from_actor_state(target)
    history = list(getattr(target, "belief_history", []) or [])
    history.append({
        "tick": tick,
        "belief_strength": target.belief_strength,
        "delta": round(target.belief_strength - current, 6),
        "alignment_factor": round(alignment, 4),
        "verified": verified,
        "trigger": "verified_exposure" if verified else "exposure",
    })
    target.belief_history = history[-config.max_history:]
    return target.belief_strength


def derive_stance_from_actor_state(actor: Any, noise: float = 0.0) -> str:
    """Derive stance from the current multi-dimensional actor state."""
    if isinstance(actor, Mapping):
        get = actor.get
    else:
        get = lambda key, default=0.5: getattr(actor, key, default)
    score = (
        0.36 * _as_unit(get("belief_strength", get("prior_belief", 0.5)))
        + 0.16 * _as_unit(get("institutional_trust", get("trust_in_official", 0.5)))
        + 0.12 * _as_unit(get("topic_involvement", 0.5))
        + 0.12 * _as_unit(get("emotional_activation", 0.5))
        + 0.10 * (1.0 - _as_unit(get("verification_tendency", 0.5)))
        + 0.08 * _as_unit(get("confirmation_bias", 0.5))
        + 0.06 * _as_unit(get("share_propensity", 0.5))
        + noise
    )
    verification = _as_unit(get("verification_tendency", 0.5))
    trust = _as_unit(get("institutional_trust", get("trust_in_official", 0.5)))
    emotion = _as_unit(get("emotional_activation", 0.5))
    if verification > 0.78 and trust > 0.55 and emotion < 0.68:
        return "corrective"
    if score >= 0.68:
        return "amplifying"
    if score >= 0.54:
        return "supportive"
    if score <= 0.31:
        return "skeptical"
    return "neutral"


def update_institutional_trust(
    actor: Any,
    *,
    tick: int,
    verified: bool = False,
    source_role: str = "official_responder",
    information_signal: Optional[float] = None,
    config: PropagationBehaviorConfig = DEFAULT_BEHAVIOR_CONFIG,
) -> float:
    """Apply only an explicit verified-official trust trigger."""
    current = _clamp(getattr(actor, "institutional_trust", getattr(actor, "trust_in_official", 0.5)))
    if not verified or source_role not in {"official_responder", "school_official", "police_or_bank"}:
        return current
    signal = _clamp(information_signal if information_signal is not None else current)
    alignment = 1.0 - abs(_clamp(getattr(actor, "belief_strength", 0.5)) - signal)
    reactance = _as_unit(getattr(actor, "reactance", 0.5))
    verification = _as_unit(getattr(actor, "verification_tendency", 0.5))
    delta = (
        config.trust_update_rate
        * (0.35 + 0.65 * current)
        * (1.0 - 0.70 * reactance)
        * (0.45 + 0.55 * verification)
        * (0.50 + 0.50 * alignment)
    )
    new_value = _clamp(current + delta)
    actor.institutional_trust = round(new_value, 6)
    actor.trust_in_official = actor.institutional_trust
    actor.stance = derive_stance_from_actor_state(actor)
    history = list(getattr(actor, "trust_history", []) or [])
    history.append({
        "tick": tick,
        "institutional_trust": actor.institutional_trust,
        "delta": round(actor.institutional_trust - current, 6),
        "trigger": "official_verified_clarification",
        "source_role": source_role,
    })
    actor.trust_history = history[-config.max_history:]
    return actor.institutional_trust


def state_band(value: Any) -> str:
    number = _as_unit(value)
    if number < 0.34:
        return "low"
    if number < 0.67:
        return "medium"
    return "high"


def actor_state_persona_summary(actor: Any) -> str:
    """Compact, actor-specific conditioning for an OASIS/social agent.

    Cognitive state controls the decision threshold; a stable actor-id hash
    controls communication style.  This avoids giving every actor the same
    stock sentence while keeping runs reproducible.
    """
    actor_id = str(getattr(actor, "agent_id", getattr(actor, "actor_id", "actor")))
    digest = hashlib.sha256(actor_id.encode("utf-8")).digest()
    styles = (
        "先给事实再给判断，短句，不使用口号",
        "以提问和核验请求为主，避免替别人下结论",
        "先说明自身经历或立场，再指出仍不确定的部分",
        "偏好引用来源、时间和上下文，少做情绪化评价",
        "表达简短直接，但必须区分已知事实与个人推测",
        "只有在能补充新信息时才发言，平时更倾向观察",
    )
    cadences = ("一句话", "两句以内", "要点式", "问答式")
    verification = state_band(getattr(actor, "verification_tendency", 0.5))
    evidence_rule = {
        "low": "容易受社交证明影响，但遇到强提醒时会停下来确认",
        "medium": "至少看到一个可追溯来源才会强化或转发判断",
        "high": "没有原始来源或交叉核验时，优先质疑或保持沉默",
    }[verification]
    return (
        "actor-state-conditioned persona initialization: "
        f"institutional trust {state_band(getattr(actor, 'institutional_trust', getattr(actor, 'trust_in_official', 0.5)))}, "
        f"confirmation bias {state_band(getattr(actor, 'confirmation_bias', 0.5))}, "
        f"verification tendency {state_band(getattr(actor, 'verification_tendency', 0.5))}, "
        f"topic involvement {state_band(getattr(actor, 'topic_involvement', 0.5))}, "
        f"social-proof sensitivity {state_band(getattr(actor, 'social_proof_sensitivity', 0.5))}, "
        f"current stance {getattr(actor, 'stance', 'neutral')}. "
        f"个人表达习惯：{styles[digest[0] % len(styles)]}；常用篇幅：{cadences[digest[1] % len(cadences)]}。"
        f"决策规范：{evidence_rule}。没有新的事实、来源、经历或问题时选择不发帖；"
        "不要重复上一轮的原句，也不要统一使用‘理性吃瓜’、‘等待官方’等套话。"
    )


__all__ = [
    "COGNITIVE_PROFILE_DIMENSIONS",
    "DEFAULT_BEHAVIOR_CONFIG",
    "MAX_STATE_HISTORY",
    "PropagationBehaviorConfig",
    "SOCIAL_PROOF_SATURATION",
    "actor_state_persona_summary",
    "apply_actor_cognitive_state",
    "assign_communities",
    "build_actor_cognitive_state",
    "build_scene_cognitive_prior",
    "compute_share_probability",
    "derive_stance_from_actor_state",
    "register_exposure",
    "social_proof_from_exposure",
    "state_band",
    "update_belief_after_exposure",
    "update_institutional_trust",
]
