from app.modules.propagation.intervention_ranker import (
    PairwiseLinearRanker,
    feature_vector,
    make_preference_record,
    rank_branches,
)


def _branch(candidate_id, intervention_type, metric):
    return {
        "branch_id": candidate_id,
        "intervention_candidate": {
            "candidate_id": candidate_id,
            "intervention_type": intervention_type,
        },
        "final_metrics": {
            "coverage_reduction": metric,
            "misinformation_reduction": metric,
            "total_score": metric,
        },
    }


def test_feature_vector_and_pairwise_schema_are_serializable():
    branch_a = _branch("a", "official_response", 0.9)
    branch_b = _branch("b", "downranking", 0.1)
    record = make_preference_record(
        case_id="case-1",
        scenario="public_opinion",
        candidate_a=branch_a,
        candidate_b=branch_b,
        preferred="a",
        judge_reason="更能覆盖原始传播链",
        human_verified=False,
    )
    assert record["preferred"] == "a"
    assert feature_vector(branch_a["intervention_candidate"], branch_a["final_metrics"])["coverage_reduction"] == 0.9


def test_pairwise_ranker_fit_and_round_trip():
    branch_a = _branch("a", "official_response", 0.9)
    branch_b = _branch("b", "downranking", 0.1)
    record = make_preference_record(
        case_id="case-1",
        scenario="public_opinion",
        candidate_a=branch_a,
        candidate_b=branch_b,
        preferred="a",
    )
    ranker = PairwiseLinearRanker()
    report = ranker.fit([record], epochs=3)
    restored = PairwiseLinearRanker.from_dict(report["weights"])
    assert report["records"] == 1
    assert restored.score(feature_vector(branch_a["intervention_candidate"], branch_a["final_metrics"])) > restored.score(
        feature_vector(branch_b["intervention_candidate"], branch_b["final_metrics"])
    )


def test_rank_modes_are_explicit_and_return_scores():
    branches = [_branch("a", "official_response", 0.9), _branch("b", "downranking", 0.1)]
    for mode in ("fixed_weight", "learned_global_weight", "learned_contextual_weight"):
        ranked = rank_branches(branches, scenario_type="public_opinion", mode=mode)
        assert ranked[0]["ranking_mode"] == mode
        assert isinstance(ranked[0]["ranking_score"], float)
