"""Media report renderer — timeline, facts, angles, and harm-prevention guidance."""

from __future__ import annotations

from typing import Any, Dict, List

from .base import ReportRenderer
from .schema import RoleReportPayload, RenderedRoleReport


class MediaReportRenderer:
    role = "media"

    def render(self, payload: RoleReportPayload) -> RenderedRoleReport:
        scenario = payload.scenario_type
        timeline = _build_timeline(payload)
        confirmed = _build_confirmed(scenario, payload)
        unverified = _build_unverified(scenario, payload)
        angles = _build_angles(scenario)
        harm_avoid = _build_harm_avoid(scenario)
        questions = _build_questions_for_officials(scenario)

        sections = [
            {"heading": "时间线", "content": timeline},
            {"heading": "已确认事实", "content": confirmed},
            {"heading": "待核实信息", "content": unverified},
            {"heading": "可报道角度", "content": angles},
            {"heading": "避免次生伤害提示", "content": harm_avoid},
            {"heading": "向官方求证的问题清单", "content": questions},
        ]

        markdown_parts = ["# 媒体报道建议\n"]
        for sec in sections:
            markdown_parts.append(f"## {sec['heading']}\n{sec['content']}\n")

        return RenderedRoleReport(
            role=self.role,
            title="媒体报道建议 — 基于 CogSec 分析",
            markdown="\n".join(markdown_parts),
            sections=sections,
            structured={
                "timeline": _timeline_list(payload),
                "confirmed": _confirmed_list(scenario, payload),
                "unverified": _unverified_list(scenario, payload),
                "angles": _angles_list(scenario),
                "questions_for_officials": _questions_list(scenario),
            },
        )


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _build_timeline(payload: RoleReportPayload) -> str:
    items = _timeline_list(payload)
    if not items:
        return "暂无时间线数据。\n"
    lines = ["| 分支 | 步骤/Tick | 动作/状态 | 风险 |", "|------|-----------|-----------|------|"]
    for item in items[:15]:
        branch = item.get("branch", "?")
        step = item.get("step", item.get("tick", "?"))
        action = item.get("action", item.get("stage", "?"))
        risk = item.get("risk", item.get("coverage", 0))
        lines.append(f"| {branch} | {step} | {action} | {risk} |")
    return "\n".join(lines) + "\n"


def _timeline_list(payload: RoleReportPayload) -> list[dict]:
    items: list[dict] = list(payload.timeline)
    if payload.propagation:
        for branch_key in ("branch_a", "branch_b"):
            branch = payload.propagation.get(branch_key, {})
            if isinstance(branch, dict):
                for item in branch.get("coverage_curve", []) or []:
                    if isinstance(item, dict):
                        items.append({
                            "branch": f"propagation_{branch_key[-1].upper()}",
                            "tick": item.get("tick", 0),
                            "action": f"coverage: {item.get('coverage', 0)}",
                            "risk": item.get("coverage", 0),
                        })
    return items


def _build_confirmed(scenario: str, payload: RoleReportPayload) -> str:
    items = _confirmed_list(scenario, payload)
    return "\n".join(f"- {item}" for item in items)


def _confirmed_list(scenario: str, payload: RoleReportPayload) -> list[str]:
    base = ["系统已完成对输入文本的认知安全分析"]
    if payload.risk_scores.get("final_risk", 0) > 50:
        base.append("分析显示该事件存在中高风险信号")
    if payload.propagation:
        comparison = payload.propagation.get("comparison", {})
        if comparison:
            base.append(f"传播仿真完成: 覆盖率差值={comparison.get('coverage_delta', 'N/A')}")
    return base


def _build_unverified(scenario: str, payload: RoleReportPayload) -> str:
    items = _unverified_list(scenario, payload)
    return "\n".join(f"- {item}" for item in items)


def _unverified_list(scenario: str, payload: RoleReportPayload) -> list[str]:
    if scenario == "fraud_im":
        return [
            "攻击者的真实身份和所在地",
            "涉案金额的最终去向",
            "是否有其他受害者",
            "诈骗团伙的组织结构",
        ]
    if scenario == "public_opinion":
        return [
            "截图和网传图片是否被编辑",
            "关键账号的身份和动机",
            "信息跨平台传播的完整路径",
            "公众情绪的准确分布",
            "是否有组织性操纵",
        ]
    return [
        "图片/视频的真实性和拍摄时间",
        "首发来源的可信度",
        "跨平台传播的关键节点",
        "官方是否已经启动调查",
        "是否有以往的类似事件可供参考",
    ]


def _build_angles(scenario: str) -> str:
    items = _angles_list(scenario)
    return "\n".join(f"- {item}" for item in items)


def _angles_list(scenario: str) -> list[str]:
    if scenario == "fraud_im":
        return [
            "反诈警示：通过案例分析提醒公众识别同类骗局",
            "官方渠道科普：介绍银行、公安的正规核验流程",
            "受害者保护：避免曝光受害者隐私，聚焦诈骗手法",
            "数据新闻：结合近期反诈数据进行趋势分析",
        ]
    if scenario == "public_opinion":
        return [
            "事实核查：对关键信息逐条核实并标注可信度",
            "传播路径还原：展示信息从首发到爆发的路径",
            "多方视角：采访不同立场群体，呈现多元观点",
            "辟谣报道：在确认信息不实后及时发布辟谣",
        ]
    return [
        "时间线还原：梳理事件从触发到传播的完整路径",
        "关键节点分析：分析谁在推动信息传播",
        "多方求证：收集官方、当事人、旁观者的说法",
        "机制探讨：分析类似事件为何容易引发传播",
    ]


def _build_harm_avoid(scenario: str) -> str:
    if scenario == "fraud_im":
        return "- 避免公布受害者姓名、联系方式、家庭住址等个人信息\n- 避免详细描述诈骗操作步骤以免被模仿\n- 避免在未结案前对嫌疑人做出有罪推定\n"
    if scenario == "public_opinion":
        return "- 避免在事实未清前使用定性词汇（如造谣、煽动）\n- 避免点名曝光未经核实的涉事账号\n- 避免使用可能激化情绪的标题和配图\n- 避免将群体标签化\n"
    return "- 避免在官方调查结论前下定论\n- 避免传播未经处理的现场图片或视频\n- 避免对涉事方使用有罪推定式表述\n- 避免使用可能引发恐慌的标题\n"


def _build_questions_for_officials(scenario: str) -> str:
    items = _questions_list(scenario)
    return "\n".join(f"- {item}" for item in items)


def _questions_list(scenario: str) -> list[str]:
    if scenario == "fraud_im":
        return [
            "该诈骗类型近期在本地区的发案数量和趋势？",
            "公安机关目前采取了哪些打击措施？",
            "银行和支付平台是否有针对性的风控升级？",
            "公众应通过什么渠道举报可疑电话和账号？",
        ]
    if scenario == "public_opinion":
        return [
            "目前是否已有官方调查结果或说明？",
            "学校/主管单位对此事的态度和处置方案？",
            "网传截图和信息是否已经过技术鉴定？",
            "是否有统一的对外信息发布计划和时间表？",
        ]
    return [
        "目前官方对此事件的定性和处置进展？",
        "是否有权威机构的调查结果可以引用？",
        "公众应通过什么渠道获取最新权威信息？",
        "是否有需要公众配合的事项（如提供线索）？",
    ]
