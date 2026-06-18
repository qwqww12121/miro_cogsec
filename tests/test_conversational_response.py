from __future__ import annotations

from app.modules.conversational_response import (
    answer_followup_from_state,
    build_conversational_response,
)
from app.modules.propagation.intervention_search import run_oasis_counterfactual_intervention_search


def _public_result() -> dict:
    text = "公开讨论迅速发酵，评论区出现愤怒表达、未经证实的目击叙述和要求官方立即公布细节的呼声。"
    search = run_oasis_counterfactual_intervention_search(
        scenario_type="public_opinion",
        seed_text=text,
        risk_graph_bundle={
            "nodes": [{"id": "risk:public", "label": "舆论风险"}],
            "links": [],
            "evidence_items": [{"label": "未经证实", "matched_terms": ["未经证实", "愤怒"]}],
        },
        quick_mode=True,
    )
    return {
        "profile": {"scenario_type": "public_opinion"},
        "scenario_metadata": {"canonical": "public_opinion"},
        "risk_graph_bundle": {
            "nodes": [{"id": "risk:public", "label": "舆论风险", "risk": 0.7}],
            "links": [{"source": "risk:public", "target": "node:official", "relation": "mitigated_by"}],
        },
        "benchmark_prediction": {
            "event_summary": "公共讨论迅速发酵",
            "emotion_signal": {"dominant_emotion": "anger", "amplification_level": "high"},
            "official_response_gap": {"description": "讨论已经扩散，但权威事实说明尚不足以稳定叙事。"},
            "uncertainty_points": [{"description": "流传说法仍缺少可复核证据。"}],
            "propagation_risk_level": "high",
            "expected_intervention_action": "发布时间线、证据状态和后续调查流程。",
            "expected_safe_public_action": "避免转发未经证实的信息，等待多源确认。",
            "evidence_spans": ["未经证实的目击叙述", "要求官方立即公布细节"],
        },
        "cogsec_analysis": {
            "evidence_trace": [
                {"id": "ev:1", "text": "未经证实的目击叙述", "source": "input_text"},
                {"id": "ev:2", "text": "要求官方立即公布细节", "source": "input_text"},
            ],
            "provenance": {"source": "mirofish_pipeline", "metric_source": "proxy"},
        },
        "scenario_extension": {
            "detection": {"canonical": "public_opinion"},
            "propagation_intervention_search": search,
        },
        "metrics": {"t0_latency_ms": 12.5, "end_to_end_ms": 850.0},
    }


def test_build_judge_friendly_response_has_compatible_fields() -> None:
    response = build_conversational_response(
        result=_public_result(),
        user_message="请分析这个舆论事件",
        tone="judge_friendly",
    )

    assert response["assistant_message"].startswith("结论：")
    assert "benchmark" not in response["assistant_message"].lower()
    assert response["response_plan"]["tone"] == "judge_friendly"
    assert response["graph_payload"]["graph_mode"] == "public_opinion"
    assert response["latency_profile"]["metric_source"] == "proxy"
    assert response["conversation_state"]["has_cached_analysis"] is True


def test_followup_answer_reuses_cached_state() -> None:
    first = build_conversational_response(result=_public_result(), tone="friendly")
    followup = answer_followup_from_state(
        state=first["conversation_state"],
        user_message="证据是什么？",
        tone="friendly",
    )

    assert followup is not None
    assert followup["response_plan"]["reused_state"] is True
    assert followup["latency_profile"]["pipeline_rerun"] is False
    assert "证据" in followup["assistant_message"]
