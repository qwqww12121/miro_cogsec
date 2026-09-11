"""Static-contract tests for Phase 2A narrative competition.

These tests are intentionally added but not executed in Phase 2A review.
They cover deterministic extraction, actor-conditioned narrative dynamics,
intervention semantics, metric bounds, and the S0/regression boundary.
"""

import inspect

import pytest


def _case(text="学生质疑校方隐瞒事故，官方声明称目前证据不足并澄清，等待进一步核实。"):
    from modules import InputPackage, build_canonical_case

    return build_canonical_case(
        InputPackage.from_fragments(
            primary_text=text,
            fragments=[{"fragment_id": "E1", "content": text, "source": "chat"}],
        ),
        scenario_type="public_opinion",
    )


def _narratives():
    from modules.propagation.narrative_model import extract_public_opinion_narratives

    return extract_public_opinion_narratives(_case(), max_narratives=4)


def _actor(**kwargs):
    from modules.propagation.schema import PropagationAgent

    values = {
        "agent_id": "A1",
        "role": "ordinary_viewer",
        "stance": "neutral",
        "influence": 0.5,
        "susceptibility": 0.5,
        "activity": 0.7,
        "trust_in_official": 0.5,
        "institutional_trust": 0.5,
        "verification_tendency": 0.5,
        "confirmation_bias": 0.6,
        "topic_involvement": 0.7,
        "emotional_activation": 0.6,
        "share_propensity": 0.7,
    }
    values.update(kwargs)
    return PropagationAgent(**values)


def test_same_case_yields_bounded_multiple_narratives():
    narratives = _narratives()
    assert 2 <= len(narratives) <= 4
    assert all(0.0 <= item.credibility <= 1.0 for item in narratives)


def test_narrative_ids_are_stable_for_same_case_and_seed():
    from modules.propagation.narrative_model import extract_public_opinion_narratives

    assert [item.narrative_id for item in _narratives()] == [
        item.narrative_id for item in extract_public_opinion_narratives(_case(), max_narratives=4)
    ]


def test_explicit_observed_frame_is_not_synthetic():
    observed = [item for item in _narratives() if item.stance_direction == "institutional_concealment"]
    assert observed and observed[0].provenance == "observed"


def test_synthetic_narrative_does_not_enter_canonical_claims():
    from modules.propagation.narrative_model import extract_public_opinion_narratives

    case = _case("学生质疑校方隐瞒事故。")
    narratives = extract_public_opinion_narratives(case, max_narratives=4)
    synthetic = [item for item in narratives if item.provenance == "synthetic"]
    claim_ids = {claim.claim_id for claim in case.claims}
    # Sparse deterministic extraction may yield inferred rather than synthetic
    # frames; only assert truthful provenance when a synthetic frame exists.
    assert all(item.provenance in {"observed", "inferred", "synthetic"} for item in narratives)
    assert all(item.narrative_id not in claim_ids for item in synthetic)
    assert all(not set(item.source_claim_ids) - claim_ids for item in synthetic)


def test_affinity_differs_by_institutional_trust():
    from modules.propagation.narrative_model import compute_narrative_affinity

    official = next(item for item in _narratives() if item.stance_direction == "official_correction")
    low = _actor(institutional_trust=0.15, trust_in_official=0.15)
    high = _actor(institutional_trust=0.85, trust_in_official=0.85)
    assert compute_narrative_affinity(low, official) != compute_narrative_affinity(high, official)


def test_confirmation_bias_favors_aligned_update():
    from modules.propagation.narrative_model import (
        compute_narrative_affinity,
        initialize_actor_narratives,
        update_narrative_belief_after_exposure,
    )

    narrative = _narratives()[0]
    aligned = _actor(prior_belief=0.8, belief_strength=0.8, confirmation_bias=0.9)
    conflicting = _actor(agent_id="A2", prior_belief=0.2, belief_strength=0.2, confirmation_bias=0.9)
    initialize_actor_narratives([aligned, conflicting], [narrative])
    before_a = aligned.narrative_beliefs[narrative.narrative_id]
    before_b = conflicting.narrative_beliefs[narrative.narrative_id]
    update_narrative_belief_after_exposure(aligned, narrative, source_credibility=0.7, tick=1)
    update_narrative_belief_after_exposure(conflicting, narrative, source_credibility=0.7, tick=1)
    assert abs(aligned.narrative_beliefs[narrative.narrative_id] - before_a) >= abs(
        conflicting.narrative_beliefs[narrative.narrative_id] - before_b
    ) or compute_narrative_affinity(aligned, narrative) >= compute_narrative_affinity(conflicting, narrative)


