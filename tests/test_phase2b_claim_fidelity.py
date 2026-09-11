"""Regression coverage for the event-only Phase 2B claim-fidelity model."""

from copy import deepcopy


def _agent(
    agent_id,
    *,
    influence=0.9,
    verification=0.1,
    emotion=0.9,
    confirmation=0.7,
    topic=0.2,
    reactance=0.5,
    institutional_trust=0.8,
    social_proof=0.9,
    share=1.0,
):
    from modules.propagation.schema import PropagationAgent

    return PropagationAgent(
        agent_id=agent_id,
        role="ordinary_viewer",
        stance="neutral",
        influence=influence,
        susceptibility=0.85,
        activity=1.0,
        trust_in_official=institutional_trust,
        institutional_trust=institutional_trust,
        verification_tendency=verification,
        confirmation_bias=confirmation,
        social_proof_sensitivity=social_proof,
        topic_involvement=topic,
        reactance=reactance,
        emotional_activation=emotion,
        belief_strength=0.55,
        share_propensity=share,
    )


def _event(emotion="panic"):
    from modules.propagation.schema import PropagationEvent

    return PropagationEvent.create(
        scenario_type="event_propagation",
        seed_text="A reported event claim with an uncertain source",
        risk_dimensions=["distortion_index"],
        initial_emotion=emotion,
    )


def _claim():
    from modules.canonical_case import CanonicalClaim

    return CanonicalClaim(
        claim_id="C1",
        text="A reported event occurred",
        status="reported",
        provenance="observed",
        evidence_refs=["E1"],
    )


def _run(monkeypatch, agents, adjacency, *, claims=None, ticks=3, strategy=None):
    from modules.propagation import simulator

    monkeypatch.setattr(simulator, "compute_share_probability", lambda *args, **kwargs: 1.0)
    return simulator.run_propagation_simulation(
        _event(),
        agents,
        adjacency,
        ticks=ticks,
        seed=42,
        fork_strategy=strategy,
        claims=claims,
    )


def _candidate(intervention_type, target_nodes=None, tick=1):
    from modules.propagation.intervention_search import InterventionCandidate

    return InterventionCandidate(
        candidate_id=f"test_{intervention_type}",
        intervention_type=intervention_type,
        target_nodes=list(target_nodes or []),
        target_stage="early",
        intervention_tick=tick,
        message="test intervention",
        expected_mechanism="test mechanism",
        evidence_basis=["E1"],
        cost=0.1,
    )


def _candidate_run(monkeypatch, intervention_type, target_nodes=None, *, adjacency=None):
    from modules.propagation.intervention_search import CandidateInterventionFork

    agents = [_agent("A", influence=0.95), _agent("B", influence=0.1)]
    return _run(
        monkeypatch,
        agents,
        adjacency or {"A": ["B"], "B": []},
        claims=[_claim()],
        ticks=2,
        strategy=CandidateInterventionFork(
            _candidate(intervention_type, target_nodes),
            scenario_type="event_propagation",
        ),
    )


def test_canonical_claim_enters_event_runtime_and_lineage(monkeypatch):
    trace = _run(
        monkeypatch,
        [_agent("A", influence=0.95), _agent("B", influence=0.1)],
        {"A": ["B"], "B": []},
        claims=[_claim()],
        ticks=1,
    )

    assert trace.claim_analysis["claim_count"] == 1
    assert trace.claim_analysis["claim_fidelity_by_claim"]["C1"] > 0
    assert trace.claim_analysis["claim_lineage_summary"]["transmission_count"] == len(trace.actions)
    assert trace.actions[0].metadata["claim_transmissions"][0]["claim_id"] == "C1"


def test_missing_claims_use_honest_seed_text_fallback(monkeypatch):
    trace = _run(
        monkeypatch,
        [_agent("A", influence=0.95), _agent("B", influence=0.1)],
        {"A": ["B"], "B": []},
        claims=None,
        ticks=1,
    )

    assert trace.claim_analysis["claim_count"] == 1
    assert "RUNTIME_CLAIM_001" in trace.claim_analysis["claim_fidelity_by_claim"]
    assert trace.claim_analysis["provenance"]["reality_status"] == "stylized_simulation_proxy"


