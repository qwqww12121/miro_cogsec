"""Official report renderer — institutional response and coordination guidance."""

from __future__ import annotations

from typing import Any, Dict, List

from .base import ReportRenderer
from .schema import RoleReportPayload, RenderedRoleReport


class OfficialReportRenderer:
    role = "official"

    def render(self, payload: RoleReportPayload) -> RenderedRoleReport:
        scenario = payload.scenario_type
        risk = payload.risk_scores.get("final_risk", 0.0)
        key_nodes = _extract_key_nodes(payload)

        sections: list[dict] = []

        # 1. current situation
        situation = {
            "scenario_type": scenario,
            "risk_level": _risk_label(risk),
            "risk_score": risk,
        }
        sections.append({"heading": "当前态势", "content": _situation_text(situation)})

        # 2. key nodes table
        node_table = _build_key_node_table(key_nodes)
        sections.append({"heading": "关键节点表", "content": node_table})

        # 3. Fork A/B comparison
        fork_text = _build_fork_comparison(payload)
        sections.append({"heading": "Fork A/B 对比", "content": fork_text})

        # 4. intervention window
        window = _build_intervention_window(payload)
        sections.append({"heading": "处置窗口", "content": window})

        # 5. cross-department coordination
        coord = _build_coordination(scenario)
        sections.append({"heading": "跨部门协同建议", "content": coord})

        # 6. data still needed
        data_needed = _build_data_needed(scenario)
        sections.append({"heading": "仍需补充的数据", "content": data_needed})

        markdown_parts = ["# 官方处置摘要\n"]
        for sec in sections:
            markdown_parts.append(f"## {sec['heading']}\n{sec['content']}\n")

        return RenderedRoleReport(
            role=self.role,
            title="官方处置摘要 — 基于 CogSec 分析",
            markdown="\n".join(markdown_parts),
            sections=sections,
            structured={
                "situation": situation,
                "key_nodes": key_nodes,
                "intervention_window": _window_dict(payload),
                "coordination": _coordination_list(scenario),
                "data_needed": _data_needed_list(scenario),
            },
        )


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _extract_key_nodes(payload: RoleReportPayload) -> list[dict]:
    nodes: list[dict] = []
    if payload.propagation:
        for branch_key in ("branch_a", "branch_b"):
            branch = payload.propagation.get(branch_key, {})
            if isinstance(branch, dict):
                for kn in branch.get("key_nodes", []) or []:
                    if isinstance(kn, dict) and kn not in nodes:
                        nodes.append(kn)
    for kf in payload.key_findings:
        if "title" in kf:
            nodes.append({"agent_id": kf.get("title", ""), "role": kf.get("title", ""), "score": 0.0, "intervention_reason": kf.get("evidence", "")})
    return nodes[:10]


def _build_key_node_table(nodes: list[dict]) -> str:
    if not nodes:
        return "暂无关键节点数据。\n"
    lines = ["| 节点 | 角色 | 评分 | 干预原因 |", "|------|------|------|----------|"]
    for n in nodes:
        aid = n.get("agent_id", n.get("title", "?"))
        role = n.get("role", "?")
        score = n.get("score", 0)
        reason = n.get("intervention_reason", n.get("evidence", ""))
        if isinstance(reason, list):
            reason = "; ".join(str(r) for r in reason)
        lines.append(f"| {aid} | {role} | {score} | {reason} |")
    return "\n".join(lines) + "\n"


def _build_fork_comparison(payload: RoleReportPayload) -> str:
    prop = payload.propagation or {}
    comparison = prop.get("comparison", {})
    if comparison:
        cov = comparison.get("coverage_delta", 0)
        act = comparison.get("action_delta", 0)
        peak = comparison.get("peak_risk_delta", 0)
        eff = comparison.get("intervention_effective", False)
        lines = [
            f"- 覆盖率差值 (A - B): {cov}",
            f"- 行动数差值 (A - B): {act}",
            f"- 峰值风险差值 (A - B): {peak}",
            f"- 干预是否有效: {'是' if eff else '否'}",
        ]
        return "\n".join(lines) + "\n"

    fc = payload.fork_comparison
    gap = fc.get("trajectory_gap", "N/A")
    return f"当前 Fork 轨迹差值: {gap}\n"


def _build_intervention_window(payload: RoleReportPayload) -> str:
    window = payload.fork_comparison.get("best_intervention_window", {})
    if window:
        return f"- 最佳干预窗口: step {window.get('open_step', '?')} - {window.get('close_step', '?')}\n- 标签: {window.get('label', '')}\n"
    prop = payload.propagation or {}
    fork_point = prop.get("fork_point", {})
    if fork_point:
        return f"- 干预 tick: {fork_point.get('intervention_tick', '?')}\n- 策略: {fork_point.get('strategy_type', '?')}\n"
    return "暂无干预窗口数据。\n"


def _window_dict(payload: RoleReportPayload) -> dict:
    w = payload.fork_comparison.get("best_intervention_window", {})
    if w:
        return w
    return payload.propagation.get("fork_point", {}) if payload.propagation else {}


def _build_coordination(scenario: str) -> str:
    items = _coordination_list(scenario)
    return "\n".join(f"- {item}" for item in items)


def _coordination_list(scenario: str) -> list[str]:
    if scenario == "fraud_im":
        return [
            "与公安反诈中心联动，共享诈骗账号和话术特征",
            "协调银行和支付平台对涉案账户实施紧急管控",
            "通知电信运营商对诈骗号码进行标记和拦截",
            "联动社区和学校开展针对性反诈宣传",
        ]
    if scenario == "public_opinion":
        return [
            "与宣传部门协调统一口径，避免信息矛盾",
            "联动网信办对不实信息进行标注和管控",
            "协调教育部门和学校做好师生情绪安抚",
            "与媒体建立信息通报机制，及时提供可发布的权威信息",
        ]
    return [
        "与应急管理部门协调事件定性和处置方案",
        "联动网信、公安等部门做好信息管控和辟谣",
        "协调事发单位或区域的管理部门做好现场处置",
        "与主流媒体建立信息通报渠道，统一信息出口",
    ]


def _build_data_needed(scenario: str) -> str:
    items = _data_needed_list(scenario)
    return "\n".join(f"- {item}" for item in items)


def _data_needed_list(scenario: str) -> list[str]:
    if scenario == "fraud_im":
        return [
            "受害者完整对话记录和转账凭证",
            "诈骗号码、账号、链接等溯源信息",
            "受害人画像数据（年龄、职业、被骗前知情程度）",
            "同类型案件的近期发案趋势",
        ]
    if scenario == "public_opinion":
        return [
            "舆情首发来源和首发平台",
            "关键传播节点（转发量大的账号和群组）",
            "公众情绪和主要关切点的抽样调查",
            "已发布的官方声明和媒体报导汇总",
        ]
    return [
        "事件首发时间、地点和来源",
        "关键传播路径（跨平台转发链）",
        "涉事方和权威机构的回应情况",
        "公众关注度和情绪分布数据",
    ]


def _situation_text(sit: dict) -> str:
    return (
        f"场景类型: {sit.get('scenario_type', 'unknown')}\n"
        f"风险等级: {sit.get('risk_level', 'low')} (分数: {sit.get('risk_score', 0.0)})\n"
    )


def _risk_label(score: float) -> str:
    if score >= 75:
        return "high"
    if score >= 50:
        return "medium"
    return "low"
