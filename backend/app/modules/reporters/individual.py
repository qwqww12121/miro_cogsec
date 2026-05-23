"""Individual report renderer — personal protection and next-step guidance."""

from __future__ import annotations

from typing import Any, Dict, List

from .base import ReportRenderer
from .schema import RoleReportPayload, RenderedRoleReport


class IndividualReportRenderer:
    role = "individual"

    def render(self, payload: RoleReportPayload) -> RenderedRoleReport:
        scenario = payload.scenario_type
        risk = payload.risk_scores.get("final_risk", 0.0)

        sections = [
            {"heading": "为什么这和你有关", "content": _why_relevant(scenario)},
            {"heading": "你现在最应该做的三件事", "content": _top_actions(scenario, payload)},
            {"heading": "暂时不要做的三件事", "content": _avoid_actions(scenario, payload)},
            {"heading": "可以直接复制的应对话术", "content": _copyable_responses(scenario, payload)},
            {"heading": "如果已经操作了怎么办", "content": _already_done(scenario)},
        ]

        markdown_parts = [f"# 个人风险判断\n"]
        for sec in sections:
            markdown_parts.append(f"## {sec['heading']}\n{sec['content']}\n")

        top = _top_actions_list(scenario, payload)
        avoid = _avoid_actions_list(scenario, payload)
        copyable = _copyable_responses_list(scenario, payload)

        return RenderedRoleReport(
            role=self.role,
            title=f"个人风险判断 — 基于 CogSec 分析",
            markdown="\n".join(markdown_parts),
            sections=sections,
            structured={
                "top_actions": top,
                "avoid_actions": avoid,
                "copyable_responses": copyable,
                "risk_summary": {
                    "final_risk": risk,
                    "level": _risk_label(risk),
                },
            },
        )


# ---------------------------------------------------------------------------
# section builders
# ---------------------------------------------------------------------------


def _why_relevant(scenario: str) -> str:
    if scenario == "fraud_im":
        return "根据分析，你面临的对话具有典型的诈骗特征。攻击者可能利用权威身份、时间压力或稀缺性诱导你转账、提供验证码或共享屏幕。我们建议你仔细阅读以下建议，保护好你的资金和身份信息。"
    if scenario == "public_opinion":
        return "当前舆情传播中，你可能接触到未经证实的信息或带有强烈情绪的内容。我们建议你在转发、评论或采取行动前，先核实信息来源，避免成为不实信息的传播者。"
    return "当前事件传播快速，图片、视频和描述可能存在不确定性。我们建议你等待官方或多源信息确认后再做判断，不要因着急而轻信单一来源。"


def _top_actions(scenario: str, payload: RoleReportPayload) -> str:
    actions = _top_actions_list(scenario, payload)
    lines = [f"{i+1}. {a}" for i, a in enumerate(actions)]
    return "\n".join(lines)


def _top_actions_list(scenario: str, payload: RoleReportPayload) -> list[str]:
    if scenario == "fraud_im":
        return [
            "暂停当前对话，不要继续提供任何信息",
            "通过官方渠道（官方 APP、银行热线、110）核实对方身份",
            "告知一位家人或朋友你遇到的情况，让他们帮你一起判断",
        ]
    if scenario == "public_opinion":
        return [
            "暂停转发或评论，等待更多信息确认",
            "检查信息来源：发布者是否可查证、截图是否有编辑痕迹",
            "保存相关截图和链接，作为后续核实的依据",
        ]
    return [
        "暂停判断，确认信息来源的可靠性",
        "查找官方或权威机构的回应",
        "记录你看到信息的时间和平台，便于后续追溯",
    ]


def _avoid_actions(scenario: str, payload: RoleReportPayload) -> str:
    actions = _avoid_actions_list(scenario, payload)
    lines = [f"{i+1}. {a}" for i, a in enumerate(actions)]
    return "\n".join(lines)


def _avoid_actions_list(scenario: str, payload: RoleReportPayload) -> list[str]:
    if scenario == "fraud_im":
        return [
            "不要向任何人透露短信验证码",
            "不要下载来源不明的 APP 或开启屏幕共享",
            "不要因为对方声称是'官方'就放弃独立核验",
        ]
    if scenario == "public_opinion":
        return [
            "不要仅凭一张截图或一段文字就下结论",
            "不要在情绪激动时发布公开言论",
            "不要转发未经核实的信息，即使它看起来像真的",
        ]
    return [
        "不要轻信单一来源的图片或视频",
        "不要因为多人转发就认为信息属实",
        "不要在未确认事实前传播个人信息或对方信息",
    ]


def _copyable_responses(scenario: str, payload: RoleReportPayload) -> str:
    responses = _copyable_responses_list(scenario, payload)
    lines = [f"- \"{r}\"" for r in responses]
    return "\n".join(lines)


def _copyable_responses_list(scenario: str, payload: RoleReportPayload) -> list[str]:
    if scenario == "fraud_im":
        return [
            "我先核实一下你的身份，稍后回拨官方客服电话确认。",
            "我需要和家人商量一下，现在不方便继续操作。",
            "我不会在电话里提供银行卡信息和验证码，请通过官方渠道联系我。",
        ]
    if scenario == "public_opinion":
        return [
            "我看到这个消息了，但想先确认一下来源再回应。",
            "这条信息我还没核实，建议你也先不要转发。",
            "我们可以一起看看官方有没有发布相关说明。",
        ]
    return [
        "我需要等更多信息确认后再表态。",
        "建议大家先看官方渠道的说明。",
        "图片和视频可以编辑，我们不要急于下结论。",
    ]


def _already_done(scenario: str) -> str:
    if scenario == "fraud_im":
        return "如果你已经转账、提供了验证码或开启了屏幕共享，请立即拨打银行客服冻结账户，并拨打 110 报警。保留聊天记录、通话记录和转账凭证作为证据。"
    if scenario == "public_opinion":
        return "如果你已经转发或评论了不实信息，建议你发布更正说明，告知信息来源不可靠。删除原内容并附上更正有助于减少次生传播。"
    return "如果你已经传播了未经核实的信息，建议你在原平台发布更正或补充说明。保留原始来源以备后续核实。"


def _risk_label(score: float) -> str:
    if score >= 75:
        return "high"
    if score >= 50:
        return "medium"
    return "low"
