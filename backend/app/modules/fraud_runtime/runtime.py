"""fraud_runtime — main runtime that wires agents, environment, and fallback."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .agents import ThreatActor, UserTwin, Verifier
from .environment import FraudEnvironment
from .schema import (
    FraudInteractionResult,
    ThreatActorState,
    UserTwinState,
    VerifierState,
)


class FraudMultiRoleRuntime:
    """Top-level runtime for fraud multi-role interaction.

    Creates three agents (ThreatActor, UserTwin, Verifier) with
    independent state and memory, runs Branch A and Branch B from the
    same initial state, and returns a ``FraudInteractionResult``.

    When an LLM client is available, agent decisions are LLM-driven
    (shared backend, different system roles).  When unavailable, falls
    back to deterministic heuristics.
    """

    DEFAULT_MAX_ROUNDS = 4

    def __init__(self, llm_client=None, policy_mode: str = "auto"):
        self.llm_client = llm_client
        mode = str(policy_mode or "auto").strip().lower()
        self.policy_mode = mode if mode in {"auto", "llm", "deterministic"} else "auto"

    def run(
        self,
        scenario_text: str,
        cognitive_profile: Any = None,
        risk_graph_bundle: Any = None,
        scenario_type: str = "fraud_im",
        max_rounds: int = DEFAULT_MAX_ROUNDS,
    ) -> FraudInteractionResult:
        """Run full fraud multi-role interaction.

        Parameters
        ----------
        scenario_text:
            The (sanitized) scenario input text.
        cognitive_profile:
            ``CognitiveProfile`` instance for UserTwin initialisation.
        risk_graph_bundle:
            ``RiskGraphBundle`` providing evidence and fork data.
        scenario_type:
            Must be ``"fraud_im"`` — others skip this runtime.
        max_rounds:
            Number of interaction rounds (default 4, range 3–5).

        Returns
        -------
        FraudInteractionResult with both branch traces and comparison.
        """
        # ── Build agents ──────────────────────────────────────────
        threat = self._build_threat_actor(scenario_text, risk_graph_bundle)
        user_twin = self._build_user_twin(cognitive_profile)
        verifier = self._build_verifier(risk_graph_bundle)

        # ── Run environment ───────────────────────────────────────
        env = FraudEnvironment(
            threat_actor=threat,
            user_twin=user_twin,
            verifier=verifier,
            max_rounds=max_rounds,
            llm_client=self.llm_client,
            policy_mode=self.policy_mode,
        )

        result = env.run()

        return result

    # ── Agent builders ──────────────────────────────────────────────

    def _build_threat_actor(
        self,
        scenario_text: str,
        risk_graph_bundle: Any = None,
    ) -> ThreatActor:
        """Infer initial threat actor state from scenario text and RAG data."""
        claimed_identity = ""
        objective = "extract money or credentials"

        # Extract claimed identity from evidence / fork points
        if risk_graph_bundle is not None:
            forks = getattr(risk_graph_bundle, "fork_points", []) or []
            if forks:
                fork_type = forks[0].get("type", "") if isinstance(forks[0], dict) else getattr(forks[0], "type", "")
                identity_map = {
                    "transfer_money": "银行客服 / 征信中心",
                    "screen_share": "技术支持 / IT安全人员",
                    "verification_code": "平台客服 / 账户安全专员",
                    "unknown_app_download": "IT协查人员 / 系统管理员",
                    "social_isolation": "办案民警 / 监管调查员",
                    "fake_official_verification": "官方机构 / 监管部门",
                }
                claimed_identity = identity_map.get(fork_type, "")

            # Extract strategy info
            strategies = getattr(risk_graph_bundle, "attack_strategy_chain", []) or []
            if strategies:
                first = strategies[0]
                if isinstance(first, dict):
                    objective = first.get("description", objective)
                    if not claimed_identity:
                        claimed_identity = first.get("tactic_name", "")

        # Fallback: scan text for identity claims
        if not claimed_identity:
            identity_keywords = ["客服", "公安", "银行", "官方", "征信", "监管", "民警", "老师"]
            for kw in identity_keywords:
                if kw in (scenario_text or ""):
                    claimed_identity = kw
                    break

        return ThreatActor(
            actor_id="threat_actor",
            claimed_identity=claimed_identity,
            objective=objective,
        )

    def _build_user_twin(self, cognitive_profile: Any = None) -> UserTwin:
        """Build UserTwin from CognitiveProfile."""
        return UserTwin(
            actor_id="user_twin",
            cognitive_profile=cognitive_profile,
        )

    def _build_verifier(self, risk_graph_bundle: Any = None) -> Verifier:
        """Build Verifier with evidence and known patterns from RiskGraph."""
        evidence_refs: List[str] = []
        known_patterns: List[str] = []

        if risk_graph_bundle is not None:
            # Extract evidence refs
            evidence_items = getattr(risk_graph_bundle, "evidence_items", []) or []
            for item in evidence_items:
                if isinstance(item, dict):
                    eid = item.get("id", "") or item.get("label", "")
                else:
                    eid = getattr(item, "id", "") or getattr(item, "label", "")
                if eid:
                    evidence_refs.append(str(eid))

            # Extract scam patterns from fork points
            forks = getattr(risk_graph_bundle, "fork_points", []) or []
            for f in forks[:5]:
                if isinstance(f, dict):
                    pattern = f.get("type", "") or f.get("label", "")
                else:
                    pattern = getattr(f, "type", "") or getattr(f, "label", "")
                if pattern:
                    known_patterns.append(str(pattern))

            # Extract persuasion principles
            principles = getattr(risk_graph_bundle, "persuasion_principles", []) or []
            known_patterns.extend([str(p) for p in principles[:5]])

        return Verifier(
            actor_id="verifier",
            evidence_refs=evidence_refs,
            known_patterns=known_patterns,
        )


def adapt_fraud_to_fork_comparison(
    fraud_result: FraudInteractionResult,
    existing_fork: Any = None,
) -> Any:
    """Adapt FraudInteractionResult to a ForkComparison-compatible structure.

    This allows FraudMultiRoleRuntime to feed into RiskScorer and
    CounterfactualReporter without rewriting those modules.

    The fraud result is PRIMARY; optional existing FORK data is merged
    as supplementary evidence.
    """
    from ...modules.runtime_schema import (
        BranchTraceStep,
        ForkComparisonResult,
        WorldStateSnapshot,
    )

    def _risk_event_for_round(branch: Dict[str, Any], round_index: int) -> Optional[Dict[str, Any]]:
        return next(
            (event for event in branch.get("risk_events", [])
             if event.get("round") == round_index),
            None,
        )

    def _trace(branch: Dict[str, Any], branch_id: str) -> List[BranchTraceStep]:
        final_user = branch.get("final_user_state", {}) or {}
        raw_trace = branch.get("trace", []) or []

        # Reconstruct an outcome-risk trajectory from the observed user
        # actions.  The previous adapter copied the *final* awareness value to
        # every actor step in both branches.  Consequently a branch with four
        # `comply` actions and one with four `verify` actions both appeared as
        # posterior_risk=0.5, destroying the counterfactual signal.
        current_risk = 1.0 - float(final_user.get("risk_awareness", 0.5))
        user_actions = [
            str(item.get("action", ""))
            for item in raw_trace
            if item.get("actor_id") == "user_twin"
        ]
        for action in reversed(user_actions):
            if action == "comply":
                current_risk -= 0.12
            elif action in {"refuse", "verify", "seek_help", "stop_interaction"}:
                current_risk += 0.12
            elif action in {"delay", "ask_question"}:
                current_risk += 0.05
        current_risk = max(0.05, min(0.95, current_risk))

        risk_by_round: Dict[int, float] = {}
        for item in raw_trace:
            if item.get("actor_id") != "user_twin":
                continue
            action = str(item.get("action", ""))
            if action == "comply":
                current_risk += 0.12
            elif action in {"refuse", "verify", "seek_help", "stop_interaction"}:
                current_risk -= 0.12
            elif action in {"delay", "ask_question"}:
                current_risk -= 0.05
            current_risk = max(0.02, min(0.98, current_risk))
            risk_by_round[int(item.get("round", 0))] = current_risk

        steps: List[BranchTraceStep] = []
        for raw_step in raw_trace:
            round_index = int(raw_step.get("round", len(steps)))
            state_delta = dict(raw_step.get("state_delta") or {})
            event = _risk_event_for_round(branch, round_index)
            severity = str((event or {}).get("severity", "")).lower()
            exposure = 1.0 if severity == "high" else (0.6 if severity == "medium" else 0.0)
            posterior_risk = risk_by_round.get(round_index, current_risk)
            world_state = WorldStateSnapshot(
                step=round_index,
                stage=f"fraud_multi_role_branch_{branch_id}",
                action=str(raw_step.get("action", "")),
                trust_score=round(float(final_user.get("trust", 0.5)) * 100, 3),
                cognitive_mode="SYSTEM_2",
                asset_exposure=exposure,
                intervention_window=1.0 if branch_id == "B" else 0.0,
                posterior_risk=round(posterior_risk, 3),
                reversibility=round(1.0 - posterior_risk, 3),
                evidence_hits=list(raw_step.get("evidence_refs") or []),
                notes=[f"actor={raw_step.get('actor_id', '')}"],
            )
            state_delta.update({
                "actor_id": raw_step.get("actor_id", ""),
                "target_actor_id": raw_step.get("target_actor_id", ""),
                "fraud_runtime_marker": f"fraud:{branch_id}:{round_index}:{raw_step.get('actor_id', '')}",
            })
            steps.append(BranchTraceStep(
                branch=branch_id,
                step=round_index,
                action=str(raw_step.get("action", "")),
                action_type="fraud_interaction",
                fork_point_type="fraud_decision",
                world_state=world_state,
                posterior_updates=state_delta,
                evidence_refs=list(raw_step.get("evidence_refs") or []),
                persona_hit_chain=list(fraud_result.actors.get("verifier", {}).get("known_scam_patterns", [])),
                irreversible=exposure >= 1.0,
                audit_flag=bool(event),
            ))
        return steps

    branch_a = _trace(fraud_result.branch_a or {}, "A")
    branch_b = _trace(fraud_result.branch_b or {}, "B")
    if not branch_a and fraud_result.interaction_trace:
        # Older producers may only populate interaction_trace.  Preserve its
        # explicit actor/trace fields; do not infer A/B from round parity.
        branch_a = _trace(
            {"trace": [step.to_dict() for step in fraud_result.interaction_trace]},
            "A",
        )
    if not branch_b:
        branch_b = list(branch_a)

    threat_state = fraud_result.actors.get("threat_actor", {}) or {}
    # ``fraud_result.actors`` reflects the last executed branch (B).  Risk of
    # irreversible loss must be derived from the unprotected branch A, not
    # from the successfully protected branch.
    branch_a_user_state = (fraud_result.branch_a or {}).get("final_user_state", {}) or {}
    verifier_state = fraud_result.actors.get("verifier", {}) or {}
    comparison = fraud_result.branch_comparison or {}
    compliance_delta = abs(float(comparison.get("compliance_delta", 0.0)))
    trajectory_gap = round(compliance_delta / max(1, fraud_result.round_count), 3)
    risk_awareness = float(branch_a_user_state.get("risk_awareness", 0.5))
    risk_events = fraud_result.risk_events or []
    high_risk_events = sum(
        str(event.get("severity", "")).lower() == "high"
        for event in (fraud_result.branch_a or {}).get("risk_events", []) or []
    )
    irreversibility_loss = 1.0 - risk_awareness
    if high_risk_events:
        irreversibility_loss = max(
            irreversibility_loss,
            min(1.0, 0.5 + 0.25 * high_risk_events),
        )
    window = {}
    if risk_events:
        rounds = [int(event.get("round", 0)) for event in risk_events]
        window = {
            "open_step": min(rounds),
            "close_step": max(rounds),
            "label": "Fraud multi-role observed risk window",
        }

    # The optional FORK result is supplementary evidence only.  The typed
    # result returned here is built from FraudInteractionResult fields.
    result = ForkComparisonResult(
        fork_point_type="fraud_multi_role_primary",
        fork_node_id="fraud:primary",
        branch_a_state_trace=branch_a,
        branch_b_state_trace=branch_b,
        posterior_updates=[
            step.posterior_updates
            for step in branch_a + branch_b
        ],
        reversibility_curve=[
            {
                "step": step.step,
                "branch": step.branch,
                "reversibility": step.world_state.reversibility,
            }
            for step in branch_a + branch_b
        ],
        persona_hit_chain=list(verifier_state.get("known_scam_patterns", [])),
        evidence_graph_consistency=min(1.0, len(fraud_result.evidence_refs) / 5.0),
        trajectory_gap=trajectory_gap,
        irreversibility_loss=round(irreversibility_loss, 3),
        anomaly_flags=([] if fraud_result.status == "complete" else ["fraud_runtime_degraded"]),
        best_intervention_window=window,
    )
    setattr(result, "runtime_source", "fraud_multi_role")
    setattr(result, "supplementary_fork", existing_fork is not None)
    setattr(result, "threat_pressure_level", threat_state.get("pressure_level"))
    return result


def build_deterministic_fraud_result(
    fork_comparison: Any = None,
    risk_graph_bundle: Any = None,
) -> FraudInteractionResult:
    """Build a deterministic-fallback fraud result from existing FORK data.

    Used when the LLM client is unavailable and the multi-role runtime
    cannot be driven by LLM.
    """
    evidence_refs: List[str] = []
    if risk_graph_bundle is not None:
        items = getattr(risk_graph_bundle, "evidence_items", []) or []
        for item in items:
            eid = (item.get("id", "") or item.get("label", "")) if isinstance(item, dict) else getattr(item, "id", "")
            if eid:
                evidence_refs.append(str(eid))

    return FraudInteractionResult(
        runtime_mode="deterministic_fallback",
        status="degraded",
        round_count=0,
        actors={
            "threat_actor": ThreatActorState().to_dict(),
            "user_twin": UserTwinState().to_dict(),
            "verifier": VerifierState().to_dict(),
        },
        evidence_refs=evidence_refs,
        decision_provenance={"total_decisions": 0, "llm_decisions": 0, "fallback_decisions": 0, "sources": []},
        degraded_reasons=["fraud_runtime_not_executed"],
    )
