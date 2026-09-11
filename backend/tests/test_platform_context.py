from app.modules.opinion_shaping import shaping_plan, shaping_plain_answer
from app.modules.platform_context import detect_platform, public_opinion_lens
from app.modules.response_planner import _plan_event_propagation, _plan_fraud_im, _plan_public_opinion


def _joined(plan):
    return "\n".join(
        [
            str(plan.get("conclusion") or ""),
            *(plan.get("evidence") or []),
            *(plan.get("recommendations") or []),
            *(plan.get("mechanism") or []),
        ]
    )


def test_detect_platform_prefers_label():
    text = "[平台]抖音\n[话题]食堂涨价\n样本里也提到了微博热搜"
    assert detect_platform(text) == "抖音"


def test_public_opinion_lens_differs_by_platform():
    weibo = public_opinion_lens("微博")
    douyin = public_opinion_lens("抖音")
    xhs = public_opinion_lens("小红书")
    assert "转发链" in weibo[0]
    assert "推荐页" in douyin[0]
    assert "封面" in xhs[0]
    assert weibo[1] != douyin[1] != xhs[1]


def test_plan_public_opinion_changes_with_platform():
    topic = "[话题]食堂涨价\n[样本]\n看了这次官方回应，根本没回应核心问题"
    weibo = _plan_public_opinion({}, [], f"[平台]微博\n{topic}")
    douyin = _plan_public_opinion({}, [], f"[平台]抖音\n{topic}")
    xhs = _plan_public_opinion({}, [], f"[平台]小红书\n{topic}")
    weibo_text = _joined(weibo)
    douyin_text = _joined(douyin)
    xhs_text = _joined(xhs)
    assert "当前观察场是微博" in weibo["conclusion"]
    assert "当前观察场是抖音" in douyin["conclusion"]
    assert "当前观察场是小红书" in xhs["conclusion"]
    assert "转发链" in weibo_text and "热搜" in weibo_text
    assert "短视频" in douyin_text or "推荐封面" in douyin_text
    assert "笔记" in xhs_text
    assert weibo_text != douyin_text
    assert douyin_text != xhs_text
    assert weibo_text != xhs_text


def test_shaping_plan_changes_with_platform():
    weibo = shaping_plain_answer("微博")
    douyin = shaping_plain_answer("抖音")
    assert "当前观察场是微博" in weibo
    assert "当前观察场是抖音" in douyin
    assert "转发链" in weibo
    assert "短视频" in douyin or "推荐封面" in douyin
    assert weibo != douyin
    assert "不是代写爆款帖" in shaping_plan("微博")["conclusion"]


def test_event_and_fraud_plans_use_channel():
    event_weibo = _plan_event_propagation({}, [], "[渠道]微博\n[事件]食堂涨价")
    event_dy = _plan_event_propagation({}, [], "[渠道]抖音\n[事件]食堂涨价")
    assert "微博" in event_weibo["conclusion"]
    assert "抖音" in event_dy["conclusion"]
    assert _joined(event_weibo) != _joined(event_dy)

    fraud_wx = _plan_fraud_im({}, [], "[平台]微信\n骗子：把验证码发给我")
    fraud_sms = _plan_fraud_im({}, [], "[平台]短信\n骗子：点这个链接")
    assert "微信" in fraud_wx["conclusion"]
    assert any("短信" in item for item in (fraud_sms["recommendations"] + fraud_sms["evidence"]))
    assert _joined(fraud_wx) != _joined(fraud_sms)
