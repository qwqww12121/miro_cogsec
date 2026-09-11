from __future__ import annotations

import json

from app.modules.propagation.intervention_ranker import (
    PairwiseLinearRanker,
    split_preferences_by_case,
    train_ranker_with_holdout,
)


def _record(case_id: str, preferred: str = "b"):
    return {
        "case_id": case_id,
        "scenario": "public_opinion",
        "candidate_a": {"intervention_type": "downranking"},
        "candidate_b": {"intervention_type": "official_response"},
        "metrics_a": {"overblocking_risk": 1.0, "correction_reach_gain": 0.0},
        "metrics_b": {"overblocking_risk": 0.0, "correction_reach_gain": 1.0},
        "preferred": preferred,
    }


def test_group_split_has_no_case_leakage() -> None:
    rows = [_record(f"case-{index // 2}") for index in range(12)]
    train, validation = split_preferences_by_case(rows, validation_ratio=0.34, seed=7)
    assert {item["case_id"] for item in train}.isdisjoint({item["case_id"] for item in validation})


def test_training_gate_writes_only_promoted_artifact(tmp_path) -> None:
    rows = [_record(f"case-{index}") for index in range(12)]
    # Deliberately invert the fixed-weight preference so learning has a clear
    # held-out improvement to demonstrate.
    for row in rows:
        row["preferred"] = "a"
    artifact_path = tmp_path / "ranker.json"
    result = train_ranker_with_holdout(
        rows,
        artifact_path=artifact_path,
        validation_ratio=0.34,
        epochs=120,
        minimum_records=4,
        minimum_validation_records=2,
        minimum_accuracy_gain=0.01,
    )
    assert result["promoted"] is True
    assert artifact_path.exists()
    ranker, artifact = PairwiseLinearRanker.load_artifact(artifact_path)
    assert artifact["dataset_hash"] == result["dataset_hash"]
    assert isinstance(ranker.score({"overblocking_risk": 1.0}), float)
