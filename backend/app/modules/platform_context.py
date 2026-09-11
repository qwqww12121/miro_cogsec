"""Map an explicit platform/channel choice onto distinct analysis actions."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

PLATFORM_LABELS = ("微博", "抖音", "小红书", "知乎", "多平台聚合", "跨平台", "微信", "QQ", "短信")

_WINDOW = {
    "6h": "最近 6 小时",
    "24h": "最近 24 小时",
    "7d": "最近 7 天",
}

_PUBLIC = {
    "微博": (
        "传播主要靠转发链、热搜和超话，一条原帖被包装后会迅速离开现场。",
        [
            "先核对本条微博和转发链，而不是只看截图。",
            "官方说明应发在原帖评论置顶，并同步长文，而不是另开一条没人看到的通报。",
            "热搜词和超话标题若已变形，要单独标注「已确认 / 仍在核实」。",
        ],
    ),
    "抖音": (
        "传播主要靠推荐页和几秒钩子，评论置顶会比长文先被刷到。",
        [
            "先看同一条作品的推荐封面、文案和置顶评论，而不是另找一篇通稿。",
            "澄清要用短视频或原作品置顶评论回到同一条，避免只发图文没人刷到。",
            "同款 BGM、话题标签若在带跑说法，要和原作品分开核对。",
        ],
    ),
    "小红书": (
        "传播主要靠封面、标题和搜索词，很多人没看完正文就会转。",
        [
            "先核对笔记封面、标题和标签，不要只引用最冲的一句。",
            "澄清要发能搜到的笔记，覆盖同一批标签，而不是只在评论区吵架。",
            "把种草口吻和能核对的价格、时间、出处拆开写。",
        ],
    ),
    "知乎": (
        "传播主要靠高赞回答和问题页，立场帖容易被当成论证。",
        [
            "先看原问题下的高赞回答是在举证还是在带节奏。",
            "澄清应发在原问题下，并标明来源，而不是只发一条想法。",
            "把仍待核实的部分单独标出，避免被当成又一篇立场文。",
        ],
    ),
    "多平台聚合": (
        "同一套说法会在不同平台换成各自的体裁，不能假设已经传成同一版本。",
        [
            "先分别核对微博、短视频和社区里的主帖，不要混成一条。",
            "每个平台用该平台习惯的澄清方式，再交叉核验数字和时间。",
            "缺来源的版本单独标成未证实，不要用一个平台的热度证明另一个平台的事实。",
        ],
    ),
}

_CHANNEL = {
    **_PUBLIC,
    "跨平台": _PUBLIC["多平台聚合"],
}

_FRAUD = {
    "微信": "回到微信官方入口或公开电话核对，不要按对方给的搜索词走。",
    "QQ": "回到 QQ 官方客服或机构公开账号核对，不要在临时会话里继续。",
    "短信": "回拨官方号码或打开官方 App，不要点短信里的链接。",
    "电话": "挂断后用官方公开号码回拨，不要按对方要求转接到第二个电话。",
}


def detect_platform(text: str, questionnaire: Optional[Dict] = None) -> str:
    labeled = re.search(r"\[(?:平台|渠道)\]\s*([^\n]+)", text or "")
    if labeled:
        return labeled.group(1).strip()
    q = questionnaire or {}
    for key in ("platform", "channel"):
        value = str(q.get(key) or "").strip()
        if value:
            return value
    for name in PLATFORM_LABELS:
        if name in (text or ""):
            return name
    return ""


def detect_time_window(text: str, questionnaire: Optional[Dict] = None) -> str:
    labeled = re.search(r"\[时间窗口\]\s*([^\n]+)", text or "")
    if labeled:
        return labeled.group(1).strip()
    raw = str((questionnaire or {}).get("time_window") or "").strip()
    return _WINDOW.get(raw, raw)


def public_opinion_lens(platform: str) -> Tuple[str, List[str]]:
    return _PUBLIC.get(platform) or (
        "先按该平台真实可见的主帖来核对，不要套用别的平台的传播方式。",
        ["先补来源，再决定转不转。", "官方回应要标出「已确认 / 仍在核实」。"],
    )


def channel_lens(channel: str) -> Tuple[str, List[str]]:
    return _CHANNEL.get(channel) or public_opinion_lens(channel)


def fraud_platform_action(platform: str) -> str:
    return _FRAUD.get(platform, "")