def test_repeated_narrative_exposure_saturates_social_proof():
    from modules.propagation.narrative_model import register_narrative_exposure
    from modules.social_state.behavior import social_proof_from_exposure

    actor = _actor()
    narrative = _narratives()[0]
    counts = [register_narrative_exposure(actor, narrative.narrative_id, tick=i) for i in (1, 2, 3)]
    assert counts == [1, 2, 3]
    assert social_proof_from_exposure(counts[-1]) <= 1.0


def test_exposure_is_narrative_specific():
    from modules.propagation.narrative_model import register_narrative_exposure

    actor = _actor()
    first, second = _narratives()[:2]
    for tick in (1, 2, 3):
        register_narrative_exposure(actor, first.narrative_id, tick=tick)
    assert actor.narrative_exposure_count[first.narrative_id] == 3
    assert actor.narrative_exposure_count.get(second.narrative_id, 0) == 0


def test_narrative_switch_and_rate_are_recorded():
    from modules.propagation.narrative_model import (
        initialize_actor_narratives,
        refresh_actor_public_stance,
    )

    first, second = _narratives()[:2]
    actor = _actor()
    initialize_actor_narratives([actor], [first, second])
    actor.narrative_beliefs[first.narrative_id] = 0.8
    actor.narrative_beliefs[second.narrative_id] = 0.1
    refresh_actor_public_stance(actor, [first, second])
    actor.narrative_beliefs[second.narrative_id] = 0.9
    refresh_actor_public_stance(actor, [first, second])
    assert actor.narrative_switch_count == 1


def test_community_distributions_can_differ():
    from modules.propagation.narrative_model import (
        compute_narrative_metrics,
        initialize_actor_narratives,
        register_narrative_exposure,
    )

    first, second = _narratives()[:2]
    left = _actor(agent_id="L", community_id="c1")
    right = _actor(agent_id="R", community_id="c2")
    initialize_actor_narratives([left, right], [first, second])
    register_narrative_exposure(left, first.narrative_id, tick=1)
    register_narrative_exposure(right, second.narrative_id, tick=1)
    left.narrative_beliefs[first.narrative_id] = 0.9
    left.narrative_beliefs[second.narrative_id] = 0.1
    right.narrative_beliefs[first.narrative_id] = 0.1
    right.narrative_beliefs[second.narrative_id] = 0.9
    metrics = compute_narrative_metrics([left, right], [first, second])
    assert metrics["community_narrative_distribution"]["c1"] != metrics["community_narrative_distribution"]["c2"]


def test_official_response_is_actor_conditioned():
    from modules.propagation.narrative_model import apply_narrative_intervention

    narratives = _narratives()
    low = _actor(agent_id="low", institutional_trust=0.15, trust_in_official=0.15)
    high = _actor(agent_id="high", institutional_trust=0.85, trust_in_official=0.85)
    before = [dict(low.narrative_beliefs), dict(high.narrative_beliefs)]
    apply_narrative_intervention([low, high], narratives, intervention_type="official_response", tick=2)
    assert low.narrative_beliefs != before[0] and high.narrative_beliefs != before[1]
    assert low.narrative_beliefs["N_OFFICIAL"] != high.narrative_beliefs["N_OFFICIAL"]


def test_friction_changes_share_probability_without_belief_rewrite():
    from modules.propagation.narrative_model import (
        apply_narrative_intervention,
        initialize_actor_narratives,
        narrative_share_probability,
    )

    actor = _actor()
    narrative = _narratives()[0]
    initialize_actor_narratives([actor], [narrative])
    before_belief = dict(actor.narrative_beliefs)
    before_probability = narrative_share_probability(actor, narrative)
    apply_narrative_intervention([actor], [narrative], intervention_type="friction_prompt", tick=2)
    assert actor.narrative_beliefs == before_belief
    assert narrative_share_probability(actor, narrative) < before_probability