def test_public_opinion_does_not_activate_claim_engine(monkeypatch):
    from modules.propagation.narrative_model import NarrativeState
    from modules.propagation.schema import PropagationEvent
    from modules.propagation import simulator

    monkeypatch.setattr(simulator, "compute_share_probability", lambda *args, **kwargs: 1.0)
    event = PropagationEvent.create(
        scenario_type="public_opinion",
        seed_text="public opinion frame",
        risk_dimensions=["polarization"],
    )
    trace = simulator.run_propagation_simulation(
        event,
        [_agent("A", influence=0.95), _agent("B", influence=0.1)],
        {"A": ["B"], "B": []},
        ticks=1,
        narratives=[NarrativeState(
            narrative_id="N1",
            label="frame",
            summary="frame",
            stance_direction="neutral",
            provenance="observed",
            credibility=0.9,
        )],
        claims=[_claim()],
    )

    assert trace.claim_analysis == {}
    assert trace.narrative_analysis


def test_claim_metrics_are_deterministic_and_bounded(monkeypatch):
    agents = [_agent("A", influence=0.95), _agent("B", influence=0.1), _agent("C", influence=0.05)]
    adjacency = {"A": ["B"], "B": ["C"], "C": []}
    first = _run(monkeypatch, deepcopy(agents), adjacency, claims=[_claim()], ticks=3)
    second = _run(monkeypatch, deepcopy(agents), adjacency, claims=[_claim()], ticks=3)

    assert first.claim_analysis == second.claim_analysis
    for key in (
        "claim_fidelity", "distortion_index", "distortion_rate", "source_loss_rate",
        "certainty_inflation", "unsupported_claim_share", "verified_claim_reach",
        "correction_reach",
    ):
        assert 0.0 <= first.claim_analysis[key] <= 1.0


def test_repeated_propagation_loses_context_and_records_flags(monkeypatch):
    agents = [_agent("A3", influence=0.95), _agent("B", influence=0.2), _agent("C", influence=0.1), _agent("D", influence=0.05)]
    trace = _run(
        monkeypatch,
        agents,
        {"A3": ["B"], "B": ["C"], "C": ["D"], "D": []},
        claims=[_claim()],
        ticks=5,
    )

    states = trace.claim_analysis["actor_claim_states"]
    assert states["D"]["C1"]["context_retention"] < 0.92
    assert trace.claim_analysis["claim_generation_depth"] >= 3
    assert trace.claim_analysis["distortion_rate"] > 0


def test_high_verification_preserves_fidelity(monkeypatch):
    low = _run(
        monkeypatch,
        [_agent("A", influence=0.95, verification=0.05), _agent("B", influence=0.1, verification=0.05)],
        {"A": ["B"], "B": []},
        claims=[_claim()],
        ticks=2,
    )
    high = _run(
        monkeypatch,
        [_agent("A", influence=0.95, verification=0.95), _agent("B", influence=0.1, verification=0.95)],
        {"A": ["B"], "B": []},
        claims=[_claim()],
        ticks=2,
    )

    assert high.claim_analysis["claim_fidelity"] > low.claim_analysis["claim_fidelity"]
    assert high.claim_analysis["distortion_index"] < low.claim_analysis["distortion_index"]


def test_social_proof_raises_certainty_without_creating_evidence():
    from modules.propagation.claim_model import initialize_claim_states, transmit_claim_states

    source = _agent("A", verification=0.1)
    target = _agent("B", verification=0.1)
    records, source_states = initialize_claim_states([_claim()], ["A"])
    first_states = {}
    first = transmit_claim_states(
        source, target, source_states["A"], first_states,
        tick=1, source_id="A", target_id="B", exposure_count=1, social_proof=0.0,
    )[0]
    second = transmit_claim_states(
        source, target, source_states["A"], first_states,
        tick=2, source_id="A", target_id="B", exposure_count=6, social_proof=1.0,
    )[0]

    assert second["certainty"] >= first["certainty"]
    assert second["evidential_support"] == first["evidential_support"]


def test_source_loss_and_certainty_inflation_are_separate_metrics(monkeypatch):
    from modules.canonical_case import CanonicalClaim

    trace = _run(
        monkeypatch,
        [_agent("A", influence=0.95, verification=0.02, emotion=1.0, confirmation=1.0), _agent("B", influence=0.1, verification=0.02, emotion=1.0, confirmation=1.0)],
        {"A": ["B"], "B": []},
        claims=[CanonicalClaim("C1", "An unsupported event claim", provenance="inferred")],
        ticks=4,
    )

    assert trace.claim_analysis["source_loss_rate"] >= 0
    assert trace.claim_analysis["certainty_inflation"] >= 0
    assert "certainty_inflation" in trace.claim_analysis["actor_claim_states"]["B"]["C1"]["distortion_flags"]


