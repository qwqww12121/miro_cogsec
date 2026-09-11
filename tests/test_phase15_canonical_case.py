"""Static-contract tests for Phase 1.5 canonical case integration.

These tests are intentionally added but not executed in this phase.  Runtime,
LLM, OASIS, embedding, and API execution are outside the Phase 1.5 review.
"""

import inspect


def test_input_package_preserves_fragment_identity_and_provenance():
    from modules import InputPackage

    package = InputPackage.from_fragments(
        primary_text="观察到首发消息",
        fragments=[
            {"fragment_id": "TURN_A", "content": "首发消息", "source": "chat"},
            {"fragment_id": "FILE_B", "content": "官方回应", "source": "file", "timestamp": "t2"},
        ],
    )
    assert [item.evidence_id for item in package.evidence_items] == ["TURN_A", "FILE_B"]
    assert all(item.provenance == "observed" for item in package.evidence_items)
    assert package.evidence_items[1].timestamp == "t2"


def test_canonical_case_assigns_stable_observed_actor_ids_and_grounding():
    from modules import InputPackage, build_canonical_case

    package = InputPackage.from_fragments(
        primary_text="学生称老师发布回应，媒体观察并转发。",
        fragments=[
            {"fragment_id": "E1", "content": "学生称老师发布回应。", "timestamp": "t1"},
            {"fragment_id": "E2", "content": "媒体观察并转发。", "timestamp": "t2"},
        ],
    )
    first = build_canonical_case(package, scenario_type="public_opinion")
    second = build_canonical_case(package, scenario_type="public_opinion")
    assert [actor.actor_id for actor in first.actors] == [actor.actor_id for actor in second.actors]
    assert first.provenance["grounding_level"] in {"G1", "G2"}
    assert first.timeline and first.claims


def test_social_state_reuses_canonical_ids_and_tracks_actor_provenance():
    from modules import InputPackage, build_canonical_case
    from modules.social_state import build_social_state

    case = build_canonical_case(
        InputPackage.from_text("学生称老师发布回应，媒体转发。"),
        scenario_type="public_opinion",
    )
    state = build_social_state(
        case.summary,
        "public_opinion",
        n_agents=6,
        seed=42,
        canonical_case=case,
    )
    actor_ids = {actor.actor_id for actor in state.actors}
    assert {actor.actor_id for actor in case.actors}.issubset(actor_ids)
    assert any(actor.actor_id.startswith("SYNTH_") for actor in state.actors)
    assert state.provenance["initial_state_source"] == "canonical_social_state"
    assert case.simulation_state_id == state.simulation_state_id


def test_cognitive_profile_changes_same_case_same_seed_initial_state():
    from modules import CognitiveProfile, InputPackage, build_canonical_case
    from modules.social_state import build_social_state

    package = InputPackage.from_text("学生称老师发布回应，媒体转发。")
    cautious = CognitiveProfile(
        scenario_type="public_opinion",
        verification_habit=9.0,
        authority_compliance=2.0,
        social_proof_sensitivity=2.0,
    )
    urgent = CognitiveProfile(
        scenario_type="public_opinion",
        verification_habit=1.0,
        authority_compliance=9.0,
        social_proof_sensitivity=9.0,
    )
    first_case = build_canonical_case(package, scenario_type="public_opinion", cognitive_profile=cautious)
    second_case = build_canonical_case(package, scenario_type="public_opinion", cognitive_profile=urgent)
    first = build_social_state(first_case.summary, "public_opinion", cautious, n_agents=6, seed=11, canonical_case=first_case)
    second = build_social_state(second_case.summary, "public_opinion", urgent, n_agents=6, seed=11, canonical_case=second_case)
    assert [a.to_dict() for a in first.actors] != [a.to_dict() for a in second.actors]
    assert len(first.actors[0].cognitive_features.profile_dimensions) == 18
    assert len(first.metadata["scene_cognitive_prior"]["profile_dimensions"]) == 18


def test_snapshot_and_oasis_mapping_keep_one_simulation_state_id():
    from modules import InputPackage, build_canonical_case
    from modules.social_state import actor_to_oasis_row, actor_to_propagation_agent, build_social_state, create_snapshot

    case = build_canonical_case(InputPackage.from_text("学生称官方回应并核验。"), scenario_type="event_propagation")
    state = build_social_state(case.summary, "event_propagation", n_agents=4, canonical_case=case)
    snapshot = create_snapshot(state, seed=42)
    propagation_agent = actor_to_propagation_agent(state.actors[0])
    oasis_row = actor_to_oasis_row(state.actors[0])
    assert snapshot.simulation_state_id == state.simulation_state_id
    assert propagation_agent.agent_id == state.actors[0].actor_id
    assert state.actors[0].actor_id in oasis_row["username"]


