from app.modules.dialogue_attribution import attribute_dialogue, build_preview_graph
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


def test_greeting_reply_introduces_mirofish():
    reply = compose_chat_reply("你好", {"model": "deterministic_guard", "scenario": ""}, {})
    assert reply["style"] == "greeting"
    assert "MiroCogSec" in reply["lead"]
    assert reply["show_feature_cards"] is True


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


def test_preview_graph_keeps_absent_victim():
    attribution = attribute_dialogue("我是秦始皇，打钱")
    graph = build_preview_graph(
        "我是秦始皇，打钱",
        attribution,
        {"scenario_type": "fraud_im", "extracted_summary": "冒充权威索财"},
    )
    labels = [node["label"] for node in graph["nodes"]]
    assert "受害人（未发言）" in labels
    assert all("label" in node for node in graph["nodes"])
    relations = [edge["relation"] for edge in graph["edges"]]
    assert "未见应答" in relations
