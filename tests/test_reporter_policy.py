from __future__ import annotations

from app.modules.conversational_response import build_conversational_response
from app.modules.reporter_policy import generate_reporter_answer, validate_reporter_text
from app.modules.report_state import build_report_state
from app.modules.response_planner import build_response_plan
from app.services.cogsec_service import _fraud_threat_level


class FakeReporterClient:
    model = "fake-reporter"

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def chat(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


class MetadataReporterClient(FakeReporterClient):
    model = "reasoning-reporter"

    def __init__(self, responses, metadata):
        super().__init__(responses)
        self._metadata = list(metadata)
        self.last_response_metadata = {}

    def chat(self, **kwargs):
        value = super().chat(**kwargs)
        self.last_response_metadata = self._metadata.pop(0)
        return value


def _result() -> dict:
    return {
        "scenario_metadata": {"canonical": "fraud_im"},
        "core_analysis": {
            "fraud_type": "private_contact_lure",
            "risk_level": "high",
            "attack_stage": "initial_contact",
            "asset_targets": ["支付资金"],
            "fork_points": [
                {
                    "type": "private_contact_lure",
                    "reason": "对方要求离开平台并转到私人微信，平台核验和追责能力下降。",
                }
            ],
            "expected_warning": "先不要添加私人微信或付款。",
            "expected_safe_action": "在原平台核验发布者身份并举报可疑广告。",
            "evidence_spans": [
                {"text": "留下微信联系", "source": "canonical_case"},
            ],
            "provenance": {"metric_source": "runtime"},
        },
    }


def test_llm_reporter_is_same_response_path_and_receives_no_benchmark_payload() -> None:
    client = FakeReporterClient([
        "这条广告的主要风险不只是商品本身，而是它要求你转到私人微信继续交易。先不要添加或付款；留在原平台核验发布者身份，并保留广告页面用于举报。"
    ])
    result = _result()
    result["benchmark_prediction"] = {"gold_like_field": "must not enter prompt"}

    response = build_conversational_response(
        result=result,
        user_message="帮我判断这条广告",
        reporter_client=client,
        reporter_mode="main_llm",
    )

    assert response["assistant_message"].startswith("这条广告")
    assert response["reporter_provenance"]["backend"] == "main_llm"
    assert response["reporter_provenance"]["fallback_used"] is False
    prompt = str(client.calls[0]["messages"])
    assert "must not enter prompt" not in prompt
    assert "benchmark_prediction" not in prompt


def test_invalid_llm_reporter_retries_then_uses_visible_fallback() -> None:
    client = FakeReporterClient(["{}", "```json\n{}\n```"])
    response = build_conversational_response(
        result=_result(),
        reporter_client=client,
        reporter_mode="main_llm",
    )

    assert response["assistant_message"].startswith("结论：")
    provenance = response["reporter_provenance"]
    assert provenance["fallback_used"] is True
    assert provenance["retry_count"] == 1
    assert provenance["fallback_reason"] == "machine_format_leaked"
    assert len(client.calls) == 2


def test_length_truncated_reporter_is_retried_with_more_budget() -> None:
    client = MetadataReporterClient(
        [
            "这是第一版回答，但在关键建议处被截断",
            "这条信息存在较高风险。请先暂停付款，并通过平台官方入口核验发布者身份。",
        ],
        [
            {"finish_reason": "length", "completion_tokens": 300, "model": "reasoning-reporter"},
            {"finish_reason": "stop", "completion_tokens": 80, "model": "reasoning-reporter"},
        ],
    )
    result = generate_reporter_answer(
        report_state={"scenario": "fraud_im", "evidence": ["要求先付款"]},
        response_plan={"recommendations": ["暂停付款"]},
        user_message="帮我判断",
        tone="friendly",
        deterministic_fallback=lambda: "当前信息不足，请暂停操作并核验。",
        mode="remote_model",
        client=client,
        max_tokens=600,
    )

    assert result.assistant_message.endswith("。")
    assert result.provenance["backend"] == "remote_model"
    assert result.provenance["retry_count"] == 1
    assert result.provenance["finish_reason"] == "stop"
    assert client.calls[0]["max_tokens"] == 600
    assert client.calls[1]["max_tokens"] == 1000


def test_internal_agent_action_token_is_not_allowed_in_user_answer() -> None:
    valid, reason = validate_reporter_text("建议优先处理 identity_asset_exchange 并及时核验。")
    assert valid is False
    assert reason == "internal_action_token_leaked"


def test_reporter_cannot_promise_unavailable_followup_service() -> None:
    valid, reason = validate_reporter_text("请先通过官方渠道核验。我们将持续关注并提供支持。")
    assert valid is False
    assert reason == "unsupported_followup_promise"


def test_low_risk_fraud_cannot_be_rewritten_as_confirmed_scam() -> None:
    state = {
        "scenario": "fraud_im",
        "summary": {"risk_level": "low"},
        "evidence": ["公开招投标公告列出了项目联系人和发布时间。"],
    }
    valid, reason = validate_reporter_text(
        "这是一条典型诈骗信息，请立即停止操作并报警。",
        report_state=state,
        user_message="请判断这则公开公告。",
    )
    assert valid is False
    assert reason == "low_risk_overclaim"


def test_low_risk_fraud_uses_neutral_guardrail_before_remote_generation() -> None:
    state = {
        "scenario": "fraud_im",
        "summary": {"risk_level": "low"},
        "evidence": ["这是一则公开招投标公告。"],
    }
    client = FakeReporterClient([
        "这是一条典型诈骗信息，请立即报警处理。",
        "该骗局可能继续索要验证码，应立即报警。",
    ])
    result = generate_reporter_answer(
        report_state=state,
        response_plan={},
        user_message="帮我看看公告。",
        tone="friendly",
        deterministic_fallback=lambda: "旧兜底错误地判定为诈骗。",
        mode="remote_model",
        client=client,
    )
    assert "没有足够证据" in result.assistant_message
    assert "把它判定为诈骗" in result.assistant_message
    assert result.provenance["fallback_used"] is False
    assert result.provenance["guardrail_applied"] is True
    assert result.provenance["backend"] == "deterministic_guardrail"
    assert client.calls == []


def test_observed_payment_request_bypasses_low_risk_guardrail() -> None:
    client = FakeReporterClient([
        "广告要求先交包装费和通道费，并承诺无需征信保证下卡，这是明确的高风险收费信号。不要付款，应直接通过银行官方渠道核验。"
    ])
    state = {
        "scenario": "fraud_im",
        "summary": {"risk_level": "low"},
        "evidence": ["广告称无需征信也能办高额信用卡，先交包装费和通道费，保证下卡。"],
    }
    result = generate_reporter_answer(
        report_state=state,
        response_plan={},
        user_message="帮我判断这则办卡广告。",
        tone="friendly",
        deterministic_fallback=lambda: "请核验。",
        mode="remote_model",
        client=client,
    )
    assert result.provenance["guardrail_applied"] is False
    assert result.provenance["backend"] == "remote_model"
    assert len(client.calls) == 1


def test_proxy_event_payload_hides_synthetic_trace_and_metrics() -> None:
    client = FakeReporterClient([
        "原文说明高影响力账号加入判断性措辞后放大了未经证实的信息。建议核实首发来源，并把更正同步到原帖和主要转发链。"
    ])
    state = {
        "scenario": "event_propagation",
        "summary": {"risk_level": "medium"},
        "evidence": ["高影响力账号加入判断性措辞后放大了未经证实的信息。"],
        "event_propagation": {
            "original_claim": "高影响力账号加入判断性措辞后放大了未经证实的信息。",
            "mutation_steps": [{"source_agent_id": "SYNTH_002", "claim_fidelity_after": 0.136}],
            "containment_action": "继续监测主要转发链。",
        },
        "selected_actions": [{
            "candidate_id": "cand_1",
            "best_intervention_action": "继续监测主要转发链。",
            "target_nodes": ["SYNTH_002"],
            "score_breakdown": {"total_score": 0.5},
        }],
        "provenance": {
            "metric_source": "proxy",
            "has_oasis_counterfactual_branches": False,
        },
    }
    result = generate_reporter_answer(
        report_state=state,
        response_plan={},
        user_message="请分析这条未经证实的信息如何传播。",
        tone="friendly",
        deterministic_fallback=lambda: "当前没有明显误传证据，建议继续核验。",
        mode="remote_model",
        client=client,
    )
    prompt = str(client.calls[0]["messages"])
    assert "SYNTH_002" not in prompt
    assert "0.136" not in prompt
    assert "mutation_steps" not in prompt
    assert result.provenance["fallback_used"] is False


def test_explicit_no_distortion_uses_observation_guardrail_before_proxy_reporter() -> None:
    client = FakeReporterClient(["不应调用"])
    state = {
        "scenario": "event_propagation",
        "summary": {"risk_level": "medium"},
        "evidence": ["官方预警被完整转发，未出现明显地点误传或断章取义。"],
        "provenance": {"metric_source": "proxy", "has_oasis_counterfactual_branches": False},
    }
    result = generate_reporter_answer(
        report_state=state,
        response_plan={},
        user_message="请判断传播风险。",
        tone="friendly",
        deterministic_fallback=lambda: "旧兜底错误地声称发生严重失真。",
        mode="remote_model",
        client=client,
    )
    assert "没有明显" in result.assistant_message
    assert "不宜把它直接定性" in result.assistant_message
    assert result.provenance["guardrail_applied"] is True
    assert client.calls == []


def test_explicitly_stable_public_discussion_overrides_proxy_emotion_signal() -> None:
    client = FakeReporterClient(["不应调用"])
    state = {
        "scenario": "public_opinion",
        "summary": {"risk_level": "medium"},
        "evidence": ["新闻已由多家可靠媒体确认，评论以理性分析为主，未出现未经证实爆料或强烈情绪动员。"],
        "provenance": {"metric_source": "proxy", "has_oasis_counterfactual_branches": False},
    }
    result = generate_reporter_answer(
        report_state=state,
        response_plan={},
        user_message="请判断当前舆论风险。",
        tone="friendly",
        deterministic_fallback=lambda: "旧兜底声称风险很高。",
        mode="remote_model",
        client=client,
    )
    assert "整体平稳" in result.assistant_message
    assert "没有足够证据支持中高风险" in result.assistant_message
    assert result.provenance["guardrail_applied"] is True
    assert client.calls == []


def test_proxy_event_cannot_contradict_explicit_no_distortion_evidence() -> None:
    state = {
        "scenario": "event_propagation",
        "summary": {"risk_level": "medium"},
        "evidence": ["未出现明显地点误传或断章取义。"],
        "provenance": {"metric_source": "proxy", "has_oasis_counterfactual_branches": False},
    }
    valid, reason = validate_reporter_text(
        "多轮传播后内容完整性正在显著下降，应立即定向处置。",
        report_state=state,
    )
    assert valid is False
    assert reason == "contradicts_observed_evidence"


def test_trained_policy_without_checkpoint_never_claims_trained_inference() -> None:
    result = generate_reporter_answer(
        report_state={"scenario": "fraud_im"},
        response_plan={},
        user_message="",
        tone="friendly",
        deterministic_fallback=lambda: "当前信息不足，请先暂停操作并核验。",
        mode="trained_policy",
        client=FakeReporterClient(["不会被调用的回答"]),
        checkpoint_path=None,
    )

    assert result.provenance["trained_policy_used"] is False
    assert result.provenance["fallback_reason"] == "trained_reporter_checkpoint_missing"


def test_direct_llm_answer_is_not_rewritten_by_miro_template() -> None:
    direct = "原生模型回答：先暂停付款，并通过订单页中的官方入口核验。"
    result = generate_reporter_answer(
        report_state={
            "scenario": "fraud_im",
            "is_direct_llm_baseline": True,
            "direct_llm": {"assistant_message": direct},
        },
        response_plan={},
        user_message="",
        tone="friendly",
        deterministic_fallback=lambda: "不应出现",
        mode="auto",
        client=None,
    )

    assert result.assistant_message == direct
    assert result.provenance["policy_mode"] == "direct_llm_passthrough"


def test_fraud_threat_is_not_diluted_by_persona_outcome_score() -> None:
    assert _fraud_threat_level(
        forks=[{"type": "private_contact_lure"}, {"type": "transfer_money"}],
        fallback="low",
    ) == "high"

    state = build_report_state({
        "scenario_metadata": {"canonical": "fraud_im"},
        "core_analysis": {
            "fraud_type": "fraud_im",
            "risk_level": "high",
            "threat_level": "high",
            "personalized_outcome_risk_level": "low",
            "fork_points": [{"type": "transfer_money"}],
            "evidence_spans": [{"text": "先转保证金", "source": "canonical_case"}],
        },
    })
    plan = build_response_plan(result={"report_state": state}, tone="expert")

    assert state["summary"]["risk_level"] == "high"
    assert state["fraud"]["personalized_outcome_risk_level"] == "low"
    assert plan["primary_risk"] == "high"
    assert "分开报告" in " ".join(plan["mechanism"])
