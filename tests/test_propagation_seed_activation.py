"""Regression tests for lightweight propagation seed activation timing."""


def _agent(agent_id, *, influence=0.9, activity=1.0, susceptibility=0.9):
    from app.modules.propagation.schema import PropagationAgent

    return PropagationAgent(
        agent_id=agent_id,
        role="ordinary_viewer",
        stance="neutral",
        influence=influence,
        susceptibility=susceptibility,
        activity=activity,
        trust_in_official=0.8,
        institutional_trust=0.8,
        verification_tendency=0.1,
        confirmation_bias=0.5,
        topic_involvement=0.9,
        emotional_activation=0.9,
        share_propensity=1.0,
    )


def _event(scenario_type="event_propagation"):
    from app.modules.propagation.schema import PropagationEvent

    return PropagationEvent.create(
        scenario_type=scenario_type,
        seed_text="高传播概率测试事件",
        risk_dimensions=["public_spread"],
        initial_emotion="urgency",
    )


def _run(monkeypatch, event, agents, adjacency, *, ticks=3, seed=42, narratives=None):
    from app.modules.propagation import simulator

    monkeypatch.setattr(simulator, "compute_share_probability", lambda *args, **kwargs: 1.0)
    return simulator.run_propagation_simulation(
        event,
        agents,
        adjacency,
        ticks=ticks,
        seed=seed,
        narratives=narratives,
    )


def test_initial_seed_reaches_first_real_propagation_tick(monkeypatch):
    agents = [_agent("A"), _agent("B", influence=0.1)]
    trace = _run(monkeypatch, _event(), agents, {"A": ["B"], "B": []}, ticks=1)

    assert len(trace.actions) > 0
    assert trace.coverage_curve[-1]["coverage"] > trace.coverage_curve[0]["coverage"]
    assert trace.actions[0].source_agent_id == "A"
    assert trace.actions[0].target_agent_id == "B"


def test_event_propagation_multitick_smoke(monkeypatch):
    agents = [_agent(f"A{i}", influence=0.9 - i * 0.01) for i in range(5)]
    adjacency = {f"A{i}": [f"A{(i + 1) % 5}"] for i in range(5)}
    trace = _run(monkeypatch, _event(), agents, adjacency, ticks=3)

    assert len(trace.actions) > 0
    assert trace.coverage_curve[-1]["coverage"] > trace.coverage_curve[0]["coverage"]


def test_public_narrative_propagation_reaches_non_seed_actor(monkeypatch):
    from app.modules.propagation.narrative_model import NarrativeState

    narratives = [
        NarrativeState(
            narrative_id="N1",
            label="initial frame",
            summary="initial frame",
            stance_direction="neutral",
            provenance="observed",
            credibility=0.9,
        ),
        NarrativeState(
            narrative_id="N2",
            label="competing frame",
            summary="competing frame",
            stance_direction="skeptical",
            provenance="inferred",
            credibility=0.6,
        ),
    ]
    agents = [_agent("A"), _agent("B", influence=0.1)]
    agents[0].narrative_beliefs["N1"] = 0.99
    trace = _run(
        monkeypatch,
        _event("public_opinion"),
        agents,
        {"A": ["B"], "B": []},
        ticks=1,
        narratives=narratives,
    )

    assert len(trace.actions) > 0
    target = next(agent for agent in trace.agents if agent.agent_id == "B")
    assert target.narrative_exposure_count.get("N1", 0) > 0


def test_natural_stop_with_seed_without_neighbors(monkeypatch):
    trace = _run(monkeypatch, _event(), [_agent("A")], {"A": []}, ticks=3)

    assert trace.actions == []
    coverage = [item["coverage"] for item in trace.coverage_curve]
    assert coverage[0] == 1.0
    assert len(set(coverage)) == 1


def test_seed_is_not_reactivated_from_covered_after_first_step(monkeypatch):
    from app.modules.propagation import simulator

    class SequenceRandom:
        def __init__(self, seed):
            self.values = iter((0.0, 0.99, 0.99))

        def random(self):
            return next(self.values, 0.99)

    monkeypatch.setattr(simulator._random, "Random", SequenceRandom)
    monkeypatch.setattr(simulator, "compute_share_probability", lambda *args, **kwargs: 1.0)
    agents = [_agent("A", activity=0.9), _agent("B", influence=0.1, activity=0.9)]
    trace = simulator.run_propagation_simulation(
        _event(),
        agents,
        {"A": ["B"], "B": []},
        ticks=3,
        seed=42,
    )

    assert len(trace.actions) == 1
    assert [action.source_agent_id for action in trace.actions] == ["A"]
