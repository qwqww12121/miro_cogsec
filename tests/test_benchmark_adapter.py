"""Benchmark adapter boundary regressions.

The adapter is an exporter, not a second classifier.  These tests deliberately
avoid asserting keyword-triggered benchmark answers.
"""

from copy import deepcopy

from app.modules.benchmark_adapter import build_benchmark_payload


def _fraud_state():
    return {
        "schema_version": "report_state.v2",
        "scenario": "fraud_im",
        "summary": {"text": "私人渠道付款诱导", "risk_level": "high"},
        "evidence": ["通过微信联系", "先支付保证金"],
        "fraud": {
            "risk_type": "private_contact_lure",
            "current_stage": "pre_payment",
            "requested_assets": [{"type": "funds", "label": "保证金"}],
            "critical_transitions": [{"type": "transfer_money", "reason": "核验前付款"}],
            "recommended_actions": ["不要继续付款", "通过独立官方渠道核验"],
            "recommended_timing": {"start_turn": 0, "end_turn": 1},
            "evidence_spans": ["通过微信联系", "先支付保证金"],
            "confidence": 0.82,
        },
        "selected_actions": [],
        "counterfactual_effect": {"risk_reduction": 0.4},
        "field_provenance": {},
        "provenance": {"metric_source": "runtime"},
    }


def test_adapter_maps_canonical_runtime_state():
    payload = build_benchmark_payload(
        result={"report_state": _fraud_state()},
        scenario_text="raw input is intentionally irrelevant here",
        scenario_type="fraud_im",
    )
    prediction = payload["prediction"]
    assert prediction["fraud_type"] == "private_contact_lure"
    assert prediction["risk_level"] == "high"
    assert prediction["expected_safe_action"] == "通过独立官方渠道核验"
    assert payload["provenance"]["raw_input_used"] is False
    assert payload["adapter_diagnostics"]["inference_pass"]["used"] is False


def test_raw_keyword_or_paraphrase_cannot_change_exported_prediction():
    state = _fraud_state()
    first = build_benchmark_payload(
        result={"report_state": deepcopy(state)},
        scenario_text="先支付保证金并添加微信",
        scenario_type="fraud_im",
    )["prediction"]
    second = build_benchmark_payload(
        result={"report_state": deepcopy(state)},
        scenario_text="一段完全不同且没有关键词的改写",
        scenario_type="fraud_im",
    )["prediction"]
    assert first == second


def test_empty_runtime_remains_unknown_instead_of_guessing_from_text():
    payload = build_benchmark_payload(
        result={"scenario_metadata": {"canonical": "fraud_im"}},
        scenario_text="可以买实名手机卡，留下微信联系",
        scenario_type="fraud_im",
    )
    assert payload["prediction"]["fraud_type"] == "unknown"
    assert payload["prediction"]["is_fraud"] is False
    assert "fraud_type" in payload["adapter_diagnostics"]["empty_fields"]


def test_public_state_exports_selected_runtime_intervention():
    state = {
        "schema_version": "report_state.v2",
        "scenario": "public_opinion",
        "summary": {"text": "多个叙事竞争", "risk_level": "medium"},
        "evidence": ["来源尚未确认"],
        "public_opinion": {
            "narrative_threads": [{"claim": "说法 A"}],
            "uncertainty_points": [{"description": "来源不明"}],
            "source_status": {"status": "investigation_pending"},
            "polarization_signal": {"dominant_emotion": "confusion"},
            "intervention_timing": {"open_stage": "early"},
            "confidence": 0.7,
        },
        "selected_actions": [{"action": "补充原始来源与核验状态"}],
        "field_provenance": {},
        "provenance": {"metric_source": "proxy"},
    }
    prediction = build_benchmark_payload(
        result={"report_state": state}, scenario_text="unused", scenario_type="public_opinion"
    )["prediction"]
    assert prediction["event_summary"] == "多个叙事竞争"
    assert prediction["expected_intervention_action"] == "补充原始来源与核验状态"


def test_event_state_exports_actor_local_propagation_fields():
    state = {
        "schema_version": "report_state.v2",
        "scenario": "event_propagation",
        "summary": {"text": "限定条件在转发中丢失", "risk_level": "high"},
        "evidence": ["限定条件被裁掉"],
        "event_propagation": {
            "original_claim": "原消息带有限定条件",
            "source_nodes": [{"id": "actor-1", "description": "首发节点"}],
            "amplifier_nodes": [{"id": "actor-2"}],
            "cross_platform_path": [{"from": "actor-1", "to": "actor-2"}],
            "lost_context": [{"description": "限定条件丢失"}],
            "containment_timing": {"open_step": 1},
            "containment_action": "把更正绑定回原传播链",
            "confidence": 0.8,
        },
        "selected_actions": [],
        "field_provenance": {},
        "provenance": {"metric_source": "simulation_proxy"},
    }
    prediction = build_benchmark_payload(
        result={"report_state": state}, scenario_text="unused", scenario_type="event_propagation"
    )["prediction"]
    assert prediction["origin_node"]["id"] == "actor-1"
    assert prediction["distortion_points"][0]["description"] == "限定条件丢失"
    assert prediction["expected_containment_action"] == "把更正绑定回原传播链"
