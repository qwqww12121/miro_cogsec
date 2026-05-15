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
            "keywords": ["共享屏幕", "远程控制", "会议软件", "screen share"],
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
            "keywords": ["下载 app", "安装 app", "下载软件", "未知应用", "链接安装"],
            "severity": 0.83,
            "asset": "终端与账户",
        },
        {
            "type": "social_isolation",
            "keywords": ["不要告诉别人", "不要联系家人", "单独联系", "保密"],
            "severity": 0.74,
            "asset": "社会支持系统",
        },
        {
            "type": "fake_official_verification",
            "keywords": ["官方核验", "安全核验", "监管流程", "伪官方"],
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
    ) -> RuntimeResult:
        """Run the mainline runtime and return branch evidence."""
        started = time.perf_counter()
        initial_state = self.initialize_world_state(
            persona_state_vector=persona_state_vector,
            risk_graph_bundle=risk_graph_bundle,
            current_input=current_input,
        )

        try:
            fork_meta = self.select_primary_fork(current_input, risk_graph_bundle)
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

    def select_primary_fork(self, current_input: str, risk_graph_bundle: RiskGraphBundle) -> Dict[str, Any]:
        """Select the highest-severity fork point."""
        fork_points = list(risk_graph_bundle.fork_points)
        if fork_points:
            fork_points.sort(key=lambda item: (item.get("severity", 0.0), item.get("type", "")), reverse=True)
            return fork_points[0]

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

        fallback_rule = self.FORK_RULES[0]
        return {
            "id": f"fork:{fallback_rule['type']}",
            "type": fallback_rule["type"],
            "severity": 0.68,
            "asset": fallback_rule["asset"],
            "reason": "fallback fork selected",
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
        audit_flag = score_jump > 40
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
            best_intervention_window=self._best_intervention_window(branch_a, branch_b),
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
    ) -> Dict[str, Any]:
        best = None
        for step_a, step_b in zip(branch_a, branch_b):
            value = (
                step_a.world_state.intervention_window
                + (step_b.world_state.posterior_risk - step_a.world_state.posterior_risk)
                + (step_b.world_state.reversibility - step_a.world_state.reversibility)
            )
            if best is None or value > best[0]:
                best = (value, step_a.step, step_a.world_state.stage)
        if best is None:
            return {}
        return {
            "open_step": best[1],
            "close_step": min(best[1] + 1, len(branch_a)),
            "label": f"{best[2]} intervention window",
        }

    def _build_action_templates(self, branch: str, fork_meta: Dict[str, Any]) -> List[Dict[str, Any]]:
        fork_type = fork_meta["type"]
        risky_action = self._risky_action_label(fork_type)
        safe_action = self._safe_action_label(fork_type)
        if branch == "A":
            return [
                {"action": "Adversary raises urgency and authority pressure", "action_type": "pressure", "irreversible": False},
                {"action": "Primary Agent isolates from family and external verification", "action_type": "isolation", "irreversible": False},
                {"action": risky_action, "action_type": fork_type, "irreversible": fork_type in {"transfer_money", "verification_code"}},
                {"action": "Adversary escalates asset extraction through chained instructions", "action_type": "escalation", "irreversible": False},
                {"action": "WorldState crosses irreversible threshold and loss materializes", "action_type": "irreversible", "irreversible": True},
                {"action": "Audit Agent reconstructs compromised path for post-hoc defense", "action_type": "audit_reconstruction", "irreversible": False},
            ]
        return [
            {"action": "Primary Agent pauses and delays the decision", "action_type": "delay", "irreversible": False},
            {"action": safe_action, "action_type": "verification", "irreversible": False},
            {"action": "Primary Agent re-engages family or trusted peer for cross-check", "action_type": "help_seeking", "irreversible": False},
            {"action": "Audit Agent verifies evidence consistency and breaks the attack chain", "action_type": "audit_verification", "irreversible": False},
            {"action": "Asset exposure is contained and reversibility recovers", "action_type": "containment", "irreversible": False},
            {"action": "Intervention prescription is stored for future similar forks", "action_type": "prescription", "irreversible": False},
        ]

    def _risky_action_label(self, fork_type: str) -> str:
        mapping = {
            "transfer_money": "Primary Agent transfers funds to a fake safe account",
            "screen_share": "Primary Agent shares the screen and exposes secure workflow",
            "verification_code": "Primary Agent discloses the one-time verification code",
            "unknown_app_download": "Primary Agent installs an untrusted application package",
            "social_isolation": "Primary Agent cuts off family and peer contact",
            "fake_official_verification": "Primary Agent follows the fake official verification flow",
        }
        return mapping.get(fork_type, "Primary Agent complies with the attacker-led high-risk instruction")

    def _safe_action_label(self, fork_type: str) -> str:
        mapping = {
            "transfer_money": "Primary Agent verifies the transfer request through an official bank or platform channel",
            "screen_share": "Primary Agent rejects screen sharing and switches to an official support endpoint",
            "verification_code": "Primary Agent withholds the verification code and resets account trust channels",
            "unknown_app_download": "Primary Agent blocks the download and checks the publisher through official stores",
            "social_isolation": "Primary Agent restores contact with family and trusted peers before acting",
            "fake_official_verification": "Primary Agent exits the fake flow and performs an independent callback",
        }
        return mapping.get(fork_type, "Primary Agent verifies independently before any further action")

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
