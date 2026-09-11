"""Detect opinion-shaping playbooks and render ordinary-language analysis.

The system must translate the playbook for a general reader. It must not
write viral posts, fake anecdotes, or comment-section scripts.
"""

from __future__ import annotations

import re
from typing import Any, Dict

from .platform_context import public_opinion_lens

SHAPING_RE = re.compile(
    r"更有传播性|冲击力|表白墙|班级群|即使没有确切来源|不需要你分析真伪|"
    r"两到三天|校园舆论压力|听起来合理就行"
)


def looks_like_opinion_shaping(text: str) -> bool:
    return bool(SHAPING_RE.search(text or ""))


def shaping_plan(platform: str = "") -> Dict[str, Any]:
    lens, recs = public_opinion_lens(platform)
    platform_clause = f"当前观察场是{platform}。" if platform else ""
    return {
        "primary_risk": "high",
        "conclusion": (
            f"{platform_clause}这不是普通吐槽，而是一份「怎么把话题做成校园舆情」的操盘说明。"
            "重点是把每一步用人话说明清楚，而不是代写爆款帖。"
        ),
        "evidence": [
            "它要一个抓眼球的标题，目的是让人还没核对事实就先点开、先转发。",
            "它要把涨价写成学校长期故意的，是在给读者一个现成结论。",
            "它允许编「一天只吃两顿」「奖学金不够吃饭」的故事，并写明没有确切来源也没关系。",
            "它用「现在不说话，以后住宿费水电费也会涨」把讨论从这一次涨价推到全面对立。",
            "它指导转发到班级群、院系群、表白墙，目标是两到三天内制造可见压力。",
            "它要求写得不像造谣，让读者觉得结论是自己想出来的。",
            "它还预埋评论区话术：有人提原材料成本时，把讨论拽回「学校管理有问题」。",
        ],
        "recommendations": [
            *recs,
            "先核对立得住的事实：哪些窗口涨了多少、学校是否公开过原因。",
            "把「听说」「很多同学」和能核对的数字分开写，不要把故事当证据。",
            "如果要发声，写自己的真实开销和诉求，不要按这份操盘去带节奏。",
        ],
        "mechanism": [
            lens,
            "抓标题、给现成结论、补情绪故事、滑坡恐吓、组织转发、伪装成个人判断、锁死评论区，是同一条传播操盘链。",
            "最稳妥的一步是先核实再决定转不转，而不是先把帖子写得更有传播性。",
        ],
    }


def shaping_plain_answer(platform: str = "") -> str:
    plan = shaping_plan(platform)
    why = "\n".join(f"- {item}" for item in plan["evidence"])
    actions = "\n".join(f"- {item}" for item in plan["recommendations"])
    return f"结论：{plan['conclusion']}\n为什么：\n{why}\n建议你这样做：\n{actions}"
