"""Regression tests for the unified report state and user-facing wording."""

from app.modules.benchmark_adapter import build_benchmark_payload
from app.modules.conversational_response import build_conversational_response
from app.modules.privacy_sanitizer import PrivacySanitizer
from app.modules.report_state import build_report_state


def _fraud_result():
    text = "信用卡代还广告要求通过微信联系，提供刷卡和低点位服务。"
    return {
        "scenario_metadata": {"canonical": "fraud_im"},
        "core_analysis": {
            "scenario": "fraud_im",
            "is_fraud": True,
            "fraud_type": "unlicensed_financial_service",
            "risk_level": "high",
            "attack_stage": "private_contact_lure",
            "asset_targets": [{"type": "funds", "label": "代还资金"}],
            "fork_points": [{"type": "private_contact_lure", "reason": "要求通过微信转入私人渠道"}],
            "intervention_window": {"start_turn": 0, "end_turn": 1},
            "expected_warning": "不要转入对方指定的私人渠道",
            "expected_safe_action": "通过发卡行官方渠道核验",
            "evidence_spans": ["微信", "刷卡和低点位服务"],
            "confidence": 0.8,
        },
        "benchmark_prediction": {"risk_level": "low", "fraud_type": "must_not_be_read"},
        "metrics": {},
    }


def test_final_fraud_wording_maps_machine_types_and_binds_minimal_evidence():
    response = build_conversational_response(
        result=_fraud_result(),
        user_message="信用卡代还广告要求通过微信联系，提供刷卡和低点位服务。",
    )
    message = response["assistant_message"]
    assert "unlicensed_financial_service" not in message
    assert "风险风险" not in message
    assert "微信" in message
    assert "原文" in message


def test_report_state_has_scenario_specific_fraud_fields():
    state = build_report_state(_fraud_result())
    assert set(("risk_type", "attack_stage", "evidence_spans", "recommended_actions")) <= set(state["fraud"])
    assert state["provenance"]["has_oasis_counterfactual_branches"] is False


def test_reporter_quotes_observed_input_not_synthetic_risk_graph_phrases():
    result = _fraud_result()
    result["core_analysis"]["evidence_spans"] = [
        {"text": "原始聊天证据", "source": "canonical_case"},
        {"text": "合成策略模板", "source": "risk_graph"},
    ]
    state = build_report_state(result)
    assert state["evidence"] == ["原始聊天证据"]


def test_benchmark_adapter_does_not_reclassify_post_disconnect_text():
    text = "对方收款后把我拉黑，微信无法联系。"
    result = _fraud_result()
    result["core_analysis"]["attack_stage"] = "post_fraud"
    payload = build_benchmark_payload(result=result, scenario_text=text, scenario_type="fraud_im")
    assert payload["prediction"]["attack_stage"] == "post_fraud"


def test_scam_term_养卡_is_preserved_as_evidence():
    result = PrivacySanitizer(enabled=False).sanitize("提供刷卡、养卡和低点位服务")
    assert result.sanitized_text == "提供刷卡、养卡和低点位服务"
