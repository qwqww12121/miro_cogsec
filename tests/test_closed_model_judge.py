from __future__ import annotations

import pytest

from scripts.run_closed_model_judge import JUDGE_DIMENSIONS, validate_judgement


def _valid_payload() -> dict:
    scores = {dimension: 8 for dimension in JUDGE_DIMENSIONS}
    return {
        "winner": "A",
        "answer_a_scores": dict(scores),
        "answer_b_scores": dict(scores),
        "rationale": "答案 A 的机制解释和行动建议更具体。",
    }


def test_judge_validation_accepts_complete_payload() -> None:
    validate_judgement(_valid_payload())


def test_judge_validation_rejects_missing_or_out_of_range_scores() -> None:
    missing = _valid_payload()
    del missing["answer_a_scores"][JUDGE_DIMENSIONS[0]]
    with pytest.raises(ValueError):
        validate_judgement(missing)

    out_of_range = _valid_payload()
    out_of_range["answer_b_scores"][JUDGE_DIMENSIONS[1]] = 11
    with pytest.raises(ValueError):
        validate_judgement(out_of_range)
