"""Public/event propagation semantic-frame tests."""

from modules.public_event_semantics import validate_public_event_frame


def test_public_event_frame_keeps_only_source_evidence():
    text = "新闻被截取标题转发，原文限定条件被裁掉，新的讨论变得绝对化。"
    frame = {
        "risk_level": "high",
        "summary": "争议新闻被截断传播。",
        "evidence_spans": ["截取标题转发", "外部不存在证据"],
        "distortion_points": [
            {
                "type": "context_loss",
                "description": "限定条件被裁掉",
                "severity": 0.8,
                "evidence_spans": ["原文限定条件被裁掉", "伪证据"],
            }
        ],
    }

    validated = validate_public_event_frame(frame, text=text, scenario="event_propagation")

    assert validated["evidence_spans"] == ["截取标题转发", "原文限定条件被裁掉"]
    assert validated["distortion_points"][0]["evidence_spans"] == ["原文限定条件被裁掉"]
