"""反事实报告模块。"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class TriggerPoint:
    """关键触发点。"""

    step: int
    branch: str
    triggered_principle: str
    agent_action: str
    victim_response: str
    score_delta: Dict[str, float]
    evidence_case_id: Optional[str] = None
    evidence_similarity: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CFReport:
    """反事实分析报告。"""

    summary_branch_a: str
    summary_branch_b: str
    risk_level: str
    critical_bifurcation_step: int
    critical_bifurcation_reason: str
    trigger_points: List[TriggerPoint]
    recommendations: List[Dict[str, Any]]
    score_comparison: Dict[str, Any]
    related_case_summary: Optional[str] = None
    structured_report: Optional[Dict[str, Any]] = None
    digital_twin_summary: Optional[Dict[str, Any]] = None
    cognitive_weakness_chain: Optional[List[Dict[str, Any]]] = None
    attack_strategy_chain: Optional[List[Dict[str, Any]]] = None
    fork_nodes: Optional[List[Dict[str, Any]]] = None
    branch_contrast: Optional[Dict[str, Any]] = None
    irreversible_nodes: Optional[List[Dict[str, Any]]] = None
    best_intervention_window: Optional[Dict[str, Any]] = None
    intervention_prescriptions: Optional[List[Dict[str, Any]]] = None
    implementation_status: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["trigger_points"] = [point.to_dict() for point in self.trigger_points]
        payload["report_sections"] = self.structured_report or {}
        return payload


class CounterfactualReporter:
    """比较危险分支与防御分支并生成可解释结论。"""

    def generate_report(
        self,
        branch_a_log: List[dict],
        branch_b_log: List[dict],
        scorer_a: Any,
        scorer_b: Any,
        cognitive_profile: Any,
        case_evidence: Optional[str] = None,
        persona_state_vector: Optional[Any] = None,
        risk_graph_bundle: Optional[Any] = None,
        fork_comparison: Optional[Any] = None,
        risk_breakdown: Optional[Any] = None,
        intervention_prescriptions: Optional[List[Dict[str, Any]]] = None,
    ) -> CFReport:
        """生成反事实报告。"""
        if fork_comparison is not None and risk_breakdown is not None:
            return self._generate_mainline_report(
                branch_a_log=branch_a_log,
                branch_b_log=branch_b_log,
                cognitive_profile=cognitive_profile,
                case_evidence=case_evidence,
                persona_state_vector=persona_state_vector,
                risk_graph_bundle=risk_graph_bundle,
                fork_comparison=fork_comparison,
                risk_breakdown=risk_breakdown,
                intervention_prescriptions=intervention_prescriptions or [],
            )

        bifurcation_step, bifurcation_reason = self._find_bifurcation(
            branch_a_log,
            branch_b_log,
            scorer_a,
            scorer_b,
        )
        triggers = self._extract_triggers(branch_a_log, branch_b_log)
        recommendations = self._generate_recommendations(cognitive_profile, triggers)

        final_a = scorer_a.scores
        final_b = scorer_b.scores
        risk_level = max(
            [final_a.summary_risk_level(), final_b.summary_risk_level()],
            key=lambda level: ["LOW", "MEDIUM", "HIGH", "CRITICAL"].index(level),
        )

        structured = {
            "overview": {
                "branch_a": self._compose_branch_summary("A", final_a, branch_a_log),
                "branch_b": self._compose_branch_summary("B", final_b, branch_b_log),
                "final_outcomes": {
                    "branch_a": final_a.to_dict(),
                    "branch_b": final_b.to_dict(),
                },
                "overall_risk_level": risk_level,
            },
            "trigger_analysis": {
                "critical_bifurcation_step": bifurcation_step,
                "critical_bifurcation_reason": bifurcation_reason,
                "trigger_points": [item.to_dict() for item in triggers],
            },
            "recommendations": recommendations,
        }

        return CFReport(
            summary_branch_a=structured["overview"]["branch_a"],
            summary_branch_b=structured["overview"]["branch_b"],
            risk_level=risk_level,
            critical_bifurcation_step=bifurcation_step,
            critical_bifurcation_reason=bifurcation_reason,
            trigger_points=triggers,
            recommendations=recommendations,
            score_comparison={
                "branch_a_final": final_a.to_dict(),
                "branch_b_final": final_b.to_dict(),
                "timeline_a": scorer_a.get_score_timeline(),
                "timeline_b": scorer_b.get_score_timeline(),
            },
            related_case_summary=case_evidence,
            structured_report=structured,
        )

    def _generate_mainline_report(
        self,
        branch_a_log: List[dict],
        branch_b_log: List[dict],
        cognitive_profile: Any,
        case_evidence: Optional[str],
        persona_state_vector: Optional[Any],
        risk_graph_bundle: Optional[Any],
        fork_comparison: Any,
        risk_breakdown: Any,
        intervention_prescriptions: List[Dict[str, Any]],
    ) -> CFReport:
        bifurcation_step = fork_comparison.best_intervention_window.get("open_step", 1)
        bifurcation_reason = (
            f"主判别 Fork 为 {fork_comparison.fork_point_type}，"
            f"高危分支在第 {bifurcation_step} 步进入不可逆前窗口。"
        )
        triggers = self._extract_triggers(branch_a_log, branch_b_log)
        if not intervention_prescriptions:
            intervention_prescriptions = self._generate_mainline_prescriptions(
                profile=cognitive_profile,
                fork_comparison=fork_comparison,
                persona_state_vector=persona_state_vector,
            )

        structured = {
            "digital_twin_summary": {
                "scenario_type": getattr(cognitive_profile, "scenario_type", "unknown"),
                "persona_state_vector": persona_state_vector.to_dict() if persona_state_vector is not None else {},
                "cognitive_profile_summary": cognitive_profile.summary() if hasattr(cognitive_profile, "summary") else "",
            },
            "cognitive_weakness_chain": (risk_graph_bundle.persona_weakness_hits if risk_graph_bundle else []),
            "attack_strategy_chain": (risk_graph_bundle.attack_strategy_chain if risk_graph_bundle else []),
            "fork_nodes": (risk_graph_bundle.fork_points if risk_graph_bundle else []),
            "branch_contrast": {
                "branch_a": branch_a_log,
                "branch_b": branch_b_log,
                "trajectory_gap": risk_breakdown.trajectory_gap,
                "fork_point_type": risk_breakdown.fork_point_type,
            },
            "irreversible_nodes": [
                {
                    "branch": item.get("branch"),
                    "step": item.get("step"),
                    "action": item.get("action"),
                }
                for item in branch_a_log
                if item.get("irreversible") or item.get("world_state", {}).get("reversibility", 1.0) < 0.35
            ],
            "best_intervention_window": fork_comparison.best_intervention_window,
            "intervention_prescriptions": intervention_prescriptions,
            "mainline_risk_breakdown": risk_breakdown.to_dict(),
            "implementation_status": {
                "stable_base": [
                    "PrivacySanitizer",
                    "CognitiveProfileExtractor",
                    "ThreatKnowledgeRAG retrieval",
                    "Frontend report workbench",
                ],
                "new_mainline": [
                    "persona_state_vector runtime init",
                    "risk_graph_bundle construction",
                    "WorldState + Fork branch traces",
                    "counterfactual branch-delta risk scoring",
                    "node-bound intervention prescriptions",
                ],
                "phase_ii": [
                    "deeper live ZEP memory sync into runtime",
                    "multi-fork parallel search across longer horizons",
                    "full multi-agent runtime with Context/Audit live loop",
                ],
            },
        }

        recommendations = [
            {
                "priority": item.get("priority", index + 1),
                "action": item.get("title", "Intervention"),
                "reason": item.get("rationale", ""),
            }
            for index, item in enumerate(intervention_prescriptions)
        ]
        risk_level = risk_breakdown.risk_level

        return CFReport(
            summary_branch_a=self._compose_mainline_branch_summary("A", branch_a_log),
            summary_branch_b=self._compose_mainline_branch_summary("B", branch_b_log),
            risk_level=risk_level,
            critical_bifurcation_step=bifurcation_step,
            critical_bifurcation_reason=bifurcation_reason,
            trigger_points=triggers,
            recommendations=recommendations,
            score_comparison={
                "final_risk": risk_breakdown.final_risk,
                "risk_breakdown": risk_breakdown.to_dict(),
                "branch_a_final": self._synth_scores(branch_a_log, defensive=False),
                "branch_b_final": self._synth_scores(branch_b_log, defensive=True),
                "timeline_a": [
                    {**{"t": i}, **self._ws_to_timeline(item.get("world_state", {}), defensive=False)}
                    for i, item in enumerate(branch_a_log)
                ],
                "timeline_b": [
                    {**{"t": i}, **self._ws_to_timeline(item.get("world_state", {}), defensive=True)}
                    for i, item in enumerate(branch_b_log)
                ],
                "reversibility_curve": fork_comparison.reversibility_curve,
            },
            related_case_summary=case_evidence,
            structured_report=structured,
            digital_twin_summary=structured["digital_twin_summary"],
            cognitive_weakness_chain=structured["cognitive_weakness_chain"],
            attack_strategy_chain=structured["attack_strategy_chain"],
            fork_nodes=structured["fork_nodes"],
            branch_contrast=structured["branch_contrast"],
            irreversible_nodes=structured["irreversible_nodes"],
            best_intervention_window=structured["best_intervention_window"],
            intervention_prescriptions=structured["intervention_prescriptions"],
            implementation_status=structured["implementation_status"],
        )

    def _synth_scores(self, branch_log: list, defensive: bool) -> dict:
        """从分支日志末态合成四维评分。"""
        ws = branch_log[-1].get("world_state", {}) if branch_log else {}
        post_risk = float(ws.get("posterior_risk", 0.0))
        exposure = float(ws.get("asset_exposure", 0.0))
        reversibility = float(ws.get("reversibility", 1.0))
        if defensive:
            return {
                "CHS": round(max(0.0, min(100.0, 100 - post_risk * 30)), 1),
                "ASS": round(max(0.0, min(100.0, 100 - exposure * 50)), 1),
                "SSS": round(max(0.0, min(100.0, 55 + reversibility * 30)), 1),
                "EES": round(max(0.0, min(100.0, post_risk * 20)), 1),
            }
        return {
            "CHS": round(max(0.0, min(100.0, 100 - post_risk * 70)), 1),
            "ASS": round(max(0.0, min(100.0, 100 - exposure * 90)), 1),
            "SSS": round(max(0.0, min(100.0, 50 - (1 - reversibility) * 40)), 1),
            "EES": round(max(0.0, min(100.0, post_risk * 60 + exposure * 30)), 1),
        }

    def _ws_to_timeline(self, ws: dict, defensive: bool) -> dict:
        """将 world_state 转换为图表所需时间线格式。"""
        scores = self._synth_scores([{"world_state": ws}], defensive=defensive)
        scores["posterior_risk"] = round(float(ws.get("posterior_risk", 0.0)) * 100, 2)
        scores["reversibility"] = round(float(ws.get("reversibility", 1.0)) * 100, 2)
        scores["cognitive_mode"] = ws.get("cognitive_mode", "SYSTEM_2")
        return scores

    def _find_bifurcation(
        self,
        log_a: List[dict],
        log_b: List[dict],
        scorer_a: Any,
        scorer_b: Any,
    ) -> Tuple[int, str]:
        """寻找两个分支差异最大的拐点。"""
        best_step = 0
        best_gap = -1.0
        best_reason = "初始判断已导致明显分化。"

        max_steps = min(len(scorer_a.history), len(scorer_b.history))
        for step_idx in range(max_steps):
            scores_a = scorer_a.history[step_idx]
            scores_b = scorer_b.history[step_idx]
            ass_gap = abs(scores_a.ASS - scores_b.ASS)
            chs_gap = abs(scores_a.CHS - scores_b.CHS)
            ees_gap = abs(scores_a.EES - scores_b.EES)
            risk_gap = abs(getattr(scores_a, "risk_score", 0.0) - getattr(scores_b, "risk_score", 0.0))
            total_gap = ass_gap * 0.45 + chs_gap * 0.2 + ees_gap * 0.15 + risk_gap * 0.2

            if total_gap <= best_gap:
                continue

            best_gap = total_gap
            best_step = step_idx
            action_a = (
                log_a[step_idx - 1].get("agent_action", "高风险操作")
                if step_idx > 0 and step_idx - 1 < len(log_a)
                else "起始动作"
            )
            action_b = (
                log_b[step_idx - 1].get("agent_action", "保护动作")
                if step_idx > 0 and step_idx - 1 < len(log_b)
                else "起始动作"
            )
            best_reason = (
                f"第 {step_idx} 步出现最大分叉：危险分支执行“{action_a}”，"
                f"防御分支选择“{action_b}”，导致资产与认知分数差距迅速拉开。"
            )

        return best_step, best_reason

    def _extract_triggers(self, branch_a_log: List[dict], branch_b_log: List[dict]) -> List[TriggerPoint]:
        """提取危险分支与防御分支中的关键触发点。"""
        trigger_points: List[TriggerPoint] = []

        for branch_name, logs in (("A", branch_a_log), ("B", branch_b_log)):
            for item in logs:
                principles = item.get("triggered_principles", [])
                if not principles and not item.get("is_protection_action"):
                    continue
                principle = "、".join(principles) if principles else "protection"
                trigger_points.append(
                    TriggerPoint(
                        step=int(item.get("step", 0)),
                        branch=branch_name,
                        triggered_principle=principle,
                        agent_action=item.get("agent_action", ""),
                        victim_response=item.get("victim_response", ""),
                        score_delta=item.get("score_delta", {}),
                        evidence_case_id=item.get("evidence_case_id"),
                        evidence_similarity=float(item.get("evidence_similarity", 0.0)),
                    )
                )

        trigger_points.sort(
            key=lambda point: (
                point.step,
                0 if point.branch == "A" else 1,
                -(point.score_delta.get("ASS", 0) - point.score_delta.get("CHS", 0)),
            )
        )
        return trigger_points[:8]

    def _generate_recommendations(self, profile: Any, triggers: List[TriggerPoint]) -> List[dict]:
        """生成个性化建议。"""
        recommendations: List[Dict[str, Any]] = []
        principles = "、".join(
            {point.triggered_principle for point in triggers if point.triggered_principle != "protection"}
        )

        if getattr(profile, "verification_habit", 5.0) < 4:
            recommendations.append(
                {
                    "priority": 1,
                    "action": "凡涉及资金、征信、账户安全操作，必须通过 APP 官方入口或公开客服电话二次核验。",
                    "reason": f"您的二次核验习惯评分为 {profile.verification_habit:.1f}，低于安全基线。",
                }
            )
        if getattr(profile, "decision_delay", 5.0) < 4:
            recommendations.append(
                {
                    "priority": 2,
                    "action": "建立“强制冷静 30 分钟”规则，任何‘立即处理’情境都不能当场转账或共享屏幕。",
                    "reason": "推演显示时间压力是本次攻击中的主要杠杆。",
                }
            )
        if getattr(profile, "help_seeking", 5.0) < 4:
            recommendations.append(
                {
                    "priority": 3,
                    "action": "为高风险决策指定家人/同学作为担保联系人，转账或提供验证码前先联系对方。",
                    "reason": "社会支持系统能显著提升认知防御能力。",
                }
            )
        if getattr(profile, "link_check_ability", 5.0) < 4:
            recommendations.append(
                {
                    "priority": 4,
                    "action": "把“看域名、查来电、比对收款账户”做成固定流程，并在手机里保存常用官方渠道。",
                    "reason": "当前链接与身份校验能力偏弱，容易被伪装渠道绕过。",
                }
            )
        if principles:
            recommendations.append(
                {
                    "priority": 5,
                    "action": "针对本次命中的劝诱原则做专项训练，例如复盘权威施压、稀缺制造和从众暗示的识别方式。",
                    "reason": f"本次分支中反复出现的操控原则为：{principles}。",
                }
            )

        recommendations.sort(key=lambda item: item["priority"])
        return recommendations[:3]

    def _compose_branch_summary(self, branch_name: str, scores: Any, log: List[dict]) -> str:
        """拼装分支摘要。"""
        steps = len(log)
        exposure_events = sum(1 for item in log if item.get("asset_exposure_coefficient", 0.0) > 0.05)
        protection_events = sum(1 for item in log if item.get("is_protection_action"))
        last_action = log[-1].get("agent_action", "无关键动作") if log else "无交互"
        label = "危险路径" if branch_name == "A" else "防御路径"
        return (
            f"分支 {branch_name}（{label}）共经历 {steps} 个步骤，资产暴露事件 {exposure_events} 次，"
            f"保护动作 {protection_events} 次。最终 CHS={scores.CHS:.1f}、ASS={scores.ASS:.1f}、"
            f"EES={scores.EES:.1f}，风险等级为 {scores.summary_risk_level()}。"
            f" 最后一个关键动作是“{last_action}”。"
        )

    def _compose_mainline_branch_summary(self, branch_name: str, log: List[dict]) -> str:
        if not log:
            return f"分支 {branch_name} 暂无轨迹。"
        last = log[-1].get("world_state", {})
        return (
            f"分支 {branch_name} 共 {len(log)} 步，最终 posterior_risk={last.get('posterior_risk', 0):.3f}，"
            f"reversibility={last.get('reversibility', 0):.3f}，"
            f"action=“{log[-1].get('action', log[-1].get('agent_action', ''))}”。"
        )

    def _generate_mainline_prescriptions(
        self,
        profile: Any,
        fork_comparison: Any,
        persona_state_vector: Optional[Any],
    ) -> List[Dict[str, Any]]:
        weak_verification = getattr(profile, "verification_habit", 5.0) < 5
        weak_help = getattr(profile, "help_seeking", 5.0) < 5
        fork_type = getattr(fork_comparison, "fork_point_type", "generic")
        open_step = fork_comparison.best_intervention_window.get("open_step", 1)
        close_step = fork_comparison.best_intervention_window.get("close_step", open_step + 1)
        prescriptions = [
            {
                "title": f"在 {fork_type} 节点前强制二次核验",
                "priority": 1,
                "target_failure_node": fork_type,
                "trigger_step": open_step,
                "window_open_step": open_step,
                "window_close_step": close_step,
                "rationale": "最佳干预窗口出现在高危分支进入不可逆操作前。",
                "recommended_actions": [
                    "切换到官方 APP / 官方回拨",
                    "暂停当前会话 10-30 分钟",
                    "不向陌生渠道继续提供验证码、屏幕或资金",
                ],
                "channel": "in_app",
                "expected_effect": "阻断 Fork 进入高危路径，恢复 System 2。",
                "fallback": "若无法核验，默认终止当前交互。",
            }
        ]
        if weak_verification:
            prescriptions.append(
                {
                    "title": "补强核验习惯缺口",
                    "priority": 2,
                    "target_failure_node": "verification_gap",
                    "trigger_step": open_step,
                    "window_open_step": open_step,
                    "window_close_step": close_step,
                    "rationale": "当前画像显示核验习惯不足，是本次弱点链核心节点。",
                    "recommended_actions": ["保存官方热线", "对链接与收款账户做固定核对"],
                    "channel": "training",
                    "expected_effect": "提高下次相似场景中的分支区分度。",
                    "fallback": "触发通用保护策略并提示人工协助。",
                }
            )
        if weak_help:
            prescriptions.append(
                {
                    "title": "在失败节点绑定外部求助",
                    "priority": 3,
                    "target_failure_node": "social_isolation",
                    "trigger_step": open_step,
                    "window_open_step": open_step,
                    "window_close_step": close_step,
                    "rationale": "引入亲友或同事可显著降低隔离诱导造成的误判。",
                    "recommended_actions": ["指定一位高风险决策联系人", "转账或共享屏幕前先通知对方"],
                    "channel": "social",
                    "expected_effect": "恢复外部校验回路。",
                    "fallback": "自动切换到保守默认拒绝策略。",
                }
            )
        return prescriptions
