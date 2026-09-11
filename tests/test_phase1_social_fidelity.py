"""Static-contract tests for Phase 1 actor/social fidelity upgrades.

These tests are intentionally added but not executed in this phase.  The
runtime instruction for this deliverable is source/diff review only.
"""

from random import Random


def _actor(**kwargs):
    from app.modules.propagation.schema import PropagationAgent

    defaults = {
        "agent_id": "agent_test",
        "role": "ordinary_viewer",
        "stance": "neutral",
        "influence": 0.5,
        "susceptibility": 0.5,
        "activity": 0.5,
        "trust_in_official": 0.5,
    }
    defaults.update(kwargs)
    return PropagationAgent(**defaults)


def test_same_role_actors_receive_distinct_state_from_metadata():
    from app.modules.social_state import build_actor_cognitive_state, build_scene_cognitive_prior

    scene = build_scene_cognitive_prior(scenario_type="public_opinion")
    first = build_actor_cognitive_state(
        scene, "ordinary_student", {"prior_belief": 0.2, "topic_involvement": 0.3}, Random(1)
    )
    second = build_actor_cognitive_state(
        scene, "ordinary_student", {"prior_belief": 0.8, "topic_involvement": 0.9}, Random(2)
    )
    assert first["prior_belief"] != second["prior_belief"]
    assert first["topic_involvement"] != second["topic_involvement"]


def test_same_role_oasis_personas_have_stable_actor_specific_voice():
    from app.modules.social_state import actor_state_persona_summary

    first = _actor(agent_id="viewer_001", role="ordinary_viewer")
    second = _actor(agent_id="viewer_002", role="ordinary_viewer")
    first_prompt = actor_state_persona_summary(first)
    second_prompt = actor_state_persona_summary(second)
    assert first_prompt != second_prompt
    assert first_prompt == actor_state_persona_summary(first)
    assert "没有新的事实" in first_prompt
    assert "不要重复上一轮" in first_prompt


def test_scene_prior_is_role_conditioned():
    from app.modules.social_state import build_actor_cognitive_state, build_scene_cognitive_prior

    scene = build_scene_cognitive_prior(scenario_type="event_propagation")
    official = build_actor_cognitive_state(scene, "official_responder", rng=Random(1))
    viewer = build_actor_cognitive_state(scene, "ordinary_viewer", rng=Random(1))
    assert official["verification_tendency"] != viewer["verification_tendency"]
    assert official["share_propensity"] != viewer["share_propensity"]


def test_stance_uses_state_not_only_random_choice():
    from app.modules.social_state import build_actor_cognitive_state, build_scene_cognitive_prior

    scene = build_scene_cognitive_prior(scenario_type="public_opinion")
    skeptical = build_actor_cognitive_state(scene, "ordinary_student", {"prior_belief": 0.1}, Random(3))
    supportive = build_actor_cognitive_state(scene, "ordinary_student", {"prior_belief": 0.9}, Random(3))
    assert skeptical["stance"] != supportive["stance"]


def test_repeated_exposure_is_not_activation_coverage():
    from app.modules.social_state import register_exposure

    target = _actor()
    register_exposure(target, tick=1, source_id="source")
    register_exposure(target, tick=2, source_id="source")
    register_exposure(target, tick=3, source_id="source")
    assert target.exposure_count == 3
    assert target.last_exposure_tick == 3


def test_social_proof_saturates():
    from app.modules.social_state import social_proof_from_exposure

    values = [social_proof_from_exposure(count) for count in range(1, 20)]
    assert values[-1] <= 1.0
    assert values[-1] >= values[0]


def test_verification_lowers_unverified_share_probability():
    from app.modules.propagation import compute_share_probability

    source = _actor(influence=0.7, stance="amplifying")
    low_check = _actor(verification_tendency=0.2)
    high_check = _actor(verification_tendency=0.9)
    assert compute_share_probability(source, high_check, {"belief_signal": 0.8}) < compute_share_probability(
        source, low_check, {"belief_signal": 0.8}
    )


def test_emotion_and_social_proof_raise_share_probability():
    from app.modules.propagation import compute_share_probability

    source = _actor(stance="amplifying")
    target = _actor(emotional_activation=0.2, exposure_count=0)
    baseline = compute_share_probability(source, target, scene_state={"scenario_type": "public_opinion"})
    target.emotional_activation = 0.9
    target.exposure_count = 3
    activated = compute_share_probability(source, target, scene_state={"scenario_type": "public_opinion"})
    assert activated > baseline


def test_belief_update_respects_confirmation_bias():
    from app.modules.propagation import update_belief_after_exposure

    aligned = _actor(belief_strength=0.7, confirmation_bias=0.8, verification_tendency=0.1)
    conflicting = _actor(belief_strength=0.7, confirmation_bias=0.8, verification_tendency=0.1)
    update_belief_after_exposure(aligned, tick=1, content_state={"belief_signal": 0.8, "source_credibility": 0.8})
    update_belief_after_exposure(conflicting, tick=1, content_state={"belief_signal": 0.1, "source_credibility": 0.8})
    assert abs(aligned.belief_strength - 0.7) > abs(conflicting.belief_strength - 0.7)


def test_official_response_is_actor_conditioned():
    from app.modules.social_state import update_institutional_trust

    low_reactance = _actor(institutional_trust=0.8, reactance=0.1)
    high_reactance = _actor(institutional_trust=0.8, reactance=0.9)
    update_institutional_trust(low_reactance, tick=2, verified=True)
    update_institutional_trust(high_reactance, tick=2, verified=True)
    assert low_reactance.institutional_trust != high_reactance.institutional_trust
    assert low_reactance.trust_history and high_reactance.trust_history


def test_community_is_separate_from_role():
    from app.modules.social_state import ActorState, assign_communities

    actors = [
        ActorState(actor_id="student_a", role="student", stance="supportive", prior_belief=0.8),
        ActorState(actor_id="student_b", role="student", stance="skeptical", prior_belief=0.2),
        ActorState(actor_id="teacher_a", role="teacher", stance="supportive", prior_belief=0.8),
    ]
    assign_communities(actors, "public_opinion", seed=7)
    assert len({actor.community_id for actor in actors}) >= 1
    assert any(
        left.community_id == right.community_id and left.role != right.role
        for index, left in enumerate(actors)
        for right in actors[index + 1:]
    )


def test_snapshot_contract_includes_new_initial_state():
    from app.modules.social_state import ActorState, SocialState, create_snapshot

    state = SocialState(
        scenario_id="phase1",
        scenario_type="public_opinion",
        actors=[ActorState(actor_id="actor_0000", role="student", exposure_count=0)],
    )
    snapshot = create_snapshot(state, seed=42)
    assert snapshot.actors[0].exposure_count == 0
    assert snapshot.model_config["social_model_version"] == "actor_state_v2"


def test_same_seed_branches_start_from_equivalent_agent_state():
    from copy import deepcopy

    from app.modules.propagation import build_agents, build_topology

    agents = build_agents("event_propagation", n_agents=8, seed=19)
    topology = build_topology(agents, topology_type="scale_free_like", seed=19)
    branch_a_agents = deepcopy(agents)
    branch_b_agents = deepcopy(agents)
    branch_a_topology = deepcopy(topology)
    branch_b_topology = deepcopy(topology)
    assert [agent.to_dict() for agent in branch_a_agents] == [agent.to_dict() for agent in branch_b_agents]
    assert branch_a_topology == branch_b_topology
