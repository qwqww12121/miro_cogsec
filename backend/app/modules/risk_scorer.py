"""动态风险评分模块。"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

from .runtime_schema import BranchTraceStep


@dataclass
class CounterfactualRiskBreakdown:
    """Mainline branch-delta risk output."""

    final_risk: float
    risk_level: str
    persona_prior: float
    attack_match: float
    trajectory_gap: float
    irreversibility_loss: float
    evidence_consistency: float
    fork_point_type: str
    low_discriminability: bool
    anomaly_flags: List[str]
    audit_required: bool
    metrics: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RiskScores:
    """四维风险评分 + 认知决策态势。"""

    CHS: float = 100.0
    ASS: float = 100.0
    SSS: float = 50.0
    EES: float = 0.0

    risk_score: float = 20.0
    cognitive_mode: str = "SYSTEM_2"
    reversibility: float = 1.0
    prior_probability: float = 0.2
    posterior_probability: float = 0.2

    def is_critical(self) -> bool:
        """判断是否达到危急状态。"""
        return self.risk_score >= 85 or self.ASS < 20 or self.CHS < 25

    def summary_risk_level(self) -> str:
        """返回汇总风险等级。"""
        score = float(self.risk_score)
        if score < 25:
            return "LOW"
        if score < 50:
            return "MEDIUM"
        if score < 75:
            return "HIGH"
        return "CRITICAL"

    def to_dict(self) -> Dict[str, float]:
        """转换为字典。"""
        payload = asdict(self)
        payload["risk_level"] = self.summary_risk_level()
        payload["critical"] = self.is_critical()
        return payload


CIALDINI_WEIGHTS: Dict[str, float] = {
    "authority": 2.0,
    "scarcity": 1.8,
    "social_proof": 1.5,
    "reciprocity": 1.2,
    "liking": 1.0,
    "commitment": 1.6,
    "unity": 0.8,
}

PRINCIPLE_TO_PROFILE_ATTR: Dict[str, str] = {
    "authority": "authority_compliance",
    "scarcity": "scarcity_sensitivity",
    "social_proof": "social_proof_sensitivity",
    "reciprocity": "trust_threshold",
    "liking": "trust_threshold",
    "commitment": "loss_aversion_threshold",
    "unity": "social_proof_sensitivity",
}


class RiskScorer:
    """按交互步骤滚动更新风险分数。"""

    def __init__(self, cognitive_profile: Any):
        self.profile = cognitive_profile
        self.scores = RiskScores(
            cognitive_mode=self._resolve_cognitive_mode(),
            reversibility=1.0,
            prior_probability=0.2,
            posterior_probability=0.2,
            risk_score=20.0,
        )
        self.history: List[RiskScores] = [self._clone_scores(self.scores)]

    def update_scores(
        self,
        agent_action: str,
        triggered_principles: List[str],
        is_protection_action: bool = False,
        asset_exposure_coefficient: float = 0.0,
    ) -> RiskScores:
        """根据当前步骤更新风险分数。"""
        principles = [principle.lower().strip() for principle in triggered_principles if principle]
        exposure_ratio = self._clamp(asset_exposure_coefficient, upper=1.0)

        chs_damage = 0.0
        for principle in principles:
            base_weight = CIALDINI_WEIGHTS.get(principle, 1.0)
            attr_name = PRINCIPLE_TO_PROFILE_ATTR.get(principle, "authority_compliance")
            vuln_score = getattr(self.profile, attr_name, 5.0) / 10.0
            chs_damage += base_weight * vuln_score * 3.5

        protection_bonus = 0.0
        if is_protection_action:
            protection_bonus = (
                getattr(self.profile, "decision_delay", 5.0) * 1.4
                + getattr(self.profile, "verification_habit", 5.0) * 1.6
                + getattr(self.profile, "help_seeking", 5.0) * 0.9
            ) / 3

        new_chs = self._clamp(self.scores.CHS - chs_damage + protection_bonus)
        new_ass = self._clamp(self.scores.ASS * (1 - exposure_ratio))

        action_lower = (agent_action or "").lower()
        help_delta = 6.0 if ("help" in action_lower or "求助" in agent_action or "核实" in agent_action) else -0.5
        if is_protection_action:
            help_delta += max(0.0, getattr(self.profile, "help_seeking", 5.0) - 5.0) * 0.3
        new_sss = self._clamp(self.scores.SSS + help_delta)

        if is_protection_action:
            ees_delta = -5.0
        else:
            ees_delta = 3.0 + len(principles) * 2.5 + exposure_ratio * 25
        new_ees = self._clamp(self.scores.EES + ees_delta)

        prior = self._clamp(self.scores.posterior_probability, 0.001, 0.999)
        p_obs_given_scam = self._estimate_observation_likelihood(
            principles=principles,
            exposure_ratio=exposure_ratio,
            is_protection_action=is_protection_action,
        )
        p_obs = self._estimate_observation_probability(p_obs_given_scam, prior)
        posterior = self._bayes_update(prior, p_obs_given_scam, p_obs)

        mode = self._resolve_cognitive_mode()
        reversibility = self._estimate_reversibility(agent_action, exposure_ratio, is_protection_action)
        risk_score = self._combine_risk_score(
            posterior=posterior,
            chs=new_chs,
            ass=new_ass,
            ees=new_ees,
            reversibility=reversibility,
            mode=mode,
        )

        self.scores = RiskScores(
            CHS=round(new_chs, 2),
            ASS=round(new_ass, 2),
            SSS=round(new_sss, 2),
            EES=round(new_ees, 2),
            risk_score=round(risk_score, 2),
            cognitive_mode=mode,
            reversibility=round(reversibility, 3),
            prior_probability=round(prior, 4),
            posterior_probability=round(posterior, 4),
        )
        self.history.append(self._clone_scores(self.scores))
        return self.scores

    def apply_log(self, log: List[Dict[str, Any]]) -> RiskScores:
        """批量应用日志步骤。"""
        for item in log:
            self.update_scores(
                agent_action=item.get("agent_action", ""),
                triggered_principles=item.get("triggered_principles", []),
                is_protection_action=item.get("is_protection_action", False),
                asset_exposure_coefficient=item.get("asset_exposure_coefficient", 0.0),
            )
        return self.scores

    def get_score_timeline(self) -> List[dict]:
        """获取时间线形式的分数序列。"""
        return [
            {
                "t": index,
                "CHS": score.CHS,
                "ASS": score.ASS,
                "SSS": score.SSS,
                "EES": score.EES,
                "risk_score": score.risk_score,
                "cognitive_mode": score.cognitive_mode,
                "reversibility": score.reversibility,
                "posterior_probability": score.posterior_probability,
            }
            for index, score in enumerate(self.history)
        ]

    def reset(self, scores: Optional[RiskScores] = None) -> None:
        """重置评分器。"""
        self.scores = scores or RiskScores()
        self.history = [self._clone_scores(self.scores)]

    def evaluate_counterfactual(
        self,
        branch_a_state_trace: List[Any],
        branch_b_state_trace: List[Any],
        fork_point_type: str,
        posterior_updates: List[Dict[str, Any]],
        reversibility_curve: List[Dict[str, Any]],
        persona_hit_chain: List[str],
        evidence_graph_consistency: float,
        anomaly_flags: Optional[List[str]] = None,
        irreversibility_loss: Optional[float] = None,
        fork_count: int = 1,
    ) -> CounterfactualRiskBreakdown:
        """Score the mainline risk from branch evidence instead of scenario text."""
        branch_a = [self._branch_payload(item) for item in branch_a_state_trace]
        branch_b = [self._branch_payload(item) for item in branch_b_state_trace]
        anomaly_flags = list(anomaly_flags or [])

        persona_prior = self._estimate_persona_prior()
        attack_match = self._estimate_attack_match(persona_hit_chain, posterior_updates)
        trajectory_gap = self._estimate_trajectory_gap(branch_a, branch_b)
        irreversibility_loss = (
            float(irreversibility_loss)
            if irreversibility_loss is not None
            else self._estimate_irreversibility_loss(reversibility_curve, branch_a, branch_b)
        )
        evidence_consistency = self._clamp(evidence_graph_consistency, 0.0, 1.0)
        low_discriminability = trajectory_gap < 0.12 or "branch_divergence_too_small" in anomaly_flags
        if low_discriminability and "branch_divergence_too_small" not in anomaly_flags:
            anomaly_flags.append("branch_divergence_too_small")

        product = max(
            0.0001,
            persona_prior
            * attack_match
            * max(0.1, trajectory_gap)
            * max(0.1, irreversibility_loss)
            * max(0.1, evidence_consistency),
        )
        fork_bonus = min(1.20, 1.0 + max(0, fork_count - 1) * 0.04)
        # Five independent 0..1 factors are combined as a geometric mean.
        # Using 0.55 here (instead of 1/5) compressed even five strong signals
        # into a LOW score; e.g. an obvious scam with T0 hits became 9.81/100.
        final_risk = round(min(100.0, (product ** (1.0 / 5.0)) * 100.0 * fork_bonus), 2)
        risk_level = self._risk_level_from_score(final_risk)
        audit_required = "score_jump_audit" in anomaly_flags or final_risk >= 85.0

        metrics = {
            "trajectory_gap": round(trajectory_gap, 3),
            "branch_a_final_risk": round(branch_a[-1]["posterior_risk"], 3) if branch_a else 0.0,
            "branch_b_final_risk": round(branch_b[-1]["posterior_risk"], 3) if branch_b else 0.0,
            "branch_a_final_reversibility": round(branch_a[-1]["reversibility"], 3) if branch_a else 0.0,
            "branch_b_final_reversibility": round(branch_b[-1]["reversibility"], 3) if branch_b else 0.0,
            "persona_hit_chain_length": len(persona_hit_chain or []),
            "fork_point_type": fork_point_type,
        }

        return CounterfactualRiskBreakdown(
            final_risk=final_risk,
            risk_level=risk_level,
            persona_prior=round(persona_prior, 3),
            attack_match=round(attack_match, 3),
            trajectory_gap=round(trajectory_gap, 3),
            irreversibility_loss=round(irreversibility_loss, 3),
            evidence_consistency=round(evidence_consistency, 3),
            fork_point_type=fork_point_type,
            low_discriminability=low_discriminability,
            anomaly_flags=sorted(set(anomaly_flags)),
            audit_required=audit_required,
            metrics=metrics,
        )

    def _resolve_cognitive_mode(self) -> str:
        time_pressure = float(getattr(self.profile, "time_pressure", 5.0))
        emotional_volatility = float(getattr(self.profile, "emotional_volatility", 5.0))
        if time_pressure > 7 and emotional_volatility > 7:
            return "SYSTEM_1"
        return "SYSTEM_2"

    def _estimate_persona_prior(self) -> float:
        if hasattr(self.profile, "to_persona_state_vector"):
            vector = self.profile.to_persona_state_vector()
            prior = (
                vector.authority_compliance
                + vector.time_pressure_sensitivity
                + vector.financial_stress
                + vector.loss_aversion
                + vector.fomo_susceptibility
                + (10.0 - vector.digital_trust_boundary)
            ) / 60.0
            return self._clamp(prior, 0.05, 1.0)
        if hasattr(self.profile, "overall_vulnerability_score"):
            return self._clamp(self.profile.overall_vulnerability_score() / 100.0, 0.05, 1.0)
        return 0.5

    def _estimate_attack_match(
        self,
        persona_hit_chain: List[str],
        posterior_updates: List[Dict[str, Any]],
    ) -> float:
        principle_hits = 0
        for item in posterior_updates or []:
            branch_a = item.get("branch_a", {})
            principle_hits += len(branch_a.get("triggered_principles", []))
        raw = 0.35 + len(persona_hit_chain or []) * 0.07 + principle_hits * 0.03
        return self._clamp(raw, 0.1, 1.0)

    def _estimate_trajectory_gap(self, branch_a: List[Dict[str, Any]], branch_b: List[Dict[str, Any]]) -> float:
        scores = []
        for step_a, step_b in zip(branch_a, branch_b):
            risk_gap = abs(step_a["posterior_risk"] - step_b["posterior_risk"])
            exposure_gap = abs(step_a["asset_exposure"] - step_b["asset_exposure"])
            reversibility_gap = abs(step_a["reversibility"] - step_b["reversibility"])
            scores.append(risk_gap * 0.45 + exposure_gap * 0.3 + reversibility_gap * 0.25)
        return self._clamp(sum(scores) / max(1, len(scores)), 0.0, 1.0)

    def _estimate_irreversibility_loss(
        self,
        reversibility_curve: List[Dict[str, Any]],
        branch_a: List[Dict[str, Any]],
        branch_b: List[Dict[str, Any]],
    ) -> float:
        if reversibility_curve:
            best = max(
                (
                    item.get("branch_b_reversibility", 0.0)
                    - item.get("branch_a_reversibility", 0.0)
                    + item.get("branch_a_risk", 0.0)
                    - item.get("branch_b_risk", 0.0)
                )
                for item in reversibility_curve
            )
            return self._clamp(best / 2.0, 0.0, 1.0)
        if branch_a and branch_b:
            raw = (
                branch_a[-1]["asset_exposure"]
                + (1 - branch_a[-1]["reversibility"])
                - branch_b[-1]["asset_exposure"] * 0.3
            )
            return self._clamp(raw, 0.0, 1.0)
        return 0.3

    def _risk_level_from_score(self, score: float) -> str:
        if score < 25:
            return "LOW"
        if score < 50:
            return "MEDIUM"
        if score < 75:
            return "HIGH"
        return "CRITICAL"

    def _branch_payload(self, item: Any) -> Dict[str, Any]:
        if isinstance(item, BranchTraceStep):
            world_state = item.world_state
            return {
                "posterior_risk": world_state.posterior_risk,
                "asset_exposure": world_state.asset_exposure,
                "reversibility": world_state.reversibility,
                "trust_score": world_state.trust_score,
            }
        if hasattr(item, "world_state"):
            world_state = getattr(item, "world_state")
            return {
                "posterior_risk": getattr(world_state, "posterior_risk", 0.0),
                "asset_exposure": getattr(world_state, "asset_exposure", 0.0),
                "reversibility": getattr(world_state, "reversibility", 0.0),
                "trust_score": getattr(world_state, "trust_score", 0.0),
            }
        if isinstance(item, dict):
            world_state = item.get("world_state", item)
            return {
                "posterior_risk": float(world_state.get("posterior_risk", 0.0)),
                "asset_exposure": float(world_state.get("asset_exposure", 0.0)),
                "reversibility": float(world_state.get("reversibility", 0.0)),
                "trust_score": float(world_state.get("trust_score", 0.0)),
            }
        return {
            "posterior_risk": 0.0,
            "asset_exposure": 0.0,
            "reversibility": 0.0,
            "trust_score": 0.0,
        }

    def _estimate_observation_likelihood(
        self,
        principles: List[str],
        exposure_ratio: float,
        is_protection_action: bool,
    ) -> float:
        if is_protection_action:
            return self._clamp(0.18 + exposure_ratio * 0.2, 0.05, 0.8)

        principle_pressure = min(1.0, len(principles) * 0.18)
        profile_pressure = (
            float(getattr(self.profile, "authority_compliance", 5.0))
            + float(getattr(self.profile, "scarcity_sensitivity", 5.0))
            + float(getattr(self.profile, "trust_threshold", 5.0))
        ) / 30.0
        return self._clamp(0.35 + principle_pressure + profile_pressure * 0.3 + exposure_ratio * 0.4, 0.05, 0.99)

    def _estimate_observation_probability(self, p_obs_given_scam: float, prior: float) -> float:
        safe_signal = 0.28
        return self._clamp(p_obs_given_scam * prior + safe_signal * (1 - prior), 0.01, 0.999)

    def _bayes_update(self, prior: float, p_obs_given_scam: float, p_obs: float) -> float:
        posterior = (p_obs_given_scam * prior) / max(1e-6, p_obs)
        return self._clamp(posterior, 0.001, 0.999)

    def _estimate_reversibility(self, agent_action: str, exposure_ratio: float, is_protection_action: bool) -> float:
        action = (agent_action or "").lower()
        if is_protection_action:
            return self._clamp(0.85 - exposure_ratio * 0.2, 0.0, 1.0)

        irreversible_markers = ["转账", "汇款", "验证码", "银行卡", "提款", "withdraw", "transfer"]
        if any(marker in action for marker in irreversible_markers):
            return self._clamp(0.2 - exposure_ratio * 0.15, 0.0, 1.0)
        return self._clamp(0.65 - exposure_ratio * 0.35, 0.0, 1.0)

    def _combine_risk_score(
        self,
        posterior: float,
        chs: float,
        ass: float,
        ees: float,
        reversibility: float,
        mode: str,
    ) -> float:
        posterior_score = posterior * 100.0
        state_risk = (100.0 - chs) * 0.3 + (100.0 - ass) * 0.45 + ees * 0.25
        mode_multiplier = 1.12 if mode == "SYSTEM_1" else 0.96
        reversibility_penalty = (1.0 - reversibility) * 18.0
        return self._clamp((posterior_score * 0.55 + state_risk * 0.45) * mode_multiplier + reversibility_penalty)

    def _clamp(self, value: float, lower: float = 0.0, upper: float = 100.0) -> float:
        return min(upper, max(lower, float(value)))

    def _clone_scores(self, scores: RiskScores) -> RiskScores:
        return RiskScores(
            CHS=scores.CHS,
            ASS=scores.ASS,
            SSS=scores.SSS,
            EES=scores.EES,
            risk_score=scores.risk_score,
            cognitive_mode=scores.cognitive_mode,
            reversibility=scores.reversibility,
            prior_probability=scores.prior_probability,
            posterior_probability=scores.posterior_probability,
        )
