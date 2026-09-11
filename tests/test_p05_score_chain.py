"""P0.5 score-chain and canonical Reporter regressions."""

import pytest

from modules.benchmark_adapter import build_benchmark_payload
from modules.response_planner import build_response_plan


def test_benchmark_field_provenance_exposes_low_score_lineage():
    text = "对方要求通过微信联系并先支付保证金。"
    payload = build_benchmark_payload(result={
        "scenario_metadata": {"canonical": "fraud_im"},
        "core_analysis": {
            "fraud_type": "private_contact_lure", "risk_level": "high",
            "attack_stage": "pre_payment", "asset_targets": ["保证金"],
            "fork_points": [{"type": "transfer_money"}],
            "intervention_window": {"start_turn": 0},
            "expected_warning": "不要付款", "expected_safe_action": "独立核验",
            "evidence_spans": ["微信", "保证金"],
        },
    }, scenario_text=text, scenario_type="fraud_im")
    provenance = payload["benchmark_field_provenance"]
    assert provenance["source_contract"].startswith("canonical runtime -> Report State")
    assert {"IWA", "ASA", "WSA", "ATA"} <= set(provenance["score_lineage"])
    assert provenance["score_lineage"]["IWA"]["prediction_fields"] == ["intervention_window"]
    assert "source_state_field" in provenance["fields"]["intervention_window"]


def test_reporter_uses_report_state_only_after_state_is_built():
    text = "信用卡代还广告要求通过微信联系。"
    payload = build_benchmark_payload(result={"scenario_metadata": {"canonical": "fraud_im"}}, scenario_text=text, scenario_type="fraud_im")
    state = payload["report_state"]
    result = {
        "report_state": state,
        "core_analysis": {"risk_level": "critical", "fraud_type": "should-not-be-read"},
        "benchmark_prediction": {"risk_level": "low", "fraud_type": "also-not-read"},
        "cogsec_analysis": {"evidence_trace": [{"text": "mutated internal evidence"}]},
        "scenario_metadata": {"canonical": "fraud_im"},
    }
    plan = build_response_plan(result=result, user_message=text)
    assert plan["primary_risk"] == state["summary"]["risk_level"]
    assert "mutated internal evidence" not in " ".join(plan["evidence"])


def test_canonical_blind_judge_miro_text_is_actual_assistant_answer():
    from scripts.make_closed_model_judge_input import build_request, miro_text_from

    llm_row = {"assistant_message": "LLM canonical"}
    miro_row = {"assistant_message": "Reporter canonical answer", "benchmark_prediction": {"risk_level": "high"}}
    assert miro_text_from(miro_row, "fraud_im") == "Reporter canonical answer"
    request = build_request(
        scenario="fraud_im",
        truth={"id": "case-1", "input": {"text": "原文"}, "answer": {}},
        llm_row=llm_row,
        miro_row=miro_row,
        seed=42,
        include_gold=False,
    )
    miro_slot = request["private_answer_key"]["A"] == "miro_cogsec"
    miro_answer = request["answer_a"]["text"] if miro_slot else request["answer_b"]["text"]
    assert miro_answer == "Reporter canonical answer"
    assert request["rendering_provenance"]["reconstructed_text"] is False


def test_formal_miro_judge_requires_canonical_answer_unless_legacy_is_explicit():
    from scripts.make_closed_model_judge_input import miro_text_from

    with pytest.raises(ValueError, match="canonical assistant_message"):
        miro_text_from({"benchmark_prediction": {"risk_level": "high"}}, "fraud_im")
