"""Lightweight propagation simulator — tick-based, no external dependencies."""

from __future__ import annotations

import random as _random
import uuid
from copy import deepcopy
from typing import Any, Dict, List, Optional, Sequence

from .fork_strategies import (
    NoInterventionFork,
    OfficialClarificationFork,
    PropagationForkStrategy,
    RemoveKeyNodeFork,
)
from .claim_model import (
    ClaimDynamicsConfig,
    DEFAULT_CLAIM_CONFIG,
    build_claim_analysis,
    initialize_claim_states,
    transmit_claim_states,
)
from .metrics import compute_key_nodes, summarize_trace
from .narrative_model import (
    NarrativeDynamicsConfig,
    NarrativeRelation,
    NarrativeState,
    apply_narrative_intervention,
    build_narrative_analysis,
    build_narrative_relations,
    initialize_actor_narratives,
    narrative_adoption_state,
    narrative_share_probability,
    refresh_actor_public_stance,
    register_narrative_exposure,
    select_active_narrative,
    update_narrative_belief_after_exposure,
)
from .schema import (
    ForkedPropagationResult,
    PropagationAction,
    PropagationAgent,
    PropagationEvent,
    PropagationTrace,
)
from ..social_state.behavior import (
    compute_share_probability,
    register_exposure,
    social_proof_from_exposure,
    update_belief_after_exposure,
)

_RISK_FACTORS: Dict[str, float] = {
    "fraud_im": 0.75,
    "public_opinion": 0.65,
    "event_propagation": 0.70,
}
_DEFAULT_RISK = 0.60


