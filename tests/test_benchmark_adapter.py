"""Benchmark adapter regression tests."""

from modules.benchmark_adapter import build_benchmark_payload
import modules.benchmark_adapter as benchmark_adapter


def test_benign_download_text_is_not_forced_into_fraud_flow():
    payload = build_benchmark_payload(
        result={},
        scenario_text="页面说明可下载河道治理施工合同电子版，供企业内部归档使用。",
        scenario_type="fraud_im",
    )
    prediction = payload["prediction"]

    assert prediction["is_fraud"] is False
    assert prediction["fraud_type"] == "no_fraud_signal"
    assert prediction["risk_level"] == "none"
    assert prediction["fork_points"] == []


def test_identity_asset_text_prefers_grounded_semantic_fork():
    payload = build_benchmark_payload(
        result={},
        scenario_text="广告称可以买到已实名激活手机卡，留下微信联系，强调多年老店和信誉第一。",
        scenario_type="fraud_im",
    )
    prediction = payload["prediction"]
    fork_types = {item["type"] for item in prediction["fork_points"]}

    assert prediction["fraud_type"] == "identity_asset_trade"
    assert "identity_asset_exchange" in fork_types
    assert "private_contact_lure" in fork_types
    assert "transfer_money" not in fork_types
    assert prediction["risk_level"] == "high"
    assert prediction["attack_stage"] == "initial_contact"
    assert prediction["intervention_window"]["start_turn"] == 0


def test_more_benign_public_info_is_not_flagged_as_fraud():
    benign_samples = [
        "酒店介绍私人会所、香薰理疗、棋牌室、游泳池和健身房等设施，满足游客休闲娱乐需求。",
        "建设工程信息公告列出相关公司、项目联系人和发布时间，内容为公开招投标信息。",
        "寻人启事说明老人走失地点、衣着特征和家属联系方式，请发现后及时联系家人。",
    ]
    for text in benign_samples:
        payload = build_benchmark_payload(result={}, scenario_text=text, scenario_type="fraud_im")
        prediction = payload["prediction"]
        assert prediction["is_fraud"] is False
        assert prediction["risk_level"] == "none"
        assert prediction["fork_points"] == []


def test_public_opinion_low_risk_negation_gate():
    payload = build_benchmark_payload(
        result={},
        scenario_text="公众讨论围绕一条已由多家可靠媒体确认的公开新闻展开。评论主要是信息补充、背景解释和理性讨论，未出现明显未经证实的爆料、强烈情绪动员或要求立即行动的呼吁。",
        scenario_type="public_opinion",
    )
    prediction = payload["prediction"]
    assert prediction["propagation_risk_level"] == "low"
    assert prediction["emotion_signal"]["dominant_emotion"] == "neutral"
    assert prediction["best_intervention_window"]["label"] == "无需干预"


def test_event_propagation_low_risk_negation_gate():
    payload = build_benchmark_payload(
        result={},
        scenario_text="官方应急账号发布一条天气预警更新，地方媒体和社区账号转发时保留了原始发布时间、影响区域和防护建议。后续讨论主要围绕交通安排和学校通知展开，未出现明显地点误传、时间误传或断章取义。",
        scenario_type="event_propagation",
    )
    prediction = payload["prediction"]
    assert prediction["coverage_risk"] == "low"
    assert prediction["distortion_points"] == []
    assert prediction["containment_window"]["label"] == "无需特殊遏制"


def test_semantic_frame_drives_fork_without_keyword_rules(monkeypatch):
    text = "帖子说可以绕过平台审核取得内部名额，要求先提交账户截图。"

    def fake_extract_semantic_frame(**_: object):
        return {
            "available": True,
            "scenario": "fraud_im",
            "risk_level": "high",
            "is_harmful": True,
            "risk_type": "account_access_lure",
            "summary": "对方以内部名额诱导用户提交账户截图。",
            "evidence_spans": ["绕过平台审核", "内部名额", "提交账户截图"],
            "assets": [
                {
                    "type": "account",
                    "description": "账户访问安全",
                    "severity": 0.82,
                    "evidence_spans": ["提交账户截图"],
                }
            ],
            "fork_candidates": [
                {
                    "type": "submit_account_artifact_vs_verify_platform",
                    "trigger": "用户是否在未核验来源前提交账户截图",
                    "unsafe_branch": ["相信内部名额", "提交账户截图", "账户信息暴露"],
                    "safe_branch": ["暂停提交", "回到平台官方渠道核验"],
                    "intervention_window": {
                        "start_turn": 0,
                        "end_turn": 1,
                        "rationale": "提交截图前仍可阻断。",
                    },
                    "evidence_spans": ["提交账户截图"],
                }
            ],
            "warning": "不要向无法核验的对象提交账户截图。",
            "safe_action": "停止提交截图，并通过平台官方渠道核验。",
            "confidence": 0.84,
            "provenance": {"source": "llm_semantic_frame", "model": "test"},
        }

    monkeypatch.setattr(benchmark_adapter, "extract_semantic_frame", fake_extract_semantic_frame)

    payload = build_benchmark_payload(result={}, scenario_text=text, scenario_type="fraud_im")
    prediction = payload["prediction"]

    assert prediction["fraud_type"] == "account_access_lure"
    assert prediction["fork_points"][0]["type"] == "submit_account_artifact_vs_verify_platform"
    assert prediction["counterfactual_paths"]["risky_path"][1]["action"] == "提交账户截图"
    assert payload["adapter_diagnostics"]["semantic_frame"]["used"] is True


def test_public_event_frame_drives_event_prediction(monkeypatch):
    text = "新闻被截取标题转发，原文限定条件被裁掉，新的讨论变得绝对化。"

    def fake_public_event_frame(**_: object):
        return {
            "available": True,
            "scenario": "event_propagation",
            "risk_level": "high",
            "summary": "新闻被截断后跨平台传播并失去限定条件。",
            "evidence_spans": ["截取标题转发", "原文限定条件被裁掉", "新的讨论变得绝对化"],
            "origin": {"description": "新闻原文", "evidence_spans": ["新闻"]},
            "amplifiers": [{"description": "截取标题转发者", "role": "personal", "evidence_spans": ["截取标题转发"]}],
            "propagation_steps": [
                {"step": 1, "actor": "转发者", "action": "截取标题", "transformation": "删除限定条件", "risk_state": "high", "evidence_spans": ["截取标题转发", "原文限定条件被裁掉"]}
            ],
            "distortion_points": [
                {"type": "context_loss", "description": "原文限定条件被裁掉", "severity": 0.8, "evidence_spans": ["原文限定条件被裁掉"]}
            ],
            "containment_plan": {
                "open_step": 1,
                "close_step": 2,
                "label": "上下文保留窗口",
                "actor_actions": [{"actor": "platform", "target_surface": "转发入口", "action": "提示补充原文链接", "expected_effect": "减少断章取义"}],
            },
            "provenance": {"source": "llm_public_event_frame", "model": "test"},
        }

    monkeypatch.setattr(benchmark_adapter, "extract_public_event_frame", fake_public_event_frame)
    monkeypatch.setattr(benchmark_adapter, "extract_semantic_frame", lambda **_: {"available": False, "provenance": {"source": "should_not_use"}})

    payload = build_benchmark_payload(result={}, scenario_text=text, scenario_type="event_propagation")
    prediction = payload["prediction"]

    assert prediction["coverage_risk"] == "high"
    assert prediction["distortion_points"][0]["description"] == "原文限定条件被裁掉"
    assert prediction["expected_containment_action"].startswith("平台在转发入口")
    assert payload["adapter_diagnostics"]["public_event_frame"]["used"] is True
