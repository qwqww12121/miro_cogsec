from app.modules.dialogue_attribution import attribute_dialogue, build_preview_graph, build_thinking_steps
from app.modules.chat_composer import compose_chat_reply


def test_qin_shihuang_is_offender_monologue():
    result = attribute_dialogue("我是秦始皇，打钱")
    assert result.victim_present is False
    assert result.split_method == "suspect_only"
    assert result.utterances[0].speaker == "suspect"
    assert "受害人" in result.summary or any("受害人" in item for item in result.caveats)


def test_prefixed_dialogue_split():
    result = attribute_dialogue("骗子：我是客服。\n受害人：好的我转。")
    assert result.split_method == "role_prefix"
    assert [item.speaker for item in result.utterances] == ["suspect", "victim"]
    assert result.victim_present is True


def test_out_of_scope_reply_does_not_jump_to_scene():
    reply = compose_chat_reply(
        "107 Agent Hackathon Casebook 规划案",
        {
            "model": "deterministic_out_of_scope",
            "recognition_status": "out_of_scope",
            "reason": "规划文档",
            "extracted_summary": "案例集",
        },
        {},
    )
    assert reply["style"] == "out_of_scope"
    assert reply["primary_scene"] == ""
    blob = " ".join(reply["paragraphs"]) + " ".join(
        item for section in reply["sections"] for item in (section.get("items") or [])
    )
    assert "FORK" not in blob
    assert "OASIS" not in blob
    assert "未调用" not in blob
    reply = compose_chat_reply("你好", {"model": "deterministic_guard", "scenario": ""}, {})
    assert reply["style"] == "greeting"
    assert "MiroCogSec" in reply["lead"]
    assert reply["show_feature_cards"] is True


def test_unknown_reply_uses_triptych_fallback():
    reply = compose_chat_reply(
        "先看看你的三个能力",
        {
            "scenario_type": "unknown",
            "recognition_status": "unknown",
            "confidence": 0.1,
            "model": "deepseek-v4-flash",
            "reason": "输入没有提供具体认知安全材料。",
            "extracted_summary": "用户希望了解系统能力。",
        },
        {},
    )
    assert reply["style"] == "unknown"
    assert reply["primary_scene"] == "unknown"
    assert len(reply["sections"]) == 3


def test_fraud_reply_is_conversational_and_flags_unspoken_victim():
    text = "张同学，你的国家奖学金已批准，请把验证码发给教务处老师，不要问辅导员。"
    reply = compose_chat_reply(
        text,
        {
            "scenario_type": "fraud_im",
            "confidence": 0.9,
            "model": "local_rule",
            "extracted_summary": "奖学金诈骗",
            "extracted_fields": {"suspect_identity": "教务处老师"},
            "reason": "索要验证码并隔离辅导员",
        },
        attribute_dialogue(text),
    )
    assert reply["style"] == "fraud_im"
    assert "学生" in reply["lead"] or "奖学金" in reply["lead"]
    assert any("还没有开口" in item or "先验" in item for item in reply["paragraphs"])
    assert len(reply["paragraphs"]) >= 2
    assert "现在最该做的" in (reply["sections"][0].get("heading") or "")


def test_thinking_points_to_scene_analysis_without_unused_modules():
    steps = build_thinking_steps(
        "我是秦始皇，打钱",
        attribute_dialogue("我是秦始皇，打钱"),
        {"scenario_type": "fraud_im", "reason": "身份冒充"},
    )
    titles = [item["title"] for item in steps]
    assert "下一步：进入场景分析" in titles
    next_step = next(item for item in steps if item["id"] == "fork")
    blob = next_step["summary"] + " ".join(next_step["details"])
    assert "未调用" not in blob
    assert "不会启动" not in blob
    assert "OASIS" not in blob
    assert "FORK" not in blob
    attribution = attribute_dialogue("我是秦始皇，打钱")
    graph = build_preview_graph(
        "我是秦始皇，打钱",
        attribution,
        {"scenario_type": "fraud_im", "extracted_summary": "冒充权威索财"},
    )
    labels = [node["label"] for node in graph["nodes"]]
    assert "受害人（未发言）" in labels
    relations = [edge["relation"] for edge in graph["edges"]]
    assert "未见应答" in relations


def test_opinion_and_event_thinking_omit_unused_module_copy():
    for scenario in ("public_opinion", "event_propagation"):
        steps = build_thinking_steps(
            "食堂涨价在班级群和表白墙被转发",
            attribute_dialogue("食堂涨价在班级群和表白墙被转发"),
            {"scenario_type": scenario, "reason": "公共讨论扩散"},
        )
        blob = " ".join(
            f"{item.get('title') or ''} {item.get('summary') or ''} {' '.join(item.get('details') or [])}"
            for item in steps
        )
        assert "OASIS" not in blob
        assert "FORK" not in blob
        assert "未调用" not in blob
        assert "未接入" not in blob