def run_propagation_simulation(
    event: PropagationEvent,
    agents: list[PropagationAgent],
    adjacency: dict[str, list[str]],
    ticks: int = 30,
    seed: int = 42,
    fork_strategy: PropagationForkStrategy | None = None,
    narratives: Optional[list[NarrativeState | dict]] = None,
    narrative_relations: Optional[list[NarrativeRelation | dict]] = None,
    narrative_config: NarrativeDynamicsConfig | None = None,
    claims: Optional[Sequence[Any]] = None,
    claim_config: ClaimDynamicsConfig | None = None,
) -> PropagationTrace:
    """Run a single tick-based propagation simulation."""
    rng = _random.Random(seed)
    # Branch callers may reuse the same initial list.  Keeping runtime state
    # local makes A/B initial conditions equivalent and prevents hidden mutation
    # through repeated exposure/history fields.
    agents = deepcopy(agents)
    adjacency = deepcopy(adjacency)
    scenario = event.scenario_type
    risk_factor = _RISK_FACTORS.get(scenario, _DEFAULT_RISK)

    narrative_enabled = scenario == "public_opinion" and bool(narratives)
    claim_enabled = scenario == "event_propagation"
    narrative_config = narrative_config or NarrativeDynamicsConfig()
    claim_config = claim_config or DEFAULT_CLAIM_CONFIG
    narrative_states: list[NarrativeState] = []
    if narrative_enabled:
        narrative_states = [
            item if isinstance(item, NarrativeState) else NarrativeState.from_dict(item)
            for item in (narratives or [])
        ]
    relations: list[NarrativeRelation] = []
    if narrative_enabled:
        relations = [
            item if isinstance(item, NarrativeRelation) else NarrativeRelation(**item)
            for item in (narrative_relations or build_narrative_relations(narrative_states))
        ]

    id_to_agent = {a.agent_id: a for a in agents}

    if narrative_enabled:
        initialize_actor_narratives(
            agents,
            narrative_states,
            scene_state={
                "scenario_type": scenario,
                "emotional_activation": _event_emotion_value(event.initial_emotion),
            },
        )

    # initial seeds: top 1-3 influence agents
    sorted_by_inf = sorted(agents, key=lambda a: a.influence, reverse=True)
    seed_count = min(3, max(1, len(agents) // 20))
    if narrative_enabled:
        initial_narratives = [item for item in narrative_states if item.active]
        for index, seed_actor in enumerate(sorted_by_inf[:seed_count]):
            if not initial_narratives:
                break
            seed_narrative = initial_narratives[index % len(initial_narratives)]
            # Seed publication is an explicit knowledge exception, recorded
            # as exposure so the normal knowledge gate remains meaningful.
            register_narrative_exposure(
                seed_actor,
                seed_narrative.narrative_id,
                tick=0,
                source_id="seed",
                content_ref=event.event_id,
            )
            narrative_adoption_state(seed_actor, seed_narrative.narrative_id, narrative_config)
    # ``covered`` means activated/spread at least once.  It is intentionally
    # separate from each actor's exposure_count.
    covered: set[str] = {a.agent_id for a in sorted_by_inf[:seed_count]}
    active: set[str] = set(covered)
    initial_active: set[str] = set(active)

    claim_records = []
    actor_claim_states = {}
    claim_lineage = []
    if claim_enabled:
        claim_records, actor_claim_states = initialize_claim_states(
            claims,
            [actor.agent_id for actor in sorted_by_inf[:seed_count]],
            seed_text=event.seed_text,
        )

    actions: list[PropagationAction] = []
    coverage_curve: list[dict] = []
    emotion_curve: list[dict] = []
    narrative_share_history: list[dict] = []

    for tick in range(ticks + 1):
        active_claim_intervention: Dict[str, Any] = {}
        # apply fork strategy
        if fork_strategy is not None and fork_strategy.should_apply(tick):
            agents, adjacency, _ = fork_strategy.apply(agents, adjacency, compute_key_nodes(agents, adjacency, actions))
            id_to_agent = {a.agent_id: a for a in agents}
            candidate = getattr(fork_strategy, "candidate", None)
            intervention_type = getattr(candidate, "intervention_type", None)
            if intervention_type is None and getattr(fork_strategy, "name", "") == "official_clarification":
                intervention_type = "official_response"
            if intervention_type:
                active_claim_intervention = {
                    "intervention_type": intervention_type,
                    "target_nodes": list(getattr(candidate, "target_nodes", []) or []),
                }
            if narrative_enabled:
                narrative_intervention_type = getattr(candidate, "intervention_type", None)
                if narrative_intervention_type is None and getattr(fork_strategy, "name", "") == "official_clarification":
                    narrative_intervention_type = "official_clarification"
                if narrative_intervention_type:
                    target_ids = getattr(candidate, "target_nodes", None) if candidate is not None else None
                    apply_narrative_intervention(
                        agents,
                        narrative_states,
                        intervention_type=narrative_intervention_type,
                        tick=tick,
                        target_ids=target_ids,
                        config=narrative_config,
                    )
                    relations = build_narrative_relations(narrative_states)

        next_active: set[str] = set()
        tick_actions: list[PropagationAction] = []
        selected_narratives: Dict[str, Optional[NarrativeState]] = {}
        if narrative_enabled and tick > 0:
            selected_narratives = {
                source_id: select_active_narrative(
                    id_to_agent[source_id], narrative_states, config=narrative_config,
                )
                for source_id in sorted(active)
                if source_id in id_to_agent
            }

        if tick > 0:
            for source_id in sorted(active):
                source = id_to_agent.get(source_id)
                if source is None:
                    continue
                selected_narrative = selected_narratives.get(source_id) if narrative_enabled else None
                if narrative_enabled and selected_narrative is None:
                    # Actors may observe but choose not to publish any frame.
                    continue
                neighbours = adjacency.get(source_id, [])
                for target_id in neighbours:
                    target = id_to_agent.get(target_id)
                    if target is None:
                        continue
                    if narrative_enabled:
                        source_metadata = getattr(source, "metadata", {})
                        outbound_multiplier = (
                            float(source_metadata.get("narrative_outbound_reach_multiplier", 1.0) or 1.0)
                            if isinstance(source_metadata, dict) else 1.0
                        )
                        if rng.random() > _clamp(outbound_multiplier):
                            # Downranking suppresses source outbound reach;
                            # target inbound belief/trust remains untouched.
                            continue
                    exposure_count = register_exposure(
                        target,
                        tick=tick,
                        source_id=source_id,
                        content_ref=event.event_id,
                    )
                    content_state = {
                        "stance": source.stance,
                        "source_credibility": round(
                            0.55 * source.influence
                            + 0.45 * source.institutional_trust, 4
                        ),
                    }
                    narrative_exposure_count = 0
                    narrative_social_proof = 0.0
                    narrative_probability = None
                    if narrative_enabled and selected_narrative is not None:
                        narrative_exposure_count = register_narrative_exposure(
                            target,
                            selected_narrative.narrative_id,
                            tick=tick,
                            source_id=source_id,
                            content_ref=event.event_id,
                        )
                        narrative_social_proof = social_proof_from_exposure(
                            narrative_exposure_count,
                            narrative_config.social_proof_saturation,
                        )
                        narrative_source_credibility = round(
                            0.55 * source.influence
                            + 0.25 * source.institutional_trust
                            + 0.20 * selected_narrative.credibility,
                            4,
                        )
                        content_state.update({
                            "narrative_id": selected_narrative.narrative_id,
                            "narrative_credibility": selected_narrative.credibility,
                            "source_credibility": narrative_source_credibility,
                        })
                        update_narrative_belief_after_exposure(
                            target,
                            selected_narrative,
                            source_credibility=narrative_source_credibility,
                            social_proof=narrative_social_proof,
                            tick=tick,
                            relations=relations,
                            config=narrative_config,
                        )
                        narrative_probability = narrative_share_probability(
                            target,
                            selected_narrative,
                            social_proof=narrative_social_proof,
                        )
                    scene_state = {
                        "scenario_type": scenario,
                        "emotional_activation": _event_emotion_value(event.initial_emotion),
                    }
                    update_belief_after_exposure(
                        target,
                        source=source,
                        content_state=content_state,
                        scene_state=scene_state,
                        tick=tick,
                    )
                    share_probability = compute_share_probability(
                        source,
                        target,
                        content_state=content_state,
                        scene_state=scene_state,
                        exposure_context={
                            "exposure_count": exposure_count,
                            "scenario_type": scenario,
                        },
                    )
                    shared = rng.random() < share_probability * source.activity
                    if shared:
                        covered.add(target_id)
                        next_active.add(target_id)
                        action_type = "spread"
                        influence_delta = round(source.influence * 0.05, 3)
                        risk_delta = round(risk_factor * target.susceptibility * 0.1, 3)
                    else:
                        action_type = "exposed"
                        influence_delta = 0.0
                        risk_delta = round(risk_factor * target.susceptibility * 0.03, 3)
                    claim_transmissions = []
                    if claim_enabled:
                        source_claims = actor_claim_states.get(source_id, {})
                        target_claims = actor_claim_states.setdefault(target_id, {})
                        claim_transmissions = transmit_claim_states(
                            source,
                            target,
                            source_claims,
                            target_claims,
                            tick=tick,
                            source_id=source_id,
                            target_id=target_id,
                            exposure_count=exposure_count,
                            social_proof=social_proof_from_exposure(exposure_count),
                            intervention=active_claim_intervention,
                            config=claim_config,
                        )
                        claim_lineage.extend(claim_transmissions)
                    tick_actions.append(
                        PropagationAction(
                            tick=tick,
                            source_agent_id=source_id,
                            target_agent_id=target_id,
                            action_type=action_type,
                            content_summary=f"{source.role} -> {target.role}",
                            influence_delta=influence_delta,
                            risk_delta=risk_delta,
                            metadata={
                                "share_probability": share_probability,
                                "exposure_count": exposure_count,
                                "social_proof": social_proof_from_exposure(exposure_count),
                                "belief_strength": target.belief_strength,
                                **({
                                    "claim_transmissions": claim_transmissions,
                                    "claim_ids": [item["claim_id"] for item in claim_transmissions],
                                    "claim_distortion_flags": sorted({
                                        flag
                                        for item in claim_transmissions
                                        for flag in item.get("distortion_flags", [])
                                    }),
                                } if claim_enabled else {}),
                                **({
                                    "narrative_id": selected_narrative.narrative_id,
                                    "narrative_exposure_count": narrative_exposure_count,
                                    "narrative_social_proof": narrative_social_proof,
                                    "narrative_share_probability": narrative_probability,
                                    "narrative_belief": target.narrative_beliefs.get(selected_narrative.narrative_id),
                                    "narrative_adoption_state": target.narrative_adoption_state.get(selected_narrative.narrative_id),
                                } if narrative_enabled and selected_narrative is not None else {}),
                            },
                        )
                    )

            # keep previously active (still spreading)
            still_active = {aid for aid in active if id_to_agent.get(aid) and rng.random() < id_to_agent[aid].activity}
            next_active.update(still_active)

        actions.extend(tick_actions)
        # Tick 0 records the initial snapshot; preserve only the initial seed
        # set for the first real propagation step.  Later ticks stop naturally
        # when no new active actors were produced.
        active = set(initial_active) if tick == 0 else set(next_active)

        coverage_curve.append({
            "tick": tick,
            "covered_count": len(covered),
            "coverage": round(len(covered) / max(1, len(agents)), 3),
        })
        emotion_curve.append(_compute_emotion(tick, scenario, coverage_curve[-1]["coverage"], actions, agents))

        if narrative_enabled:
            for actor in agents:
                refresh_actor_public_stance(actor, narrative_states)
            tick_analysis = build_narrative_analysis(agents, narrative_states, relations=relations)
            narrative_share_history.append({
                "tick": tick,
                "narrative_share": dict(tick_analysis.get("narrative_share", {})),
                "unaware_share": tick_analysis.get("unaware_share", 0.0),
                "dominant_narrative": tick_analysis.get("dominant_narrative"),
                "narrative_entropy": tick_analysis.get("narrative_entropy", 0.0),
            })

    key_nodes = compute_key_nodes(agents, adjacency, actions, top_k=5)

    narrative_analysis = build_narrative_analysis(
        agents,
        narrative_states,
        relations=relations,
        narrative_share_history=narrative_share_history,
        model_provenance={
            "narrative_dynamics_enabled": bool(narrative_enabled),
            "narrative_extraction_source": event.metadata.get("narrative_extraction_source", "canonical_case") if isinstance(event.metadata, dict) else "canonical_case",
            "canonical_grounding": event.metadata.get("canonical_grounding", "G0") if isinstance(event.metadata, dict) else "G0",
        },
    ) if narrative_enabled else {}
    claim_analysis = build_claim_analysis(
        claim_records,
        actor_claim_states,
        claim_lineage,
        config=claim_config,
    ) if claim_enabled else {}

    trace = PropagationTrace(
        trace_id=str(uuid.uuid4()),
        scenario_type=scenario,
        ticks=ticks,
        agents=agents,
        actions=actions,
        coverage_curve=coverage_curve,
        emotion_curve=emotion_curve,
        key_nodes=key_nodes,
        final_metrics={},
        narrative_analysis=narrative_analysis,
        claim_analysis=claim_analysis,
    )
    trace.final_metrics = summarize_trace(trace)
    return trace


def run_forked_propagation(
    event: PropagationEvent,
    agents: list[PropagationAgent],
    adjacency: dict[str, list[str]],
    ticks: int = 30,
    intervention_tick: int = 10,
    strategy_type: str = "remove_key_node",
    seed: int = 42,
    narratives: Optional[list[NarrativeState | dict]] = None,
    narrative_relations: Optional[list[NarrativeRelation | dict]] = None,
    claims: Optional[Sequence[Any]] = None,
    claim_config: ClaimDynamicsConfig | None = None,
) -> ForkedPropagationResult:
    """Run Branch A (no intervention) and Branch B (intervention) and compare."""
    # Branch A
    trace_a = run_propagation_simulation(
        event=event, agents=agents, adjacency=adjacency,
        ticks=ticks, seed=seed,
        fork_strategy=NoInterventionFork(),
        narratives=deepcopy(narratives),
        narrative_relations=deepcopy(narrative_relations),
        claims=deepcopy(claims),
        claim_config=claim_config,
    )

    # Branch B
    if strategy_type == "official_clarification":
        strategy_b: PropagationForkStrategy = OfficialClarificationFork(intervention_tick)
    else:
        strategy_b = RemoveKeyNodeFork(intervention_tick)

    trace_b = run_propagation_simulation(
        event=event, agents=agents, adjacency=adjacency,
        ticks=ticks, seed=seed,
        fork_strategy=strategy_b,
        narratives=deepcopy(narratives),
        narrative_relations=deepcopy(narrative_relations),
        claims=deepcopy(claims),
        claim_config=claim_config,
    )

    cov_a = trace_a.coverage_curve[-1]["coverage"] if trace_a.coverage_curve else 0.0
    cov_b = trace_b.coverage_curve[-1]["coverage"] if trace_b.coverage_curve else 0.0
    acts_a = len(trace_a.actions)
    acts_b = len(trace_b.actions)
    peak_a = trace_a.final_metrics.get("peak_risk", 0.0)
    peak_b = trace_b.final_metrics.get("peak_risk", 0.0)

    comparison = {
        "coverage_delta": round(cov_a - cov_b, 3),
        "action_delta": acts_a - acts_b,
        "peak_risk_delta": round(peak_a - peak_b, 3),
        "intervention_effective": (cov_a - cov_b) > 0.05 or (peak_a - peak_b) > 0.02,
        "strategy_type": strategy_type,
    }
    if event.scenario_type == "public_opinion":
        base_narratives = trace_a.narrative_analysis
        branch_narratives = trace_b.narrative_analysis
        comparison.update({
            "narrative_polarization_delta": round(
                float(base_narratives.get("narrative_polarization", 0.0))
                - float(branch_narratives.get("narrative_polarization", 0.0)), 3,
            ),
            "community_fragmentation_delta": round(
                float(base_narratives.get("community_fragmentation", 0.0))
                - float(branch_narratives.get("community_fragmentation", 0.0)), 3,
            ),
            "narrative_switch_rate_delta": round(
                float(branch_narratives.get("narrative_switch_rate", 0.0))
                - float(base_narratives.get("narrative_switch_rate", 0.0)), 3,
            ),
            "narrative_metric_semantics": "simulation_proxy",
        })
    elif event.scenario_type == "event_propagation":
        base_claims = trace_a.claim_analysis
        branch_claims = trace_b.claim_analysis
        comparison.update({
            "claim_fidelity_delta": round(
                float(branch_claims.get("claim_fidelity", 0.0))
                - float(base_claims.get("claim_fidelity", 0.0)), 6,
            ),
            "distortion_index_delta": round(
                float(branch_claims.get("distortion_index", 0.0))
                - float(base_claims.get("distortion_index", 0.0)), 6,
            ),
            "source_loss_rate_delta": round(
                float(branch_claims.get("source_loss_rate", 0.0))
                - float(base_claims.get("source_loss_rate", 0.0)), 6,
            ),
            "certainty_inflation_delta": round(
                float(branch_claims.get("certainty_inflation", 0.0))
                - float(base_claims.get("certainty_inflation", 0.0)), 6,
            ),
            "unsupported_claim_share_delta": round(
                float(branch_claims.get("unsupported_claim_share", 0.0))
                - float(base_claims.get("unsupported_claim_share", 0.0)), 6,
            ),
            "verified_claim_reach_delta": round(
                float(branch_claims.get("verified_claim_reach", 0.0))
                - float(base_claims.get("verified_claim_reach", 0.0)), 6,
            ),
            "correction_reach_delta": round(
                float(branch_claims.get("correction_reach", 0.0))
                - float(base_claims.get("correction_reach", 0.0)), 6,
            ),
            "claim_metric_semantics": "simulation_proxy",
            "claim_metric_source": "lightweight_claim_model",
        })

    return ForkedPropagationResult(
        fork_point={
            "intervention_tick": intervention_tick,
            "strategy_type": strategy_type,
        },
        branch_a=trace_a,
        branch_b=trace_b,
        comparison=comparison,
    )


# ---------------------------------------------------------------------------
# emotion heuristic
# ---------------------------------------------------------------------------


def _event_emotion_value(initial_emotion: str) -> float:
    return {
        "panic": 0.85,
        "anger": 0.78,
        "confusion": 0.58,
        "trust": 0.35,
    }.get(str(initial_emotion or "confusion").lower(), 0.55)


def _clamp(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _compute_emotion(
    tick: int,
    scenario: str,
    coverage: float,
    actions: list[PropagationAction],
    agents: list[PropagationAgent],
) -> dict:
    amplifier_actions = sum(
        1 for a in actions
        if a.tick == tick and a.action_type == "spread"
    )

    panic = 0.0
    anger = 0.0
    confusion = 0.3
    trust = 0.2
    risk = 0.0

    if scenario == "public_opinion":
        anger = min(1.0, coverage * 0.6 + amplifier_actions * 0.04)
        trust = max(0.0, 0.4 - coverage * 0.3)
        risk = round(anger * 0.7 + panic * 0.2 + (1 - trust) * 0.1, 3)
    elif scenario == "event_propagation":
        confusion = min(1.0, coverage * 0.7)
        panic = min(1.0, coverage * 0.5 + amplifier_actions * 0.05)
        trust = max(0.0, 0.5 - coverage * 0.35)
        risk = round(panic * 0.5 + confusion * 0.3 + (1 - trust) * 0.2, 3)
    elif scenario == "fraud_im":
        panic = min(1.0, coverage * 0.8)
        trust = max(0.0, 0.3 - coverage * 0.25)
        risk = round(panic * 0.8 + (1 - trust) * 0.2, 3)
    else:
        risk = round(coverage * 0.5, 3)

    return {
        "tick": tick,
        "panic": round(panic, 3),
        "anger": round(anger, 3),
        "confusion": round(confusion, 3),
        "trust": round(trust, 3),
        "risk": round(risk, 3),
    }
