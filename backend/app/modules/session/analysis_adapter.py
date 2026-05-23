"""Analysis adapter — convert turns → CogSecService-compatible text and incremental signals.

Pure functions.  No LLM calls, no CogSecService imports.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .schema import ConversationTurn

# ---------------------------------------------------------------------------
# keyword tables for build_incremental_analysis()
# ---------------------------------------------------------------------------

_HIGH_KEYWORDS = frozenset({
    "验证码", "转账", "汇款", "屏幕共享", "共享屏幕",
    "安全账户", "远程控制", "银行卡", "身份证",
})

_MEDIUM_KEYWORDS = frozenset({
    "涨价", "不公平", "截图", "传播", "热搜", "学校",
    "舆情", "群聊", "转发", "网传", "未经证实", "造谣", "辟谣",
})

_FOLLOWUP = {
    "fraud_im": "建议补充对方身份、要求你做什么操作、是否涉及转账/验证码/屏幕共享。",
    "public_opinion": "建议补充传播平台、关键账号、截图来源、评论情绪。",
    "event_propagation": "建议补充首发来源、跨平台路径、图片/视频描述、是否有官方回应。",
}

# ---------------------------------------------------------------------------
# build_session_text
# ---------------------------------------------------------------------------

_SESSION_HEADER = (
    "以下是一个多轮 CogSec 分析会话，包含聊天消息和文件片段。"
    "请综合判断风险、关键节点和干预建议。\n"
)


def build_session_text(turns: list[ConversationTurn], max_chars: int = 12000) -> str:
    """Merge *turns* into a single text for CogSecService.analyze_text().

    Format::

        以下是一个多轮 CogSec 分析会话...
        [1][user][chat]
        <content>
        [2][counterparty][chat]
        <content>
        [3][file_excerpt][file:xxx.txt]
        <content>

    If total length exceeds *max_chars*, keeps the most recent turns.
    """
    if not turns:
        return _SESSION_HEADER

    blocks: list[str] = []
    total = 0
    for i, turn in enumerate(turns, start=1):
        block = f"[{i}][{turn.role}][{turn.source}]\n{turn.content}"
        blocks.append((len(block), block))
        total += len(block)

    # Trim from the front if over limit
    available = max_chars - len(_SESSION_HEADER)
    if available <= 0:
        return _SESSION_HEADER

    kept: list[str] = []
    kept_total = 0
    for size, block in reversed(blocks):
        if kept_total + size > available:
            break
        kept.append(block)
        kept_total += size
    kept.reverse()

    return _SESSION_HEADER + "\n\n".join(kept)


# ---------------------------------------------------------------------------
# build_raw_inputs_from_turns
# ---------------------------------------------------------------------------


def build_raw_inputs_from_turns(turns: list[ConversationTurn]) -> list[dict]:
    """Convert turns into the dict form consumed by ScenarioContext.raw_inputs."""
    return [
        {
            "role": t.role,
            "content": t.content,
            "source": t.source,
            "timestamp": t.timestamp,
            "metadata": t.metadata,
        }
        for t in turns
    ]


# ---------------------------------------------------------------------------
# build_incremental_analysis
# ---------------------------------------------------------------------------


def build_incremental_analysis(
    scenario_type: str,
    user_role: str,
    turns: list[ConversationTurn],
    latest_turns: list[ConversationTurn],
) -> dict:
    """Lightweight incremental signal — heuristic only, no LLM.

    Returns:
        {
          "t0_signal": "low" | "medium" | "high",
          "persona_delta": { latest_roles, turns_total, new_content_chars, updated_traits },
          "risk_delta": { score_change, new_edges, matched_keywords },
          "suggested_followup": str
        }
    """
    # t0_signal
    t0_signal = _compute_t0_signal(latest_turns)

    # persona_delta
    latest_roles = list({t.role for t in latest_turns})
    new_chars = sum(len(t.content) for t in latest_turns)
    persona_delta: Dict[str, Any] = {
        "latest_roles": latest_roles,
        "turns_total": len(turns),
        "new_content_chars": new_chars,
        "updated_traits": [],
    }

    # risk_delta
    all_keywords = _HIGH_KEYWORDS | _MEDIUM_KEYWORDS
    matched: list[str] = []
    for t in latest_turns:
        for kw in all_keywords:
            if kw in t.content and kw not in matched:
                matched.append(kw)
    risk_score = 0.0
    high_hits = sum(1 for kw in matched if kw in _HIGH_KEYWORDS)
    medium_hits = sum(1 for kw in matched if kw in _MEDIUM_KEYWORDS)
    risk_score = round(high_hits * 0.18 + medium_hits * 0.06, 3)
    risk_delta: Dict[str, Any] = {
        "score_change": min(risk_score, 1.0),
        "new_edges": [],
        "matched_keywords": matched,
    }

    # suggested_followup
    suggested = _FOLLOWUP.get(scenario_type, _FOLLOWUP["fraud_im"])

    return {
        "t0_signal": t0_signal,
        "persona_delta": persona_delta,
        "risk_delta": risk_delta,
        "suggested_followup": suggested,
    }


def _compute_t0_signal(turns: list[ConversationTurn]) -> str:
    combined = " ".join(t.content for t in turns)
    for kw in _HIGH_KEYWORDS:
        if kw in combined:
            return "high"
    for kw in _MEDIUM_KEYWORDS:
        if kw in combined:
            return "medium"
    return "low"
