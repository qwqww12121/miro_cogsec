"""Closure tests for CandidateInterventionFork actor-level target scope."""

import pytest


def _agent(agent_id):
    from app.modules.propagation.schema import PropagationAgent

    return PropagationAgent(
        agent_id=agent_id,
        role="ordinary_viewer",
        stance="neutral",
        influence=0.5,
        susceptibility=0.85,
        activity=0.8,
        trust_in_official=0.8,
        institutional_trust=0.8,
        verification_tendency=0.6,
        belief_strength=0.5,
    )


def _candidate(intervention_type, target_nodes):
    from app.modules.propagation.intervention_search import InterventionCandidate

    return InterventionCandidate(
        candidate_id=f"closure_{intervention_type}",
        intervention_type=intervention_type,
        target_nodes=list(target_nodes),
        target_stage="early",
        intervention_tick=1,
        message="closure test",
        expected_mechanism="closure test",
        evidence_basis=[],
        cost=0.1,
    )


def _apply(intervention_type, target_nodes):
    from app.modules.propagation.intervention_search import CandidateInterventionFork

    agents = [_agent("A"), _agent("B"), _agent("C")]
    before = {agent.agent_id: agent.to_dict() for agent in agents}
    fork = CandidateInterventionFork(
        _candidate(intervention_type, target_nodes),
        scenario_type="event_propagation",
    )
    new_agents, adjacency, metadata = fork.apply(
        agents,
        {"A": ["B", "C"], "B": [], "C": []},
        [],
    )
    return before, {agent.agent_id: agent for agent in new_agents}, metadata


@pytest.mark.parametrize("intervention_type", ["debunking", "source_verification"])
def test_targeted_verification_and_debunking_only_change_target(intervention_type):
    before, after, metadata = _apply(intervention_type, ["B"])

    assert after["B"].institutional_trust > before["B"]["institutional_trust"]
    assert after["A"].to_dict() == before["A"]
    assert after["C"].to_dict() == before["C"]
    assert metadata["touched_agents"] == ["B"]


@pytest.mark.parametrize(
    "intervention_type,changed_fields",
    [("content_labeling", ("susceptibility", "activity")), ("community_note", ("institutional_trust",))],
)
def test_targeted_labeling_only_changes_target(intervention_type, changed_fields):
    before, after, metadata = _apply(intervention_type, ["B"])

    for field in changed_fields:
        if field == "institutional_trust":
            assert after["B"].institutional_trust > before["B"][field]
        else:
            assert getattr(after["B"], field) < before["B"][field]
    assert after["A"].to_dict() == before["A"]
    assert after["C"].to_dict() == before["C"]
    assert metadata["touched_agents"] == ["B"]


def test_empty_target_official_response_preserves_broadcast():
    before, after, metadata = _apply("official_response", [])

    for agent_id in ("A", "B", "C"):
        assert after[agent_id].institutional_trust > before[agent_id]["institutional_trust"]
    assert metadata["touched_agents"] == ["A", "B", "C"]


def test_explicit_target_official_response_is_not_broadcast():
    before, after, metadata = _apply("official_response", ["B"])

    assert after["B"].institutional_trust > before["B"]["institutional_trust"]
    assert after["A"].to_dict() == before["A"]
    assert after["C"].to_dict() == before["C"]
    assert metadata["touched_agents"] == ["B"]


def test_non_broadcast_empty_node_target_does_not_target_all_agents():
    before, after, metadata = _apply("node_targeting", [])

    assert {agent_id: agent.to_dict() for agent_id, agent in after.items()} == before
    assert metadata["touched_agents"] == []


@pytest.mark.parametrize("intervention_type", ["downranking", "node_targeting"])
def test_targeted_node_intervention_only_changes_target_actor(intervention_type):
    before, after, metadata = _apply(intervention_type, ["B"])

    assert after["B"].influence < before["B"]["influence"]
    assert after["B"].activity < before["B"]["activity"]
    assert after["A"].to_dict() == before["A"]
    assert after["C"].to_dict() == before["C"]
    assert metadata["touched_agents"] == ["B"]


def test_targeted_event_friction_only_marks_target_actor():
    before, after, metadata = _apply("friction_prompt", ["B"])

    assert after["B"].metadata["claim_friction_share_multiplier"] < 1.0
    assert after["A"].to_dict() == before["A"]
    assert after["C"].to_dict() == before["C"]
    assert metadata["touched_agents"] == ["B"]