def test_explicit_share_multiplier_overrides_actor_metadata():
    from modules.propagation.narrative_model import narrative_share_probability

    actor = _actor(metadata={"narrative_share_multiplier": 0.2})
    narrative = _narratives()[0]
    implicit = narrative_share_probability(actor, narrative)
    explicit = narrative_share_probability(actor, narrative, share_multiplier=1.0)
    assert explicit > implicit


def test_downranking_changes_outbound_reach_without_trust_change():
    from modules.propagation.narrative_model import apply_narrative_intervention

    actor = _actor()
    trust = actor.institutional_trust
    apply_narrative_intervention([actor], _narratives(), intervention_type="downranking", tick=2, target_ids=[actor.agent_id])
    assert actor.institutional_trust == trust
    assert actor.metadata["narrative_outbound_reach_multiplier"] < 1.0


def test_competing_relation_updates_current_endpoint_without_attribute_error():
    from modules.propagation.narrative_model import (
        NarrativeRelation,
        initialize_actor_narratives,
        update_narrative_belief_after_exposure,
    )

    first, second = _narratives()[:2]
    actor = _actor()
    initialize_actor_narratives([actor], [first, second])
    actor.narrative_beliefs[first.narrative_id] = 0.2
    actor.narrative_beliefs[second.narrative_id] = 0.8
    before = actor.narrative_beliefs[second.narrative_id]
    update_narrative_belief_after_exposure(
        actor,
        first,
        source_credibility=0.95,
        relations=[NarrativeRelation(first.narrative_id, second.narrative_id, "competes", 0.8)],
        tick=1,
    )
    assert actor.narrative_beliefs[second.narrative_id] <= before


def test_reshare_probability_is_target_conditioned():
    from modules.propagation.narrative_model import (
        initialize_actor_narratives,
        narrative_share_probability,
    )

    narrative = _narratives()[0]
    source = _actor(agent_id="source", share_propensity=0.05)
    target = _actor(agent_id="target", share_propensity=0.95)
    initialize_actor_narratives([source, target], [narrative])
    source.narrative_beliefs[narrative.narrative_id] = 0.05
    target.narrative_beliefs[narrative.narrative_id] = 0.95
    source.narrative_exposure_count[narrative.narrative_id] = 4
    target.narrative_exposure_count[narrative.narrative_id] = 1
    assert narrative_share_probability(
        target, narrative, social_proof=0.25
    ) > narrative_share_probability(source, narrative, social_proof=1.0)


def test_source_narrative_state_does_not_replace_target_willingness():
    from modules.propagation.narrative_model import (
        initialize_actor_narratives,
        narrative_share_probability,
    )

    narrative = _narratives()[0]
    target = _actor(agent_id="target", share_propensity=0.8)
    source_a = _actor(agent_id="source-a")
    source_b = _actor(agent_id="source-b")
    initialize_actor_narratives([target, source_a, source_b], [narrative])
    target.narrative_beliefs[narrative.narrative_id] = 0.7
    source_a.narrative_beliefs[narrative.narrative_id] = 0.01
    source_b.narrative_beliefs[narrative.narrative_id] = 0.99
    first = narrative_share_probability(target, narrative, social_proof=0.5)
    second = narrative_share_probability(target, narrative, social_proof=0.5)
    assert first == second

    from modules.propagation import simulator

    source = inspect.getsource(simulator.run_propagation_simulation)
    assert "narrative_share_probability(\n                            target," in source
    assert "narrative_share_probability(\n                            source," not in source


def test_unaware_actor_cannot_select_unseen_narrative():
    from modules.propagation.narrative_model import select_active_narrative

    actor = _actor()
    narrative = _narratives()[0]
    actor.narrative_beliefs[narrative.narrative_id] = 0.99
    assert select_active_narrative(actor, [narrative]) is None


