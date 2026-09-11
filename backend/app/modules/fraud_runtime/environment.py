"""fraud_runtime environment — orchestrates rounds of interaction.

Manages the observation → decision → action → state-update cycle for
ThreatActor, UserTwin, and Verifier.  Supports Branch A (no verifier)
and Branch B (verifier provides information to UserTwin).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .agents import ThreatActor, UserTwin, Verifier
from .schema import FraudInteractionResult, InteractionStep


class FraudEnvironment:
    """Orchestrates multi-role fraud interaction rounds.

    Branch A: ThreatActor ↔ UserTwin only (no Verifier intervention).
    Branch B: ThreatActor ↔ UserTwin + Verifier provides information.
    """

    MAX_ROUNDS = 4  # Default 3–5 range; 4 is a reasonable default

    def __init__(
        self,
        threat_actor: ThreatActor,
        user_twin: UserTwin,
        verifier: Verifier,
        max_rounds: int = 4,
        llm_client=None,
        policy_mode: str = "auto",
    ):
        self.threat = threat_actor
        self.user = user_twin
        self.verifier = verifier
        self.max_rounds = max_rounds
        self.llm_client = llm_client
        self.policy_mode = str(policy_mode or "auto").strip().lower()

        # Shared environment state (visible to all agents as observation context)
        self._env_state: Dict[str, Any] = {
            "last_user_action": "",
            "last_threat_action": "",
            "verifier_info": None,
            "risk_flags": [],
            "round": 0,
        }

    # ── Round execution ────────────────────────────────────────────

    def run_round(
        self,
        branch: str,
        round_idx: int,
    ) -> List[InteractionStep]:
        """Execute one complete round of the interaction cycle.

        Order:
          1. ThreatActor observes environment → decides → acts
          2. UserTwin observes threat action (+ verifier info if Branch B) → decides → acts
          3. Verifier observes interaction (always, but only provides info in Branch B)
          4. WorldState updates
        """
        self._env_state["round"] = round_idx
        steps: List[InteractionStep] = []

        # 1. ThreatActor
        threat_obs = self.threat.observe(self._env_state)
        threat_action = self.threat.decide(threat_obs, self.llm_client)
        threat_delta = self.threat.update_state(
            threat_action, self._env_state.get("last_user_action", "")
        )
        self._env_state["last_threat_action"] = threat_action

        steps.append(InteractionStep(
            round=round_idx,
            actor_id=self.threat.state.actor_id,
            observation_refs=[f"round={round_idx}", f"user_last={self._env_state.get('last_user_action', '')}"],
            action=threat_action,
            target_actor_id=self.user.state.actor_id,
            state_delta={**threat_delta, "decision_source": self._decision_source(self.threat.last_decision_source)},
        ))

        # 2. Verifier observes (always — but only provides info in Branch B)
        verifier_obs = self.verifier.observe({
            "threat_action": threat_action,
            "user_action": self._env_state.get("last_user_action", ""),
            "threat_claimed_identity": self.threat.state.claimed_identity,
            "round": round_idx,
        })
        verifier_result = self.verifier.decide(verifier_obs, self.llm_client)
        verifier_action = verifier_result.get("action", "wait")
        verifier_info = verifier_result.get("info", {})
        self.verifier.update_state(verifier_action, verifier_info)

        steps.append(InteractionStep(
            round=round_idx,
            actor_id=self.verifier.state.actor_id,
            observation_refs=[f"threat_action={threat_action}"],
            action=verifier_action,
            target_actor_id="",
            state_delta={"action": verifier_action, "decision_source": self._decision_source(self.verifier.last_decision_source)},
            evidence_refs=self.verifier.state.evidence_refs[:3],
        ))

        # 3. UserTwin observes
        user_verifier_info = verifier_info if branch == "B" else None
        user_obs = self.user.observe(threat_action, user_verifier_info)
        user_action = self.user.decide(user_obs, self.llm_client)
        user_delta = self.user.update_state(user_action, threat_action)
        self._env_state["last_user_action"] = user_action

        if branch == "B" and verifier_info:
            self._env_state["verifier_info"] = verifier_info

        steps.append(InteractionStep(
            round=round_idx,
            actor_id=self.user.state.actor_id,
            observation_refs=(
                [f"threat_action={threat_action}"]
                + (["verifier_info_available"] if branch == "B" and verifier_info else [])
            ),
            action=user_action,
            target_actor_id=self.threat.state.actor_id,
            state_delta={**user_delta, "decision_source": self._decision_source(self.user.last_decision_source)},
        ))

        return steps

    # ── Branch execution ───────────────────────────────────────────

    def run_branch(self, branch: str) -> Dict[str, Any]:
        """Run a complete branch (A or B) for max_rounds."""
        trace: List[InteractionStep] = []
        risk_events: List[Dict[str, Any]] = []

        for r in range(self.max_rounds):
            round_steps = self.run_round(branch, r)
            trace.extend(round_steps)

            # Check for risk events
            for step in round_steps:
                if step.actor_id == self.threat.state.actor_id:
                    if step.action in (
                        "request_transfer",
                        "request_verification_code",
                        "request_screen_share",
                    ):
                        risk_events.append({
                            "round": r,
                            "actor": step.actor_id,
                            "action": step.action,
                            "severity": "high",
                        })
                if step.actor_id == self.user.state.actor_id:
                    if step.action == "stop_interaction":
                        risk_events.append({
                            "round": r,
                            "actor": step.actor_id,
                            "action": step.action,
                            "severity": "safe_termination",
                        })
                        break  # user ended interaction early

            # Stop if user terminated
            last_user_step = [s for s in round_steps if s.actor_id == self.user.state.actor_id]
            if last_user_step and last_user_step[-1].action == "stop_interaction":
                break

        user_final_state = self.user.state.to_dict()
        threat_final_state = self.threat.state.to_dict()

        return {
            "branch_id": branch,
            "rounds_executed": min(r + 1, self.max_rounds),
            "trace": [s.to_dict() for s in trace],
            "risk_events": risk_events,
            "final_user_state": user_final_state,
            "final_threat_state": threat_final_state,
            "user_complied": sum(
                1 for s in trace
                if s.actor_id == self.user.state.actor_id and s.action == "comply"
            ),
            "user_refused": sum(
                1 for s in trace
                if s.actor_id == self.user.state.actor_id
                and s.action in ("refuse", "verify", "seek_help")
            ),
        }

    # ── Full run (both branches) ────────────────────────────────────

    def run(self) -> FraudInteractionResult:
        """Run both Branch A and Branch B from the same initial state.

        Branch A: no verifier information given to UserTwin.
        Branch B: verifier information is shared with UserTwin.
        """
        # Snapshot initial states for Branch B reset
        import copy
        threat_init = copy.deepcopy(self.threat.state)
        user_init = copy.deepcopy(self.user.state)
        verifier_init = copy.deepcopy(self.verifier.state)
        env_init = copy.deepcopy(self._env_state)

        # Run Branch A
        branch_a = self.run_branch("A")

        # Reset to initial state for Branch B
        self.threat.state = threat_init
        self.user.state = user_init
        self.verifier.state = verifier_init
        self._env_state = env_init

        # Run Branch B
        branch_b = self.run_branch("B")

        # Build comparison
        comparison = self._compare_branches(branch_a, branch_b)

        # Collect all evidence refs used
        all_evidence = list(dict.fromkeys(
            self.verifier.state.evidence_refs
        ))

        decision_sources = [
            str(step.state_delta.get("decision_source") or "unknown")
            for step in [
                *[InteractionStep(**s) for s in branch_a.get("trace", [])],
                *[InteractionStep(**s) for s in branch_b.get("trace", [])],
            ]
        ]
        llm_decisions = sum(source == "llm" for source in decision_sources)
        fallback_decisions = len(decision_sources) - llm_decisions
        if self.policy_mode == "deterministic":
            runtime_mode, status, degraded_reasons = "deterministic_policy", "complete", []
        elif llm_decisions and not fallback_decisions:
            runtime_mode, status, degraded_reasons = "llm_driven", "complete", []
        elif llm_decisions:
            runtime_mode, status = "hybrid", "degraded"
            degraded_reasons = ["one_or_more_agent_decisions_used_deterministic_fallback"]
        else:
            runtime_mode, status = "deterministic_fallback", "degraded"
            degraded_reasons = [
                "llm_client_unavailable" if self.llm_client is None
                else "all_llm_agent_decisions_fell_back"
            ]

        return FraudInteractionResult(
            runtime_mode=runtime_mode,
            status=status,
            round_count=self.max_rounds,
            actors={
                "threat_actor": self.threat.state.to_dict(),
                "user_twin": self.user.state.to_dict(),
                "verifier": self.verifier.state.to_dict(),
            },
            interaction_trace=(
                [InteractionStep(**s) for s in branch_a.get("trace", [])]
                + [InteractionStep(**s) for s in branch_b.get("trace", [])]
            ),
            branch_a=branch_a,
            branch_b=branch_b,
            branch_comparison=comparison,
            evidence_refs=all_evidence,
            risk_events=branch_a.get("risk_events", [])
            + branch_b.get("risk_events", []),
            decision_provenance={
                "total_decisions": len(decision_sources),
                "llm_decisions": llm_decisions,
                "fallback_decisions": fallback_decisions,
                "sources": decision_sources,
            },
            degraded_reasons=degraded_reasons,
        )

    def _decision_source(self, original: str) -> str:
        if self.policy_mode == "deterministic":
            return "deterministic_policy"
        return original

    def _compare_branches(
        self, branch_a: Dict[str, Any], branch_b: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compare Branch A vs Branch B outcomes."""
        a_comply = branch_a.get("user_complied", 0)
        b_comply = branch_b.get("user_complied", 0)
        a_refuse = branch_a.get("user_refused", 0)
        b_refuse = branch_b.get("user_refused", 0)
        a_risks = len(branch_a.get("risk_events", []))
        b_risks = len(branch_b.get("risk_events", []))

        return {
            "branch_a_compliance": a_comply,
            "branch_b_compliance": b_comply,
            "branch_a_refusal": a_refuse,
            "branch_b_refusal": b_refuse,
            "compliance_delta": a_comply - b_comply,
            "branch_a_risk_events": a_risks,
            "branch_b_risk_events": b_risks,
            "summary": (
                f"Branch A: {a_comply} comply, {a_refuse} refuse, {a_risks} risk events. "
                f"Branch B: {b_comply} comply, {b_refuse} refuse, {b_risks} risk events."
            ),
        }
