"""MIRO-FISH mainline counterfactual runtime."""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any, Dict, List, Optional, Tuple

from .runtime_schema import (
    BranchTraceStep,
    ForkComparisonResult,
    PersonaStateVector,
    RiskGraphBundle,
    WorldStateSnapshot,
)


def _clamp(value: float, low: float, high: float) -> float:
    return min(high, max(low, float(value)))


@dataclass
class RuntimeResult:
    """Container returned by the runtime."""

    initial_world_state: WorldStateSnapshot
    fork_comparison: ForkComparisonResult
    degraded: bool = False
    degraded_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "initial_world_state": self.initial_world_state.to_dict(),
            "fork_comparison": self.fork_comparison.to_dict(),
            "degraded": self.degraded,
            "degraded_reason": self.degraded_reason,
        }


class MiroFishRuntime:
    """Counterfactual mainline engine for cognitive-defense inference."""

    DEFAULT_TIMEOUT_SEC = 15.0
    MAX_BRANCH_STEPS = 6
    BRANCH_GAP_MIN = 0.12

    FORK_RULES: List[Dict[str, Any]] = [
        {
            "type": "transfer_money",
            "keywords": ["转账", "汇款", "打款", "safe account", "安全账户", "保证金"],
            "severity": 0.96,
            "asset": "资金账户",
        },
        {
            "type": "screen_share",
            "keywords": ["共享屏幕", "屏幕共享", "远程控制", "会议软件", "screen share", "开启共享", "远程协助"],
            "severity": 0.88,
            "asset": "设备控制权",
        },
        {
            "type": "verification_code",
            "keywords": ["验证码", "动态码", "sms code", "verification code"],
            "severity": 0.92,
            "asset": "身份凭证",
        },
        {
            "type": "unknown_app_download",
            "keywords": ["下载 app", "安装 app", "下载软件", "未知应用", "链接安装", "下载app", "安装app", "的app", "的APP"],
            "severity": 0.83,
            "asset": "终端与账户",
        },
        {
            "type": "social_isolation",
            "keywords": ["不要告诉别人", "不要联系家人", "单独联系", "保密", "不要告诉任何人", "不能告诉", "办案纪律", "不许外传"],
            "severity": 0.74,
            "asset": "社会支持系统",
        },
        {
            "type": "fake_official_verification",
            "keywords": ["官方核验", "安全核验", "监管流程", "伪官方", "公安局", "民警", "警察局", "冒充公安", "警方通知", "安全账户核验"],
            "severity": 0.8,
            "asset": "信任边界",
        },
    ]

    def run(
        self,
        persona_state_vector: PersonaStateVector,
        risk_graph_bundle: RiskGraphBundle,
        current_input: str,
        deadline_sec: float = DEFAULT_TIMEOUT_SEC,
        scenario_type: str = "fraud_im",
    ) -> RuntimeResult:
        """Run the mainline runtime and return branch evidence."""
        started = time.perf_counter()
        initial_state = self.initialize_world_state(
            persona_state_vector=persona_state_vector,
            risk_graph_bundle=risk_graph_bundle,
            current_input=current_input,
        )

        try:
            fork_meta = self.select_primary_fork(current_input, risk_graph_bundle, scenario_type=scenario_type)
            branch_a = self._simulate_branch(
                branch="A",
                persona_state_vector=persona_state_vector,
                risk_graph_bundle=risk_graph_bundle,
                initial_state=initial_state,
                fork_meta=fork_meta,
                started=started,
                deadline_sec=deadline_sec,
            )
            branch_b = self._simulate_branch(
                branch="B",
                persona_state_vector=persona_state_vector,
                risk_graph_bundle=risk_graph_bundle,
                initial_state=initial_state,
                fork_meta=fork_meta,
                started=started,
                deadline_sec=deadline_sec,
            )
            comparison = self._compare_branches(
                branch_a=branch_a,
                branch_b=branch_b,
                fork_meta=fork_meta,
                risk_graph_bundle=risk_graph_bundle,
            )
            return RuntimeResult(initial_world_state=initial_state, fork_comparison=comparison)
        except TimeoutError:
            degraded = self._build_timeout_degraded_result(
                initial_state=initial_state,
                persona_state_vector=persona_state_vector,
                risk_graph_bundle=risk_graph_bundle,
            )
            return RuntimeResult(
                initial_world_state=initial_state,
                fork_comparison=degraded,
                degraded=True,
                degraded_reason="timeout > 15s -> downgrade local counterfactual depth",
            )

    def initialize_world_state(
        self,
        persona_state_vector: PersonaStateVector,
        risk_graph_bundle: RiskGraphBundle,
        current_input: str,
    ) -> WorldStateSnapshot:
        """Create the initial runtime state from persona and risk graph."""
        weakness_pressure = self._mean(
            [item.get("score", 0.0) for item in risk_graph_bundle.persona_weakness_hits]
        )
        evidence_hits = [item.get("label", item.get("id", "")) for item in risk_graph_bundle.evidence_items[:4]]
        persuasion_strength = len(risk_graph_bundle.persuasion_principles) * 0.07
        trust_pressure = (10.0 - persona_state_vector.digital_trust_boundary) / 10.0

        trust_score = _clamp(
            28
            + trust_pressure * 28
            + persona_state_vector.authority_compliance * 2.0
            + persuasion_strength * 30
            + len(evidence_hits) * 3.0,
            0,
            100,
        )
        asset_exposure = _clamp(
            len(risk_graph_bundle.asset_targets) * 0.08 + weakness_pressure * 0.01,
            0,
            1,
        )
        posterior_risk = _clamp(
            0.16
            + persona_state_vector.system1_bias * 0.015
            + weakness_pressure * 0.018
            + len(evidence_hits) * 0.045,
            0.01,
            0.96,
        )
        reversibility = _clamp(0.96 - asset_exposure * 0.3, 0, 1)
        intervention_window = _clamp(
            0.88
            - posterior_risk * 0.34
            - asset_exposure * 0.2
            + persona_state_vector.help_seeking_tendency * 0.01,
            0,
            1,
        )

        return WorldStateSnapshot(
            step=0,
            stage="intake",
            action=f"Input sanitized and mapped to {risk_graph_bundle.environment_context.get('scenario_type', 'unknown')} scene",
            trust_score=trust_score,
            cognitive_mode=persona_state_vector.cognitive_mode,
            asset_exposure=asset_exposure,
            intervention_window=intervention_window,
            posterior_risk=posterior_risk,
            reversibility=reversibility,
            evidence_hits=evidence_hits,
            persona_hits=[item.get("dimension", "") for item in risk_graph_bundle.persona_weakness_hits[:4]],
            notes=[current_input[:72] + ("..." if len(current_input) > 72 else "")],
        )

    # FORK rules for non-fraud scenarios — these are propagation/information
    # oriented, not financial fraud oriented.
    PROPAGATION_FORK_RULES: List[Dict[str, Any]] = [
        {
            "type": "info_propagation_risk",
            "keywords": ["传播", "转发", "扩散", "舆情", "事件", "网传", "流传", "消息"],
            "severity": 0.70,
            "asset": "信息生态",
        },
        {
            "type": "misinformation_risk",
            "keywords": ["谣言", "不实", "虚假信息", "误导", "失真", "夸大"],
            "severity": 0.75,
            "asset": "公众认知",
        },
    ]

    def select_primary_fork(
        self,
        current_input: str,
        risk_graph_bundle: RiskGraphBundle,
        scenario_type: str = "fraud_im",
    ) -> Dict[str, Any]:
        """Select the highest-severity fork point.

        Round 1 upgrade: scenario_type-aware fallback.  Non-fraud scenarios
        (public_opinion, event_propagation) no longer silently fall into
        fraud-oriented FORK rules like ``transfer_money``.
        """
        fork_points = list(risk_graph_bundle.fork_points)
        if fork_points:
            fork_points.sort(key=lambda item: (item.get("severity", 0.0), item.get("type", "")), reverse=True)
            return fork_points[0]

        is_fraud = scenario_type == "fraud_im"

        if is_fraud:
            lowered = (current_input or "").lower()
            for rule in self.FORK_RULES:
                if any(keyword.lower() in lowered for keyword in rule["keywords"]):
                    return {
                        "id": f"fork:{rule['type']}",
                        "type": rule["type"],
                        "severity": rule["severity"],
                        "asset": rule["asset"],
                        "reason": f"detected keyword match for {rule['type']}",
                    }

            # Document table 2.1: if nothing matches, fall back to the
            # highest-severity fork type so the dual-path always has a start.
            top = max(self.FORK_RULES, key=lambda item: item.get("severity", 0.0))
            return {
                "id": f"fork:{top['type']}",
                "type": top["type"],
                "severity": top["severity"],
                "asset": top["asset"],
                "reason": "no keyword match; fallback to highest-severity fork type",
            }

        # Non-fraud scenarios: try propagation-oriented rules first
        lowered = (current_input or "").lower()
        for rule in self.PROPAGATION_FORK_RULES:
            if any(keyword.lower() in lowered for keyword in rule["keywords"]):
                return {
                    "id": f"fork:{rule['type']}",
                    "type": rule["type"],
                    "severity": rule["severity"],
                    "asset": rule["asset"],
                    "reason": f"detected keyword match for {rule['type']} ({scenario_type})",
                }

        # No matching rule → highest-severity propagation fork for known
        # group scenes; unknown stays unmarked so the detector can clarify.
        if scenario_type in {"public_opinion", "event_propagation"}:
            top = max(self.PROPAGATION_FORK_RULES, key=lambda item: item.get("severity", 0.0))
            return {
                "id": f"fork:{top['type']}",
                "type": top["type"],
                "severity": top["severity"],
                "asset": top["asset"],
                "reason": f"no keyword match; fallback to highest-severity type ({scenario_type})",
            }
        return {
            "id": "fork:no_valid_fork",
            "type": "no_valid_fork",
            "severity": 0.0,
            "asset": "none",
            "reason": f"no valid fork identified for scenario_type={scenario_type}",
        }

    def _simulate_branch(
        self,
        branch: str,
        persona_state_vector: PersonaStateVector,
        risk_graph_bundle: RiskGraphBundle,
        initial_state: WorldStateSnapshot,
        fork_meta: Dict[str, Any],
        started: float,
        deadline_sec: float,
    ) -> List[BranchTraceStep]:
        trace: List[BranchTraceStep] = []
        current_state = initial_state
        action_templates = self._build_action_templates(branch, fork_meta)
        evidence_refs = [item.get("id", "") for item in risk_graph_bundle.evidence_items[:3]]
        persona_hits = [item.get("dimension", "") for item in risk_graph_bundle.persona_weakness_hits[:4]]
        principles = risk_graph_bundle.persuasion_principles[:3]
        if branch == "B":
            principles = ["verification", "help_seeking", "delay"]

        for step_index, template in enumerate(action_templates, start=1):
            self._check_deadline(started, deadline_sec)
            next_state, posterior_updates, audit_flag = self._advance_state(
                previous=current_state,
                branch=branch,
                step_index=step_index,
                action=template["action"],
                action_type=template["action_type"],
                fork_meta=fork_meta,
                persona_state_vector=persona_state_vector,
                evidence_refs=evidence_refs,
                persona_hits=persona_hits,
                principles=principles,
                irreversible=template["irreversible"],
            )
            trace.append(
                BranchTraceStep(
                    branch=branch,
                    step=step_index,
                    action=template["action"],
                    action_type=template["action_type"],
                    fork_point_type=fork_meta["type"],
                    world_state=next_state,
                    posterior_updates=posterior_updates,
                    evidence_refs=evidence_refs,
                    persona_hit_chain=persona_hits,
                    irreversible=template["irreversible"],
                    audit_flag=audit_flag,
                )
            )
            current_state = next_state
        return trace

    def _advance_state(
        self,
        previous: WorldStateSnapshot,
        branch: str,
        step_index: int,
        action: str,
        action_type: str,
        fork_meta: Dict[str, Any],
        persona_state_vector: PersonaStateVector,
        evidence_refs: List[str],
        persona_hits: List[str],
        principles: List[str],
        irreversible: bool,
    ) -> Tuple[WorldStateSnapshot, Dict[str, Any], bool]:
        risk_multiplier = fork_meta.get("severity", 0.75)
        control_buffer = persona_state_vector.system2_control / 10.0

        if branch == "A":
            posterior_delta = 0.08 + risk_multiplier * 0.12 + persona_state_vector.system1_bias * 0.008
            trust_delta = 8 + risk_multiplier * 10
            exposure_delta = 0.08 + risk_multiplier * 0.12
            reversibility_delta = -0.12 - risk_multiplier * 0.14
            window_delta = -0.11 - risk_multiplier * 0.08
            if irreversible:
                posterior_delta += 0.18
            stage = self._branch_stage("A", step_index, irreversible)
            mode = "SYSTEM_1" if step_index >= 2 or previous.cognitive_mode == "SYSTEM_1" else previous.cognitive_mode
            victim_response = "用户继续配合，对外部核验与求助的意愿下降。"
        else:
            posterior_delta = -0.06 - control_buffer * 0.05
            trust_delta = -8 - control_buffer * 10
            exposure_delta = -0.05 - control_buffer * 0.04
            reversibility_delta = 0.06 + control_buffer * 0.1
            window_delta = 0.03 + control_buffer * 0.08
            stage = self._branch_stage("B", step_index, irreversible)
            mode = "SYSTEM_2"
            victim_response = "用户转入核验路径，恢复延迟决策与外部求助。"

        posterior_risk = _clamp(previous.posterior_risk + posterior_delta, 0.01, 0.999)
        trust_score = _clamp(previous.trust_score + trust_delta, 0, 100)
        asset_exposure = _clamp(previous.asset_exposure + exposure_delta, 0, 1)
        reversibility = _clamp(previous.reversibility + reversibility_delta, 0, 1)
        if irreversible:
            reversibility = _clamp(reversibility - 0.25, 0, 1)
            asset_exposure = _clamp(asset_exposure + 0.12, 0, 1)
        intervention_window = _clamp(previous.intervention_window + window_delta, 0, 1)
        score_jump = abs(posterior_risk - previous.posterior_risk) * 100
        audit_flag = score_jump > 20
        notes = []
        if audit_flag:
            notes.append("score jump > 40 -> escalated to Audit Agent")
        if irreversible:
            notes.append("irreversible node reached")

        snapshot = WorldStateSnapshot(
            step=step_index,
            stage=stage,
            action=action,
            trust_score=trust_score,
            cognitive_mode=mode,
            asset_exposure=asset_exposure,
            intervention_window=intervention_window,
            posterior_risk=posterior_risk,
            reversibility=reversibility,
            evidence_hits=evidence_refs,
            persona_hits=persona_hits,
            notes=notes,
        )
        posterior_updates = {
            "prior": round(previous.posterior_risk, 3),
            "posterior": round(posterior_risk, 3),
            "delta": round(posterior_risk - previous.posterior_risk, 3),
            "triggered_principles": principles,
            "victim_response": victim_response,
            "stage": stage,
            "action_type": action_type,
            "trust_delta": round(trust_score - previous.trust_score, 2),
            "exposure_delta": round(asset_exposure - previous.asset_exposure, 3),
            "reversibility_delta": round(reversibility - previous.reversibility, 3),
        }
        return snapshot, posterior_updates, audit_flag

    def _compare_branches(
        self,
        branch_a: List[BranchTraceStep],
        branch_b: List[BranchTraceStep],
        fork_meta: Dict[str, Any],
        risk_graph_bundle: RiskGraphBundle,
    ) -> ForkComparisonResult:
        curve: List[Dict[str, Any]] = []
        updates: List[Dict[str, Any]] = []
        trajectory_scores: List[float] = []
        anomaly_flags = list(risk_graph_bundle.warnings)
        if risk_graph_bundle.hallucination_rollback:
            anomaly_flags.append("hallucination_rollback")

        for step_a, step_b in zip(branch_a, branch_b):
            risk_gap = abs(step_a.world_state.posterior_risk - step_b.world_state.posterior_risk)
            exposure_gap = abs(step_a.world_state.asset_exposure - step_b.world_state.asset_exposure)
            reversibility_gap = abs(step_a.world_state.reversibility - step_b.world_state.reversibility)
            trajectory_scores.append(risk_gap * 0.45 + exposure_gap * 0.3 + reversibility_gap * 0.25)
            curve.append(
                {
                    "step": step_a.step,
                    "branch_a_risk": round(step_a.world_state.posterior_risk, 3),
                    "branch_b_risk": round(step_b.world_state.posterior_risk, 3),
                    "branch_a_reversibility": round(step_a.world_state.reversibility, 3),
                    "branch_b_reversibility": round(step_b.world_state.reversibility, 3),
                }
            )
            updates.append(
                {
                    "step": step_a.step,
                    "branch_a": step_a.posterior_updates,
                    "branch_b": step_b.posterior_updates,
                }
            )
            if step_a.audit_flag or step_b.audit_flag:
                anomaly_flags.append("score_jump_audit")

        trajectory_gap = _clamp(self._mean(trajectory_scores), 0, 1)
        irreversibility_loss = _clamp(
            branch_a[-1].world_state.asset_exposure * 0.55
            + (1 - branch_a[-1].world_state.reversibility) * 0.45
            - branch_b[-1].world_state.asset_exposure * 0.25,
            0,
            1,
        )
        low_discriminability = trajectory_gap < self.BRANCH_GAP_MIN
        if low_discriminability:
            anomaly_flags.append("branch_divergence_too_small")

        delta_r_curve, loss_critical_step, window = self._best_intervention_window(branch_a, branch_b)
        return ForkComparisonResult(
            fork_point_type=fork_meta["type"],
            fork_node_id=fork_meta["id"],
            branch_a_state_trace=branch_a,
            branch_b_state_trace=branch_b,
            posterior_updates=updates,
            reversibility_curve=curve,
            persona_hit_chain=[item.get("dimension", "") for item in risk_graph_bundle.persona_weakness_hits[:5]],
            evidence_graph_consistency=risk_graph_bundle.consistency_score,
            trajectory_gap=trajectory_gap,
            irreversibility_loss=irreversibility_loss,
            low_discriminability=low_discriminability,
            anomaly_flags=sorted(set(flag for flag in anomaly_flags if flag)),
            best_intervention_window=window,
            delta_r_curve=delta_r_curve,
            loss_critical_step=loss_critical_step,
        )

    def _build_timeout_degraded_result(
        self,
        initial_state: WorldStateSnapshot,
        persona_state_vector: PersonaStateVector,
        risk_graph_bundle: RiskGraphBundle,
    ) -> ForkComparisonResult:
        fallback_a = BranchTraceStep(
            branch="A",
            step=1,
            action="Runtime timeout fallback: preserve highest-risk hypothesis for audit",
            action_type="timeout_fallback",
            fork_point_type="timeout_fallback",
            world_state=WorldStateSnapshot(
                step=1,
                stage="timeout_fallback",
                action="timeout fallback",
                trust_score=_clamp(initial_state.trust_score + 6, 0, 100),
                cognitive_mode="SYSTEM_1",
                asset_exposure=_clamp(initial_state.asset_exposure + 0.08, 0, 1),
                intervention_window=_clamp(initial_state.intervention_window - 0.08, 0, 1),
                posterior_risk=_clamp(initial_state.posterior_risk + 0.08, 0, 0.999),
                reversibility=_clamp(initial_state.reversibility - 0.1, 0, 1),
                evidence_hits=initial_state.evidence_hits,
                persona_hits=initial_state.persona_hits,
                notes=["degraded local model branch"],
            ),
            posterior_updates={"delta": 0.08, "victim_response": "timeout fallback"},
            evidence_refs=[item.get("id", "") for item in risk_graph_bundle.evidence_items[:2]],
            persona_hit_chain=initial_state.persona_hits,
            irreversible=False,
            audit_flag=False,
        )
        fallback_b = BranchTraceStep(
            branch="B",
            step=1,
            action="Runtime timeout fallback: issue generic verification guidance",
            action_type="timeout_fallback",
            fork_point_type="timeout_fallback",
            world_state=WorldStateSnapshot(
                step=1,
                stage="timeout_fallback",
                action="timeout fallback",
                trust_score=_clamp(initial_state.trust_score - 6, 0, 100),
                cognitive_mode="SYSTEM_2",
                asset_exposure=_clamp(initial_state.asset_exposure - 0.05, 0, 1),
                intervention_window=_clamp(initial_state.intervention_window + 0.05, 0, 1),
                posterior_risk=_clamp(initial_state.posterior_risk - 0.05, 0, 0.999),
                reversibility=_clamp(initial_state.reversibility + 0.05, 0, 1),
                evidence_hits=initial_state.evidence_hits,
                persona_hits=initial_state.persona_hits,
                notes=["degraded local model branch"],
            ),
            posterior_updates={"delta": -0.05, "victim_response": "timeout fallback"},
            evidence_refs=[item.get("id", "") for item in risk_graph_bundle.evidence_items[:2]],
            persona_hit_chain=initial_state.persona_hits,
            irreversible=False,
            audit_flag=False,
        )
        return ForkComparisonResult(
            fork_point_type="timeout_fallback",
            fork_node_id="fork:timeout",
            branch_a_state_trace=[fallback_a],
            branch_b_state_trace=[fallback_b],
            posterior_updates=[{"step": 1, "branch_a": fallback_a.posterior_updates, "branch_b": fallback_b.posterior_updates}],
            reversibility_curve=[{
                "step": 1,
                "branch_a_risk": fallback_a.world_state.posterior_risk,
                "branch_b_risk": fallback_b.world_state.posterior_risk,
                "branch_a_reversibility": fallback_a.world_state.reversibility,
                "branch_b_reversibility": fallback_b.world_state.reversibility,
            }],
            persona_hit_chain=initial_state.persona_hits,
            evidence_graph_consistency=risk_graph_bundle.consistency_score,
            trajectory_gap=0.08,
            irreversibility_loss=0.15,
            low_discriminability=True,
            anomaly_flags=["timeout_degraded", "branch_divergence_too_small"],
            best_intervention_window={"open_step": 1, "close_step": 1, "label": "fallback immediate verification"},
        )

    def _best_intervention_window(
        self,
        branch_a: List[BranchTraceStep],
        branch_b: List[BranchTraceStep],
    ) -> tuple:
        """Locate t* = argmax_{t < tc} ΔR(t), ΔR = R_continue − R_stoploss."""
        loss_critical_step = None
        for step in branch_a:
            if step.irreversible:
                loss_critical_step = step.step
                break
        if loss_critical_step is None:
            loss_critical_step = len(branch_a) + 1

        delta_r_curve: List[Dict[str, Any]] = []
        best = None
        for step_a, step_b in zip(branch_a, branch_b):
            delta_r = (
                step_a.world_state.posterior_risk
                - step_b.world_state.posterior_risk
            )
            delta_r_curve.append({
                "step": step_a.step,
                "delta_r": round(delta_r, 4),
                "r_continue": round(step_a.world_state.posterior_risk, 4),
                "r_stoploss": round(step_b.world_state.posterior_risk, 4),
            })
            if step_a.step >= loss_critical_step:
                continue
            if best is None or delta_r > best[0]:
                best = (delta_r, step_a.step, step_a.world_state.stage)
        if best is None:
            return delta_r_curve, loss_critical_step, {}
        return delta_r_curve, loss_critical_step, {
            "open_step": best[1],
            "close_step": min(best[1] + 1, len(branch_a)),
            "label": f"{best[2]} intervention window",
            "delta_r": round(best[0], 4),
            "loss_critical_step": loss_critical_step,
            "objective": "argmax_delta_r_before_tc",
        }

    def _build_action_templates(self, branch: str, fork_meta: Dict[str, Any]) -> List[Dict[str, Any]]:
        fork_type = fork_meta["type"]
        risky_action = self._risky_action_label(fork_type)
        safe_action = self._safe_action_label(fork_type)
        lbl = self._fork_specific_labels(fork_type)
        if branch == "A":
            return [
                {"action": lbl["a_pressure"], "action_type": "pressure", "irreversible": False},
                {"action": lbl["a_isolation"], "action_type": "isolation", "irreversible": False},
                {"action": risky_action, "action_type": fork_type, "irreversible": fork_type in {"transfer_money", "verification_code"}},
                {"action": lbl["a_escalation"], "action_type": "escalation", "irreversible": False},
                {"action": lbl["a_irreversible"], "action_type": "irreversible", "irreversible": True},
                {"action": lbl["a_aftermath"], "action_type": "audit_reconstruction", "irreversible": False},
            ]
        return [
            {"action": lbl["b_delay"], "action_type": "delay", "irreversible": False},
            {"action": safe_action, "action_type": "verification", "irreversible": False},
            {"action": lbl["b_help_seeking"], "action_type": "help_seeking", "irreversible": False},
            {"action": lbl["b_audit"], "action_type": "audit_verification", "irreversible": False},
            {"action": lbl["b_containment"], "action_type": "containment", "irreversible": False},
            {"action": lbl["b_prescription"], "action_type": "prescription", "irreversible": False},
        ]

    def _fork_specific_labels(self, fork_type: str) -> Dict[str, str]:
        labels: Dict[str, Dict[str, str]] = {
            "transfer_money": {
                "a_pressure": "攻击者以征信受损或账户冻结为由，要求受害者立即向'安全账户'转款完成核验",
                "a_isolation": "受害者被要求对家人保密并关闭第三方通讯，与外部核验渠道切断",
                "a_escalation": "攻击者声称'核验金额不足'，要求追加转款或提供验证码以完成账户解冻",
                "a_irreversible": "资金已转入攻击者控制账户，损失不可逆，受害者失去追回窗口",
                "a_aftermath": "对照整理这条转账路径，标出还能核对的银行记录和求助渠道",
                "b_delay": "受害者以'需向家人确认'为由暂停转款，要求对方提供可查询的官方文件",
                "b_help_seeking": "受害者拨打银行官方客服，确认账户无冻结记录，识破'安全账户'骗局",
                "b_audit": "对照转账指令与官方流程，证实'安全账户'为诈骗手法并阻断",
                "b_containment": "转账没有发生，当事人保存聊天和账号记录",
                "b_prescription": "给出停下来、打官网、告诉身边人的具体动作，见下方干预处方",
            },
            "screen_share": {
                "a_pressure": "攻击者以'系统检测到异常登录'为由，要求受害者立即开启屏幕共享配合处置",
                "a_isolation": "攻击者引导受害者关闭其他软件，声称'防止信号干扰核验系统'",
                "a_escalation": "攻击者趁屏幕共享实时获取账户密码，随即操控受害者账户执行转账",
                "a_irreversible": "屏幕共享期间账户凭证完全泄露，设备控制权已落入攻击者手中",
                "b_delay": "受害者察觉屏幕共享请求与官方流程不符，主动挂断并截图留存证据",
                "b_help_seeking": "受害者向家人说明情况后，通过官方客服确认该机构无远程核验业务",
                "b_audit": "审计Agent验证远程连接来源非官方域名，证实屏幕共享为社会工程手段",
            },
            "verification_code": {
                "a_pressure": "攻击者以'账户解冻必须验证身份'为由，要求受害者立即提供短信验证码",
                "a_isolation": "攻击者警告受害者'期间不得向他人透露，否则流程中断，后果自负'",
                "a_escalation": "攻击者利用验证码登录受害者账户，升级为批量资金转移操作",
                "a_irreversible": "账户控制权已通过验证码转移至攻击者，余额清零损失不可逆",
                "b_delay": "受害者以'需先核实来电身份'拒绝立即提供验证码，要求提供工号备查",
                "b_help_seeking": "受害者通过官方APP自主查看账户状态，确认无任何异常冻结记录",
                "b_audit": "审计Agent识别验证码请求实为账户登录行为，而非官方身份核验流程",
            },
            "unknown_app_download": {
                "a_pressure": "攻击者以'专用协查系统必须安装'为由，发送第三方APP安装包链接",
                "a_isolation": "攻击者要求受害者关闭手机安全防护，声称'防止误报影响协查系统运行'",
                "a_escalation": "恶意APP获取通讯录、短信读取及支付权限，实施静默后台资金转移",
                "a_irreversible": "恶意APP已获取完整设备权限，持续驻留并劫持支付与账户操作",
                "b_delay": "受害者拒绝通过陌生链接安装，要求提供官方应用商店正规下载渠道",
                "b_help_seeking": "受害者在应用商店搜索确认该应用不存在，判断为仿冒恶意软件",
                "b_audit": "审计Agent分析安装包签名证书，确认非官方机构发布并阻断安装流程",
            },
            "social_isolation": {
                "a_pressure": "攻击者以'案件保密规定'为由，要求受害者绝对不得向任何人透露通话内容",
                "a_isolation": "受害者停止与家人及朋友沟通，陷入信息茧房，完全依赖攻击者叙述",
                "a_escalation": "攻击者借受害者完全孤立状态，升级为资产控制与身份信息索取",
                "a_irreversible": "受害者在无外部监督下完成所有高风险操作，损失发生后无人知晓",
                "b_delay": "受害者对'保密要求'产生怀疑，要求对方出示书面通知后再配合",
                "b_help_seeking": "受害者将情况告知家人，共同通过官方渠道核实事件是否属实",
                "b_audit": "审计Agent识别社会隔离要求为诈骗经典手法，触发高危操作预警",
            },
            "fake_official_verification": {
                "a_pressure": "攻击者提供伪造工号和官方界面截图，声称受害者面临紧迫法律风险",
                "a_isolation": "攻击者要求受害者通过其指定渠道'核实身份'，切断与真实官方的联系",
                "a_escalation": "受害者完成伪造核实流程后，攻击者以'配合不足'为由要求继续操作",
                "a_irreversible": "受害者个人信息与账户凭证通过伪官方渠道全部泄露，无法撤销",
                "b_delay": "受害者要求对方提供可在官网查询的公示文件，拒绝通过陌生链接核实",
                "b_help_seeking": "受害者主动拨打官方公示号码，确认该工号不存在，识别为仿冒机构",
                "b_audit": "审计Agent比对来电号码与官方发布信息，识别仿冒号码并发出预警",
            },
        }
        no_valid_fork_labels = {
            "a_pressure": "系统未能识别明确的攻击行为模式，当前场景缺乏足够的风险信号进行分类",
            "a_isolation": "信息传播在无干预条件下自然扩散，受众依据各自偏见和社交圈进行信息处理",
            "a_escalation": "未经证实的信息在传播链中逐步失真，但缺乏明确的恶意操纵主体",
            "a_irreversible": "信息生态可能因持续失真而难以恢复至事实基线",
            "b_delay": "受众在接收到信息后暂缓转发，等待更多权威来源确认",
            "b_help_seeking": "受众主动搜索多方信息源进行交叉验证，降低单一信源的误导风险",
            "b_audit": "审计Agent识别当前场景缺少有效的FORK分类依据，建议增加人工研判",
        }
        info_propagation_labels = {
            "a_pressure": "高情绪强度的信息以未经核实的状态快速扩散，受众在信息不对称下产生认知偏差",
            "a_isolation": "受众在信息茧房中仅接触单一叙事，缺少多元信息源的有效补充",
            "a_escalation": "关键放大器节点持续转发未经证实内容，推动信息传播进入链式扩散阶段",
            "a_irreversible": "信息失真已达到临界规模，公众认知基线受到实质性影响",
            "a_aftermath": "对照整理传播路径，标出源头、放大器和仍可澄清的节点",
            "b_delay": "权威信息源及时发布初步情况说明，为受众提供官方参照基准",
            "b_help_seeking": "事实核查机构与权威媒体介入，对关键信息节点进行溯源和核实",
            "b_audit": "对照传播链中的信息版本与原始来源，识别失真节点",
            "b_containment": "官方说明和降权开始起作用，更多人停在观望，话题热度回落",
            "b_prescription": "给出澄清、接触关键节点和持续监测的具体动作，见下方干预处方",
        }
        misinformation_labels = {
            "a_pressure": "虚假或不实信息以耸人听闻的形式在社交网络中快速扩散，利用受众情绪进行传播",
            "a_isolation": "受众被误导性信息包围，缺少有效的纠偏信息输入渠道",
            "a_escalation": "虚假信息经过多层转发后产生变异，衍生出更极端或更具体的错误版本",
            "a_irreversible": "虚假信息已在公众认知中形成锚定效应，事后纠偏难以完全消除影响",
            "a_aftermath": "对照整理失真版本的传播路径，标出仍可更正的节点",
            "b_delay": "平台内容审核机制及时标注待核实内容，降低未确认信息的曝光权重",
            "b_help_seeking": "权威机构发布事实核查报告，逐条澄清关键信息节点的不实之处",
            "b_audit": "追踪虚假信息的传播路径，定位源头与关键放大节点",
            "b_containment": "核查标签和官方更正拦住继续裂变，外围接收面缩小",
            "b_prescription": "给出辟谣响应、关键节点接触和监测的具体动作，见下方干预处方",
        }
        default = {
            "a_pressure": "攻击者持续以紧迫性话术施压，要求受害者立即配合执行关键操作",
            "a_isolation": "受害者被要求保密并中断外部联系，陷入单一信息来源的封闭状态",
            "a_escalation": "攻击者通过连环指令逐步升级资产套取与控制范围",
            "a_irreversible": "世界状态越过不可逆阈值，受害者核心资产或凭证已泄露",
            "b_delay": "受害者主动暂停，要求对方提供可独立核实的官方证明后再行动",
            "b_help_seeking": "受害者向家人或可信同伴说明情况，共同核实事件真实性",
            "b_audit": "审计Agent验证攻击链证据一致性，识别欺骗节点并实施阻断",
        }
        labels["no_valid_fork"] = no_valid_fork_labels
        labels["info_propagation_risk"] = info_propagation_labels
        labels["misinformation_risk"] = misinformation_labels
        chosen = labels.get(fork_type, default)
        return self._ensure_closing_labels(chosen, fork_type)

    def _ensure_closing_labels(self, lbl: Dict[str, str], fork_type: str) -> Dict[str, str]:
        out = dict(lbl)
        opinion = fork_type in {"info_propagation_risk", "misinformation_risk", "no_valid_fork"}
        out.setdefault("a_aftermath", "对照整理这条路径，标出还能挽回或澄清的节点")
        if opinion:
            out.setdefault("b_containment", "澄清和降权开始起作用，更多人停在观望")
            out.setdefault("b_prescription", "给出澄清、接触关键节点和监测的具体动作，见下方干预处方")
        else:
            out.setdefault("b_containment", "高风险操作被拦住，当事人保存证据")
            out.setdefault("b_prescription", "给出核验、求助和拒绝继续的具体动作，见下方干预处方")
        return out

    def _risky_action_label(self, fork_type: str) -> str:
        mapping = {
            "transfer_money": "受害者将资金转入攻击者指定的所谓'安全账户'",
            "screen_share": "受害者开启屏幕共享，暴露敏感操作界面",
            "verification_code": "受害者将一次性验证码告知对方",
            "unknown_app_download": "受害者安装来源不明的第三方应用包",
            "social_isolation": "受害者切断与家人及外部核验渠道的联系",
            "fake_official_verification": "受害者按要求完成伪造的'官方核实'流程",
            "info_propagation_risk": "受众在未核实的情况下转发高情绪强度的信息，加速传播链扩散",
            "misinformation_risk": "受众在未核实的情况下转发疑似不实信息，扩大虚假叙事覆盖范围",
            "no_valid_fork": "系统在当前场景下未检测到明确的攻击性行为模式",
        }
        return mapping.get(fork_type, "受害者在攻击者引导下执行高风险操作")

    def _safe_action_label(self, fork_type: str) -> str:
        mapping = {
            "transfer_money": "受害者通过官方银行或平台渠道核实转账请求后拒绝操作",
            "screen_share": "受害者拒绝屏幕共享并转接官方客服核实",
            "verification_code": "受害者拒绝透露验证码并重置账户信任渠道",
            "unknown_app_download": "受害者拒绝下载并通过官方应用商店核查发布者信息",
            "social_isolation": "受害者先联系家人和可信同伴交叉核实后再行动",
            "fake_official_verification": "受害者退出伪造流程并通过独立回拨方式核实身份",
            "info_propagation_risk": "受众通过官方渠道核实信息后再决定是否转发",
            "misinformation_risk": "受众通过事实核查平台验证信息真实性后再决定传播行为",
            "no_valid_fork": "受众保持信息处理的中立状态，等待更多权威信息后再做判断",
        }
        return mapping.get(fork_type, "受害者独立核实后再决定是否执行下一步")

    def _branch_stage(self, branch: str, step_index: int, irreversible: bool) -> str:
        if branch == "A":
            stages = ["engagement", "pressure", "fork_execution", "escalation", "irreversibility", "audit"]
        else:
            stages = ["pause", "verification", "external_help", "audit_crosscheck", "containment", "prescription"]
        if irreversible:
            return "irreversibility"
        return stages[min(step_index - 1, len(stages) - 1)]

    def _check_deadline(self, started: float, deadline_sec: float) -> None:
        if deadline_sec <= 0:
            raise TimeoutError("deadline exhausted")
        if time.perf_counter() - started > deadline_sec:
            raise TimeoutError("runtime deadline exceeded")

    def _mean(self, values: List[float]) -> float:
        if not values:
            return 0.0
        return sum(values) / len(values)