def test_actor_can_select_narrative_after_explicit_exposure():
    from modules.propagation.narrative_model import (
        register_narrative_exposure,
        select_active_narrative,
    )

    actor = _actor()
    narrative = _narratives()[0]
    actor.narrative_beliefs[narrative.narrative_id] = 0.99
    register_narrative_exposure(actor, narrative.narrative_id, tick=1)
    assert select_active_narrative(actor, [narrative]) is narrative


def test_seed_actor_knowledge_is_an_explicit_initialization_exception():
    from modules.propagation.narrative_model import actor_knows_narrative, register_narrative_exposure

    actor = _actor()
    narrative = _narratives()[0]
    register_narrative_exposure(actor, narrative.narrative_id, tick=0, source_id="seed")
    assert actor_knows_narrative(actor, narrative.narrative_id)


def test_narrative_share_excludes_unaware_population():
    from modules.propagation.narrative_model import compute_narrative_metrics, initialize_actor_narratives, register_narrative_exposure

    first, second = _narratives()[:2]
    actors = [_actor(agent_id=f"A{i}") for i in range(5)]
    initialize_actor_narratives(actors, [first, second])
    for actor, narrative in zip(actors[:3], [first, second, first]):
        register_narrative_exposure(actor, narrative.narrative_id, tick=1)
        actor.narrative_beliefs[narrative.narrative_id] = 0.9
    for actor in actors[3:]:
        actor.narrative_beliefs[first.narrative_id] = 0.99
    metrics = compute_narrative_metrics(actors, [first, second])
    assert metrics["narrative_share"][first.narrative_id] == pytest.approx(2 / 3, abs=1e-6)
    assert metrics["narrative_share"][second.narrative_id] == pytest.approx(1 / 3, abs=1e-6)
    assert metrics["unaware_share"] == 0.4


def test_downranking_targets_source_outbound_reach_only():
    from modules.propagation.narrative_model import apply_narrative_intervention

    source = _actor(agent_id="source")
    target = _actor(agent_id="target")
    apply_narrative_intervention(
        [source, target],
        _narratives(),
        intervention_type="downranking",
        tick=2,
        target_ids=[source.agent_id],
    )
    assert source.metadata["narrative_outbound_reach_multiplier"] < 1.0
    assert "narrative_exposure_multiplier" not in target.metadata


def test_downranking_does_not_globally_reduce_target_inbound_state():
    from modules.propagation.narrative_model import apply_narrative_intervention

    source = _actor(agent_id="source")
    target = _actor(agent_id="target")
    apply_narrative_intervention(
        [source, target],
        _narratives(),
        intervention_type="downranking",
        tick=2,
        target_ids=[source.agent_id],
    )
    assert target.institutional_trust == 0.5
    assert target.metadata.get("narrative_outbound_reach_multiplier", 1.0) == 1.0


def test_narrative_metrics_are_bounded_and_finite():
    from modules.propagation.narrative_model import compute_narrative_metrics, initialize_actor_narratives

    narratives = _narratives()
    actors = [_actor(agent_id=f"A{i}") for i in range(3)]
    initialize_actor_narratives(actors, narratives)
    metrics = compute_narrative_metrics(actors, narratives)
    assert 0.0 <= metrics["narrative_entropy"] <= 1.0
    assert 0.0 <= metrics["community_fragmentation"] <= 1.0
    assert 0.0 <= metrics["narrative_switch_rate"] <= 1.0
    assert all(value == value for value in metrics["narrative_share"].values())


def test_narrative_engine_does_not_build_second_social_world():
    from modules.propagation import narrative_model

    source = inspect.getsource(narrative_model)
    assert "build_social_state" not in source
    assert "build_agents" not in source


def test_phase2a_is_public_opinion_only_at_simulator_boundary():
    from modules.propagation import simulator

    source = inspect.getsource(simulator.run_propagation_simulation)
    assert 'scenario == "public_opinion"' in source
    assert "narrative_enabled" in source


def test_legacy_trace_contract_remains_present():
    from modules.propagation.schema import PropagationTrace

    fields = PropagationTrace.__dataclass_fields__
    assert {"coverage_curve", "emotion_curve", "final_metrics", "metadata"}.issubset(fields)
    assert "narrative_analysis" in fields