def test_proxy_search_has_canonical_state_path_without_rebuilding_agents():
    from modules.propagation.intervention_search import run_proxy_intervention_search

    source = inspect.getsource(run_proxy_intervention_search)
    assert "social_state" in source
    assert "social_state.to_adjacency()" in source
    assert "actor_to_propagation_agent" in source
    assert "build_agents(scenario_type" in source
    assert "initial_state_source" in source


def test_oasis_verification_contract_accepts_shared_state_id_and_snapshot():
    from modules.propagation.oasis_verification import run_topk_oasis_verification

    signature = inspect.signature(run_topk_oasis_verification)
    assert "snapshot" in signature.parameters
    assert "simulation_state_id" in signature.parameters
    source = inspect.getsource(run_topk_oasis_verification)
    assert "shared_initial_world" in source
    assert "same candidate run" in source or "canonical S0" in source


def test_social_proof_sensitivity_changes_share_probability():
    from modules.propagation import PropagationAgent, compute_share_probability

    source = PropagationAgent(
        agent_id="source", role="student_kol", influence=0.8, stance="amplifying",
        susceptibility=0.5, activity=0.8, trust_in_official=0.5,
    )
    low = PropagationAgent(
        agent_id="low", role="ordinary_student", stance="neutral",
        influence=0.5, susceptibility=0.5, activity=0.5,
        trust_in_official=0.5, exposure_count=3, social_proof_sensitivity=0.1,
    )
    high = PropagationAgent(
        agent_id="high", role="ordinary_student", stance="neutral",
        influence=0.5, susceptibility=0.5, activity=0.5,
        trust_in_official=0.5, exposure_count=3, social_proof_sensitivity=0.9,
    )
    assert compute_share_probability(source, high) > compute_share_probability(source, low)


def test_dynamic_belief_update_recomputes_stance_from_one_helper():
    from modules.propagation import PropagationAgent, update_belief_after_exposure
    from modules.social_state import derive_stance_from_actor_state

    actor = PropagationAgent(
        agent_id="actor",
        role="ordinary_viewer",
        stance="neutral",
        influence=0.5,
        susceptibility=0.5,
        activity=0.5,
        trust_in_official=0.5,
        belief_strength=0.2,
        prior_belief=0.2,
        confirmation_bias=0.1,
    )
    update_belief_after_exposure(
        actor,
        tick=1,
        content_state={"belief_signal": 0.95, "source_credibility": 0.9},
    )
    assert actor.stance == derive_stance_from_actor_state(actor)
    assert actor.belief_history


def test_grounding_level_and_synthetic_fill_are_explicit():
    from modules import InputPackage, build_canonical_case
    from modules.social_state import build_social_state

    sparse_case = build_canonical_case(InputPackage.from_text("不明"), scenario_type="public_opinion")
    rich_case = build_canonical_case(
        InputPackage.from_fragments(
            primary_text="学生称老师发布回应。媒体观察并转发来源。",
            fragments=[
                {"fragment_id": "A", "content": "学生称老师发布回应。", "timestamp": "t1"},
                {"fragment_id": "B", "content": "媒体观察并转发来源。", "timestamp": "t2"},
            ],
        ),
        scenario_type="public_opinion",
    )
    sparse_state = build_social_state(sparse_case.summary, "public_opinion", n_agents=5, canonical_case=sparse_case)
    rich_state = build_social_state(rich_case.summary, "public_opinion", n_agents=5, canonical_case=rich_case)
    assert sparse_case.provenance["grounding_level"] == "G0"
    assert rich_case.provenance["grounding_level"] in {"G1", "G2"}
    assert sparse_state.provenance["synthetic_actor_count"] >= 1
    assert rich_state.provenance["observed_actor_count"] >= 1


def test_fraud_runtime_remains_separate_from_social_state_path():
    from app.services import cogsec_service

    source = inspect.getsource(cogsec_service.CogSecService.analyze_text)
    assert "fraud_interaction" in source
    assert "canonical in {\"public_opinion\", \"event_propagation\"}" in source
