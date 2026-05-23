"""Target group report renderer — community-facing communication and solidarity."""

from __future__ import annotations

from typing import Any, Dict, List

from .base import ReportRenderer
from .schema import RoleReportPayload, RenderedRoleReport


class TargetGroupReportRenderer:
    role = "target_group"

    def render(self, payload: RoleReportPayload) -> RenderedRoleReport:
        scenario = payload.scenario_type
        risk = payload.risk_scores.get("final_risk", 0.0)

        group_risks = _build_group_risks(scenario)
        verify_first = _build_verify_first(scenario)
        internal = _build_internal_communication(scenario)
        external = _build_external_expression(scenario)
        official_check = _build_official_checklist(scenario)

        sections = [
            {"heading": "我们这个群体现在面对什么", "content": group_risks},
            {"heading": "哪些信息需要先核实", "content": verify_first},
            {"heading": "群体内部沟通建议", "content": internal},
            {"heading": "对外表达建议", "content": external},
            {"heading": "如何识别可靠官方信息", "content": official_check},
        ]

        markdown_parts = ["# 面向目标群体的沟通建议\n"]
        for sec in sections:
            markdown_parts.append(f"## {sec['heading']}\n{sec['content']}\n")

        return RenderedRoleReport(
            role=self.role,
            title="面向目标群体的沟通建议 — 基于 CogSec 分析",
            markdown="\n".join(markdown_parts),
            sections=sections,
            structured={
                "group_risks": _group_risks_list(scenario),
                "verify_first": _verify_first_list(scenario),
                "internal_communication": _internal_list(scenario),
                "external_expression": _external_list(scenario),
                "official_info_checklist": _official_checklist(scenario),
            },
        )


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _build_group_risks(scenario: str) -> str:
    if scenario == "fraud_im":
        return (
            "我们这个群体正在面对一个可能的诈骗行为。对方可能冒充客服、公检法或熟人，"
            "利用权威身份和时间压力诱导转账、提供验证码或共享屏幕。"
            "我们需要互相提醒，不要因为对方语气专业就放松警惕。"
        )
    if scenario == "public_opinion":
        return (
            "我们这个群体正在面对一个快速传播的舆情事件。"
            "信息可能来自不同渠道，有些尚未得到官方确认。"
            "情绪化的内容容易让人急于表态或转发，但这可能加剧信息混乱。"
            "我们可以一起冷静下来，先核实再行动。"
        )
    return (
        "我们这个群体正在面对一个引发广泛关注的事件。"
        "图片、视频和描述可能只呈现了事件的一部分。"
        "在更多可靠信息出现前，我们需要互相支持，保持理性，避免被情绪裹挟。"
    )


def _build_verify_first(scenario: str) -> str:
    items = _verify_first_list(scenario)
    return "\n".join(f"- {item}" for item in items)


def _verify_first_list(scenario: str) -> list[str]:
    if scenario == "fraud_im":
        return [
            "对方自称的身份是否可以通过官方渠道（官网、官方热线、APP）核实",
            "对方提供的链接、二维码、电话号码是否与官方一致",
            "是否有人已经经历过类似的骗局（可以在群里问一问）",
        ]
    if scenario == "public_opinion":
        return [
            "信息的首发来源是谁，是否可查证",
            "截图是否有编辑痕迹，是否有不同版本在流传",
            "官方账号（学校、政府、权威媒体）是否发布了相关说明",
            "是否有多个独立来源可以交叉验证",
        ]
    return [
        "信息的首发来源和发布时间是否可以确认",
        "图片/视频是否有被编辑或裁剪的痕迹",
        "是否有官方或权威机构的回应可以对照",
        "是否有其他独立来源报道了相同或不同的信息",
    ]


def _build_internal_communication(scenario: str) -> str:
    items = _internal_list(scenario)
    return "\n".join(f"- {item}" for item in items)


def _internal_list(scenario: str) -> list[str]:
    if scenario == "fraud_im":
        return [
            "在群里分享你遇到的诈骗话术，让大家都能识别",
            "如果有人犹豫是否被骗，鼓励 ta 拨打官方热线核实",
            "不要嘲笑或指责已经上当的人，我们要互相支持",
            "有新的诈骗手法及时通报全群",
        ]
    if scenario == "public_opinion":
        return [
            "不要在群内转发未经核实的信息，先发到'待核实'专区",
            "如果有人情绪激动，先安抚再讨论事实",
            "指定几位同学负责汇总官方信息和可靠报道",
            "定期更新'已确认'和'待核实'信息列表",
        ]
    return [
        "建立群内信息共享机制，区分'已确认'和'待核实'",
        "如果有人掌握可靠信息，鼓励分享并标注来源",
        "避免在群内争论谁对谁错，专注于事实和下一步行动",
        "定期汇总官方和可靠媒体的最新进展",
    ]


def _build_external_expression(scenario: str) -> str:
    items = _external_list(scenario)
    return "\n".join(f"- {item}" for item in items)


def _external_list(scenario: str) -> list[str]:
    if scenario == "fraud_im":
        return [
            "如果要在社交媒体上提醒他人，只描述诈骗手法，不公布受害者信息",
            "分享官方反诈信息和举报渠道，帮助更多人识别",
            "使用#反诈提醒 等标签扩大传播，但不要散布恐慌",
        ]
    if scenario == "public_opinion":
        return [
            "公开发言前确认信息来源和可信度",
            "使用'目前了解到的信息是...'而不是'真相是...'",
            "如果你是当事人，建议先通过官方渠道表达诉求",
            "表达关切和诉求时使用理性、建设性的语言",
        ]
    return [
        "对外发声时以'我们了解到的'而非'事实是'开头",
        "如需表达诉求，使用正式、理性的渠道和语言",
        "避免在公开平台指责个人或群体",
        "如果有可靠信息，先内部确认再对外发布",
    ]


def _build_official_checklist(scenario: str) -> str:
    items = _official_checklist(scenario)
    return "\n".join(f"- {item}" for item in items)


def _official_checklist(scenario: str) -> list[str]:
    if scenario == "fraud_im":
        return [
            "官方机构通常不会通过电话要求转账或提供验证码",
            "真正的官方通知会通过 APP 消息、官方网站或纸质文件发送",
            "拨打 110 或银行官方客服是确认身份的最可靠方式",
            "凡是要求保密、不准告诉家人的，极可能是诈骗",
        ]
    if scenario == "public_opinion":
        return [
            "关注学校官方公众号、官网和官方微博账号",
            "政府部门的公告通常会在官网上同步发布",
            "权威媒体（如新华社、人民日报）的报道优先级高于自媒体",
            "如果多个官方渠道信息一致，可信度更高",
        ]
    return [
        "关注官方机构的官网、官方公众号和认证社交媒体账号",
        "权威媒体的报道通常经过多方核实，优先参考",
        "多个独立官方渠道的一致信息比单一来源更可靠",
        "如果官方发布'辟谣'或'澄清'，请优先相信并转发",
    ]


def _group_risks_list(scenario: str) -> list[str]:
    if scenario == "fraud_im":
        return ["诈骗风险", "身份信息泄露", "资金损失", "信任被利用"]
    if scenario == "public_opinion":
        return ["信息混乱", "情绪感染", "群体极化", "不实信息传播"]
    return ["信息不确定性", "情绪被裹挟", "片面信息误导", "次生传播伤害"]
