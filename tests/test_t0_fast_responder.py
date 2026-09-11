"""T0FastResponder 测试。"""

from modules.t0_fast_responder import T0FastResponder


def test_t0_fast_responder_detects_required_patterns():
    responder = T0FastResponder()
    text = "对方说你要共享屏幕并提供银行卡验证码，还要转账到安全账户，且不要告诉家人。"
    result = responder.scan(text)

    assert result["alert"] is True
    assert result["matched"] is True
    assert result["target_met"] is True
    assert "screen_share_bank_card" in result["matched_patterns"]
    assert any(item["rule_id"] == "screen_share_bank_card" for item in result["hits"])
    assert any(item["rule_id"] == "safe_account_transfer" for item in result["hits"])


def test_t0_detects_classic_impersonation_and_credit_card_lure():
    responder = T0FastResponder(patterns_path=None)
    opening = responder.scan("我是秦始皇")
    loan = responder.scan("广告称本地信用卡代还，我同意了")

    assert opening["matched"] is True
    assert "classic_impersonation_opening" in opening["matched_patterns"]
    assert loan["matched"] is True
    assert "credit_card_repay_lure" in loan["matched_patterns"]