def test_source_verification_improves_source_and_evidence(monkeypatch):
    baseline = _run(
        monkeypatch,
        [_agent("A", influence=0.95), _agent("B", influence=0.1)],
        {"A": ["B"], "B": []},
        claims=[_claim()],
        ticks=2,
    )
    branch = _candidate_run(monkeypatch, "source_verification", ["B"])

    base_state = baseline.claim_analysis["actor_claim_states"]["B"]["C1"]
    branch_state = branch.claim_analysis["actor_claim_states"]["B"]["C1"]
    assert branch_state["source_attribution"] > base_state["source_attribution"]
    assert branch_state["evidential_support"] > base_state["evidential_support"]


def test_content_labeling_improves_context(monkeypatch):
    baseline = _run(
        monkeypatch,
        [_agent("A", influence=0.95), _agent("B", influence=0.1)],
        {"A": ["B"], "B": []},
        claims=[_claim()],
        ticks=2,
    )
    branch = _candidate_run(monkeypatch, "content_labeling", ["B"])

    assert branch.claim_analysis["actor_claim_states"]["B"]["C1"]["context_retention"] > baseline.claim_analysis["actor_claim_states"]["B"]["C1"]["context_retention"]


def test_debunking_reduces_certainty_and_reaches_correction(monkeypatch):
    baseline = _run(
        monkeypatch,
        [_agent("A", influence=0.95), _agent("B", influence=0.1)],
        {"A": ["B"], "B": []},
        claims=[_claim()],
        ticks=2,
    )
    branch = _candidate_run(monkeypatch, "debunking", ["B"])
    base_state = baseline.claim_analysis["actor_claim_states"]["B"]["C1"]
    branch_state = branch.claim_analysis["actor_claim_states"]["B"]["C1"]

    assert branch_state["certainty"] < base_state["certainty"]
    assert branch_state["corrected"] is True
    assert branch.claim_analysis["correction_reach"] > 0


def test_friction_has_no_direct_claim_fidelity_boost():
    from modules.propagation.claim_model import initialize_claim_states, transmit_claim_states

    source = _agent("A")
    target = _agent("B")
    _, source_states = initialize_claim_states([_claim()], ["A"])
    plain_states = {}
    friction_states = {}
    transmit_claim_states(source, target, source_states["A"], plain_states, tick=1, source_id="A", target_id="B")
    transmit_claim_states(
        source, target, source_states["A"], friction_states,
        tick=1, source_id="A", target_id="B",
        intervention={"intervention_type": "friction_prompt", "target_nodes": ["B"]},
    )

    for key in ("content_integrity", "source_attribution", "context_retention", "certainty", "evidential_support"):
        assert friction_states["C1"].to_dict()[key] == plain_states["C1"].to_dict()[key]


def test_correction_reach_requires_real_claim_propagation(monkeypatch):
    from modules.propagation.intervention_search import CandidateInterventionFork

    no_edge = _candidate_run(monkeypatch, "official_response", [], adjacency={"A": [], "B": []})
    with_edge = _candidate_run(monkeypatch, "official_response", [], adjacency={"A": ["B"], "B": []})

    assert no_edge.claim_analysis["correction_reach"] == 0
    assert with_edge.claim_analysis["correction_reach"] > 0


def test_targeted_debunking_does_not_leak_to_sibling(monkeypatch):
    from modules.propagation.intervention_search import CandidateInterventionFork

    trace = _run(
        monkeypatch,
        [_agent("A", influence=0.95), _agent("B", influence=0.1), _agent("C", influence=0.05)],
        {"A": ["B", "C"], "B": [], "C": []},
        claims=[_claim()],
        ticks=1,
        strategy=CandidateInterventionFork(
            _candidate("debunking", ["B"]),
            scenario_type="event_propagation",
        ),
    )

    states = trace.claim_analysis["actor_claim_states"]
    assert states["B"]["C1"]["corrected"] is True
    assert states["C"]["C1"]["corrected"] is False
    assert trace.claim_analysis["correction_reach"] == round(1 / 3, 6)


