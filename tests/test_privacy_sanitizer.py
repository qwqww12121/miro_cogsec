"""PrivacySanitizer 测试。"""

from modules.privacy_sanitizer import PrivacySanitizer


def test_privacy_sanitizer_masks_phone_and_bank_card():
    sanitizer = PrivacySanitizer(enabled=False)
    text = "我的手机号是13800138000，银行卡6222021234567890123，请帮我处理。"
    result = sanitizer.sanitize(text)

    assert "某手机号" in result.sanitized_text
    assert "某银行卡" in result.sanitized_text
    assert len(result.entities) >= 2
