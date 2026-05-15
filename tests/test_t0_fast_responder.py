"""T0FastResponder 测试。"""

from modules.t0_fast_responder import T0FastResponder


def test_t0_fast_responder_detects_required_patterns():
    responder = T0FastResponder()
    text = "对方说你要共享屏幕并提供银行卡验证码，还要转到安全账户，且不要告诉家人。"
    result = responder.scan(text)

    assert result["alert"] is True
    assert result["target_met"] is True
    assert any(item["rule_id"] == "screen_share_bank_card" for item in result["hits"])
    assert any(item["rule_id"] == "safe_account_transfer" for item in result["hits"])