def test_targeted_correction_can_propagate_from_target_later(monkeypatch):
    from modules.propagation.intervention_search import CandidateInterventionFork

    trace = _run(
        monkeypatch,
        [_agent("A", influence=0.95), _agent("B", influence=0.1), _agent("C", influence=0.05)],
        {"A": ["B", "C"], "B": ["C"], "C": []},
        claims=[_claim()],
        ticks=2,
        strategy=CandidateInterventionFork(
            _candidate("debunking", ["B"]),
            scenario_type="event_propagation",
        ),
    )

    states = trace.claim_analysis["actor_claim_states"]
    assert states["B"]["C1"]["corrected"] is True
    assert states["C"]["C1"]["corrected"] is True
    assert any(
        item["source_actor_id"] == "B"
        and item["target_actor_id"] == "C"
        and item["corrected"] is True
        for item in trace.claim_analysis["claim_lineage"]
    )


def test_targeted_source_verification_and_labeling_do_not_change_sibling(monkeypatch):
    from modules.propagation.intervention_search import CandidateInterventionFork

    agents = [_agent("A", influence=0.95), _agent("B", influence=0.1), _agent("C", influence=0.05)]
    adjacency = {"A": ["B", "C"], "B": [], "C": []}
    for intervention_type, improved_key in (
        ("source_verification", "source_attribution"),
        ("content_labeling", "context_retention"),
    ):
        baseline = _run(monkeypatch, deepcopy(agents), adjacency, claims=[_claim()], ticks=1)
        branch = _run(
            monkeypatch,
            deepcopy(agents),
            adjacency,
            claims=[_claim()],
            ticks=1,
            strategy=CandidateInterventionFork(
                _candidate(intervention_type, ["B"]),
                scenario_type="event_propagation",
            ),
        )
        assert branch.claim_analysis["actor_claim_states"]["B"]["C1"][improved_key] > baseline.claim_analysis["actor_claim_states"]["B"]["C1"][improved_key]
        non_target_branch = branch.claim_analysis["actor_claim_states"]["C"]["C1"]
        non_target_baseline = baseline.claim_analysis["actor_claim_states"]["C"]["C1"]
        for key in (
            "content_integrity", "source_attribution", "context_retention",
            "evidential_support", "corrected", "verified",
        ):
            assert non_target_branch[key] == non_target_baseline[key]


def test_event_proxy_selector_ranks_by_formula_28_coverage(monkeypatch):
    from modules.propagation import intervention_search
    from modules.propagation.schema import PropagationTrace

    candidate_a = _candidate("debunking", ["B"])
    candidate_a.candidate_id = "coverage_first"
    candidate_b = _candidate("source_verification", ["B"])
    candidate_b.candidate_id = "claim_first"
    baseline_claim = {
        "claim_fidelity": 0.50,
        "distortion_index": 0.80,
        "source_loss_rate": 0.50,
        "certainty_inflation": 0.50,
        "unsupported_claim_share": 0.50,
        "verified_claim_reach": 0.10,
        "correction_reach": 0.00,
        "metric_semantics": "simulation_proxy",
        "claim_metric_source": "lightweight_claim_model",
    }

    def fake_trace(coverage, claim_analysis):
        return PropagationTrace(
            trace_id="fixture",
            scenario_type="event_propagation",
            ticks=2,
            agents=[_agent("A")],
            actions=[],
            coverage_curve=[{"tick": 0, "coverage": coverage[0]}, {"tick": 1, "coverage": coverage[1]}],
            emotion_curve=[{"tick": 0, "risk": 0.1}, {"tick": 1, "risk": 0.1}],
            key_nodes=[],
            final_metrics={},
            claim_analysis=claim_analysis,
        )

    def fake_run(*args, **kwargs):
        fork_strategy = kwargs.get("fork_strategy")
        candidate = getattr(fork_strategy, "candidate", None)
        if candidate is None:
            return fake_trace([0.80, 0.80], baseline_claim)
        if candidate.candidate_id == "coverage_first":
            return fake_trace([0.80, 0.20], {
                **baseline_claim,
                "claim_fidelity": 0.52,
                "distortion_index": 0.78,
                "source_loss_rate": 0.49,
                "certainty_inflation": 0.49,
                "unsupported_claim_share": 0.49,
            })
        return fake_trace([0.80, 0.60], {
            **baseline_claim,
            "claim_fidelity": 0.85,
            "distortion_index": 0.20,
            "source_loss_rate": 0.10,
            "certainty_inflation": 0.10,
            "unsupported_claim_share": 0.10,
            "verified_claim_reach": 0.70,
            "correction_reach": 0.50,
        })

    monkeypatch.setattr(intervention_search, "run_propagation_simulation", fake_run)
    monkeypatch.setattr(
        intervention_search,
        "generate_intervention_candidates",
        lambda **kwargs: [candidate_a, candidate_b],
    )
    result = intervention_search.run_proxy_intervention_search(
        scenario_type="event_propagation",
        seed_text="event",
        quick_mode=True,
        seed=42,
    )

    assert result["selected_best_branch"]["candidate_id"] == "coverage_first"
    scores = {
        branch["intervention_candidate"]["candidate_id"]: branch["final_metrics"]["score_breakdown"]
        for branch in result["counterfactual_branches"]
    }
    assert scores["coverage_first"]["coverage_score"] > scores["claim_first"]["coverage_score"]
    assert scores["claim_first"]["claim_fidelity_score"] > scores["coverage_first"]["claim_fidelity_score"]
    assert result["selected_best_branch"]["score_breakdown"]["total_score"] > 0


