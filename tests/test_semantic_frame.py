"""Semantic-frame validation tests."""

from modules.semantic_frame import validate_semantic_frame


def test_validate_semantic_frame_keeps_only_exact_source_spans():
    text = "帖子说可以绕过平台审核取得内部名额，要求先提交账户截图。"
    frame = {
        "risk_level": "high",
        "is_harmful": True,
        "evidence_spans": ["绕过平台审核", "不存在的外部事实"],
        "claims": [
            {
                "claim": "要求提交账户截图",
                "evidence_spans": ["要求先提交账户截图", "伪造证据"],
            }
        ],
    }

    validated = validate_semantic_frame(frame, text=text, scenario="fraud_im")

    assert validated["evidence_spans"] == ["绕过平台审核", "要求先提交账户截图"]
    assert validated["claims"][0]["evidence_spans"] == ["要求先提交账户截图"]