def test_lineage_records_match_existing_actions(monkeypatch):
    trace = _run(
        monkeypatch,
        [_agent("A", influence=0.95), _agent("B", influence=0.1)],
        {"A": ["B"], "B": []},
        claims=[_claim()],
        ticks=2,
    )
    lineage = trace.claim_analysis["claim_lineage"]
    assert len(lineage) == len(trace.actions)
    for action, item in zip(trace.actions, lineage):
        assert item["tick"] == action.tick
        assert item["source_actor_id"] == action.source_agent_id
        assert item["target_actor_id"] == action.target_agent_id


def test_forked_branches_start_with_identical_claim_state(monkeypatch):
    from modules.propagation.simulator import run_forked_propagation

    monkeypatch.setattr(
        __import__("modules.propagation.simulator", fromlist=["compute_share_probability"]),
        "compute_share_probability",
        lambda *args, **kwargs: 1.0,
    )
    result = run_forked_propagation(
        _event(),
        [_agent("A", influence=0.95), _agent("B", influence=0.1)],
        {"A": ["B"], "B": []},
        ticks=0,
        intervention_tick=1,
        claims=[_claim()],
        seed=42,
    )

    assert result.branch_a.claim_analysis["actor_claim_states"] == result.branch_b.claim_analysis["actor_claim_states"]


def test_event_ranking_uses_claim_metrics_not_legacy_misinformation_alias():
    from modules.propagation.intervention_search import InterventionCandidate, _compare_branch
    from modules.propagation.schema import PropagationTrace

    def trace(coverage, claims):
        return PropagationTrace(
            trace_id="t",
            scenario_type="event_propagation",
            ticks=2,
            agents=[_agent("A")],
            actions=[],
            coverage_curve=[{"tick": 0, "coverage": coverage}, {"tick": 1, "coverage": coverage}],
            emotion_curve=[{"tick": 0, "risk": 0.1}, {"tick": 1, "risk": 0.1}],
            key_nodes=[],
            final_metrics={},
            claim_analysis=claims,
        )

    base = trace(0.2, {
        "claim_fidelity": 0.3,
        "distortion_index": 0.8,
        "source_loss_rate": 0.7,
        "certainty_inflation": 0.8,
        "unsupported_claim_share": 0.8,
        "verified_claim_reach": 0.1,
        "correction_reach": 0.0,
        "metric_semantics": "simulation_proxy",
        "claim_metric_source": "lightweight_claim_model",
    })
    branch = trace(0.95, {
        "claim_fidelity": 0.9,
        "distortion_index": 0.1,
        "source_loss_rate": 0.1,
        "certainty_inflation": 0.1,
        "unsupported_claim_share": 0.1,
        "verified_claim_reach": 0.8,
        "correction_reach": 0.8,
        "metric_semantics": "simulation_proxy",
        "claim_metric_source": "lightweight_claim_model",
    })
    result = _compare_branch(
        baseline_trace=base,
        branch_trace=branch,
        candidate=InterventionCandidate("C", "source_verification", [], "early", 1, "", "", [], 0.1),
    )

    assert result["claim_fidelity_gain"] == 0.6
    assert result["distortion_reduction"] == 0.7
    assert result["distortion_reduction"] != result["misinformation_reduction"]
    assert result["score_breakdown"]["claim_fidelity_score"] > 0
