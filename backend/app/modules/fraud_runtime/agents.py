"""fraud_runtime agents — ThreatActor, UserTwin, Verifier.

Each agent has: observation → private state → memory → decision → action
→ state update → next observation.  They are NOT independent LLM wrappers;
they share a single LLM backend but maintain separate system roles,
memories, and state.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .schema import ThreatActorState, UserTwinState, VerifierState

# ── Allowed actions per role ─────────────────────────────────────────

THREAT_ACTOR_ACTIONS = [
    "request_transfer",
    "request_verification_code",
    "request_screen_share",
    "request_download",
    "apply_urgency",
    "apply_authority",
    "apply_isolation",
    "change_story",
    "respond_to_question",
]

USER_TWIN_ACTIONS = [
    "comply",
    "delay",
    "ask_question",
    "verify",
    "refuse",
    "seek_help",
    "stop_interaction",
]

VERIFIER_ACTIONS = [
    "verify_identity",
    "cross_check_claim",
    "identify_risk_signal",
    "provide_safe_action",
    "request_more_evidence",
    "wait",
]


# ── Helper ───────────────────────────────────────────────────────────


def _pick_action(choices: List[str], index: int) -> str:
    return choices[index % len(choices)]


# ── ThreatActor ──────────────────────────────────────────────────────


class ThreatActor:
    """Scammer agent with private identity, tactic, and memory."""

    SYSTEM_ROLE = (
        "You are a scammer engaged in a fraud interaction. "
        "You are trying to convince a target to take harmful actions "
        "(transfer money, share a verification code, download an app, "
        "share their screen, or isolate themselves). "
        "You adapt your tactics based on the target's responses. "
        "You apply urgency, authority, or isolation as needed."
    )

    def __init__(
        self,
        actor_id: str = "threat_actor",
        claimed_identity: str = "",
        objective: str = "extract money or credentials",
    ):
        self.state = ThreatActorState(
            actor_id=actor_id,
            claimed_identity=claimed_identity,
            objective=objective,
        )
        self.last_decision_source = "not_run"

    def observe(self, environment: Dict[str, Any]) -> Dict[str, Any]:
        """Build observation from environment state."""
        return {
            "last_user_action": environment.get("last_user_action", ""),
            "verifier_info_available": bool(environment.get("verifier_info")),
            "current_risk_flags": environment.get("risk_flags", []),
            "round": environment.get("round", 0),
        }

    def decide(
        self,
        observation: Dict[str, Any],
        llm_client=None,
    ) -> str:
        """Choose next action — via LLM or deterministic heuristic.

        The deterministic heuristic is a simple state machine used when
        no LLM is available.  It cycles through pressure → specific ask
        → escalate based on user compliance.
        """
        if llm_client is not None:
            return self._llm_decide(observation, llm_client)
        self.last_decision_source = "deterministic_no_client"
        return self._deterministic_decide(observation)

    def _deterministic_decide(self, observation: Dict[str, Any]) -> str:
        """Deterministic fallback — simple escalation pattern."""
        last_user = observation.get("last_user_action", "")
        round_num = observation.get("round", 0)
        mem_len = len(self.state.memory)

        # If the user is complying, escalate the ask
        if last_user in ("comply", ""):
            escalations = [
                "apply_urgency",
                "request_verification_code",
                "request_transfer",
                "apply_authority",
                "request_screen_share",
                "apply_isolation",
                "request_download",
                "change_story",
            ]
            return escalations[min(round_num, len(escalations) - 1)]

        # If the user is resisting, switch tactics
        if last_user in ("refuse", "verify", "seek_help"):
            if mem_len < 3:
                return "change_story"
            return "apply_authority"

        # If the user is delaying or asking
        if last_user in ("delay", "ask_question"):
            return "apply_urgency"

        return "request_transfer"

    def _llm_decide(
        self,
        observation: Dict[str, Any],
        llm_client,
    ) -> str:
        """Use shared LLM with a threat-actor system prompt."""
        import json

        messages = [
            {"role": "system", "content": self.SYSTEM_ROLE},
            {"role": "system", "content": (
                f"Your claimed identity: {self.state.claimed_identity}. "
                f"Your objective: {self.state.objective}. "
                f"Current tactic: {self.state.current_tactic}. "
                f"Pressure level: {self.state.pressure_level:.2f}. "
                f"Previous actions: {', '.join(self.state.previous_actions[-5:] or ['none'])}. "
                f"Memory: {'; '.join(self.state.memory[-5:] or ['none'])}."
            )},
            {"role": "system", "content": (
                "Choose exactly one next action from this list and return only the action token: "
                + ", ".join(THREAT_ACTOR_ACTIONS)
                + ". Do not explain or add punctuation."
            )},
            {"role": "user", "content": json.dumps(observation, ensure_ascii=False)},
        ]
        try:
            response = llm_client.chat(
                messages,
                temperature=0.7,
                max_tokens=128,
            )
            # Extract action from response
            for action in THREAT_ACTOR_ACTIONS:
                if action in (response or ""):
                    self.last_decision_source = "llm"
                    return action
            self.last_decision_source = "deterministic_unparsed_llm"
            return "apply_urgency"
        except Exception:
            self.last_decision_source = "deterministic_llm_error"
            return self._deterministic_decide(observation)

    def update_state(self, action: str, user_response: str) -> Dict[str, Any]:
        """Apply action and observed response to private state."""
        self.state.previous_actions.append(action)
        self.state.memory.append(f"action={action} response={user_response[:120]}")

        # Adjust pressure based on compliance
        if user_response in ("comply",):
            self.state.pressure_level = min(1.0, self.state.pressure_level + 0.05)
        elif user_response in ("refuse", "verify", "seek_help", "stop_interaction"):
            self.state.pressure_level = min(1.0, self.state.pressure_level + 0.1)

        if action == "change_story":
            self.state.current_tactic = "adapted_story"
        elif action in ("apply_urgency", "apply_authority", "apply_isolation"):
            self.state.current_tactic = action
            self.state.pressure_level = min(1.0, self.state.pressure_level + 0.08)

        return {
            "actor_id": self.state.actor_id,
            "action": action,
            "pressure_delta": round(self.state.pressure_level - 0.5, 3),
            "tactic": self.state.current_tactic,
        }


# ── UserTwin ──────────────────────────────────────────────────────────


class UserTwin:
    """User digital twin — reacts based on CognitiveProfile-derived state.

    Mapping rules (all fields divided by 10 to get 0.0–1.0 range):
      trust            ← trust_threshold
      verification_tendency ← verification_habit
      urgency_sensitivity   ← time_pressure
      compliance_tendency   ← authority_compliance
      risk_awareness        ← risk_recovery_awareness
      cognitive_load        ← cognitive_load
    """

    SYSTEM_ROLE = (
        "You are a potential scam target on an instant-messaging platform. "
        "You are talking to someone who may or may not be legitimate. "
        "You have a certain level of trust, verification habits, "
        "urgency sensitivity, compliance tendency, risk awareness, "
        "and cognitive load that affect how you respond. "
        "You should make decisions consistent with your cognitive profile."
    )

    def __init__(
        self,
        actor_id: str = "user_twin",
        cognitive_profile: Any = None,
    ):
        self.state = UserTwinState(actor_id=actor_id)
        self.last_decision_source = "not_run"
        if cognitive_profile is not None:
            self._init_from_profile(cognitive_profile)

    def _init_from_profile(self, profile: Any) -> None:
        """Map CognitiveProfile fields to UserTwinState (0.0–1.0).

        Uses getattr for resilience — missing attributes default to 0.5.
        """
        self.state.trust = round(getattr(profile, "trust_threshold", 5.0) / 10.0, 3)
        self.state.verification_tendency = round(
            getattr(profile, "verification_habit", 5.0) / 10.0, 3
        )
        self.state.urgency_sensitivity = round(
            getattr(profile, "time_pressure", 5.0) / 10.0, 3
        )
        self.state.compliance_tendency = round(
            getattr(profile, "authority_compliance", 5.0) / 10.0, 3
        )
        self.state.risk_awareness = round(
            getattr(profile, "risk_recovery_awareness", 5.0) / 10.0, 3
        )
        self.state.cognitive_load = round(
            getattr(profile, "cognitive_load", 5.0) / 10.0, 3
        )

    def observe(
        self,
        threat_action: str,
        verifier_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Build observation from what the user perceives."""
        obs = {
            "threat_action": threat_action,
            "verifier_info_available": verifier_info is not None,
        }
        if verifier_info:
            obs["verifier_risk_signals"] = verifier_info.get("risk_signals", [])
            obs["verifier_safe_action"] = verifier_info.get("safe_action", "")
        return obs

    def decide(
        self,
        observation: Dict[str, Any],
        llm_client=None,
    ) -> str:
        """Choose next action — via LLM or deterministic heuristic."""
        if llm_client is not None:
            return self._llm_decide(observation, llm_client)
        self.last_decision_source = "deterministic_no_client"
        return self._deterministic_decide(observation)

    def _deterministic_decide(self, observation: Dict[str, Any]) -> str:
        """Deterministic decision based on cognitive profile thresholds."""
        threat = observation.get("threat_action", "")
        has_verifier = observation.get("verifier_info_available", False)
        risk_signals = observation.get("verifier_risk_signals", [])

        # If verifier provides risk signals and user has decent risk awareness
        if has_verifier and risk_signals and self.state.risk_awareness > 0.4:
            if self.state.verification_tendency > 0.3:
                return "refuse"
            return "verify"

        # If user has high verification tendency and threat is asking for something specific
        specific_asks = {
            "request_transfer",
            "request_verification_code",
            "request_screen_share",
            "request_download",
        }
        if threat in specific_asks and self.state.verification_tendency > 0.5:
            return "delay"

        # High compliance + high urgency sensitivity → comply
        if (
            self.state.compliance_tendency > 0.6
            and self.state.urgency_sensitivity > 0.5
        ):
            return "comply"

        # High cognitive load → comply (reduced decision capacity)
        if self.state.cognitive_load > 0.7:
            return "comply"

        # High trust → comply
        if self.state.trust > 0.7 and threat not in specific_asks:
            return "comply"

        # High risk awareness with isolation/pressure tactics
        if self.state.risk_awareness > 0.5 and threat in (
            "apply_isolation",
            "apply_urgency",
            "apply_authority",
        ):
            return "ask_question"

        # Default: delay / ask
        if self.state.verification_tendency > self.state.compliance_tendency:
            return "ask_question"
        return "comply"

    def _llm_decide(
        self,
        observation: Dict[str, Any],
        llm_client,
    ) -> str:
        """Use shared LLM with a user-twin system prompt."""
        import json

        profile_desc = (
            f"trust={self.state.trust:.2f}, "
            f"verification={self.state.verification_tendency:.2f}, "
            f"urgency_sensitivity={self.state.urgency_sensitivity:.2f}, "
            f"compliance={self.state.compliance_tendency:.2f}, "
            f"risk_awareness={self.state.risk_awareness:.2f}, "
            f"cognitive_load={self.state.cognitive_load:.2f}"
        )
        messages = [
            {"role": "system", "content": self.SYSTEM_ROLE},
            {"role": "system", "content": (
                f"Your cognitive profile: {profile_desc}. "
                f"Previous actions: {', '.join(self.state.previous_actions[-5:] or ['none'])}. "
                f"Memory: {'; '.join(self.state.memory[-5:] or ['none'])}."
            )},
            {"role": "system", "content": (
                "Choose exactly one next action from this list and return only the action token: "
                + ", ".join(USER_TWIN_ACTIONS)
                + ". Do not explain or add punctuation."
            )},
            {"role": "user", "content": json.dumps(observation, ensure_ascii=False)},
        ]
        try:
            response = llm_client.chat(
                messages,
                temperature=0.7,
                max_tokens=128,
            )
            for action in USER_TWIN_ACTIONS:
                if action in (response or ""):
                    self.last_decision_source = "llm"
                    return action
            self.last_decision_source = "deterministic_unparsed_llm"
            return self._deterministic_decide(observation)
        except Exception:
            self.last_decision_source = "deterministic_llm_error"
            return self._deterministic_decide(observation)

    def update_state(self, action: str, threat_action: str) -> Dict[str, Any]:
        """Update private state after taking an action."""
        self.state.previous_actions.append(action)
        self.state.memory.append(
            f"threat={threat_action[:80]} my_action={action}"
        )

        # State drifts based on experience
        if action in ("refuse", "seek_help"):
            self.state.trust = max(0.0, self.state.trust - 0.15)
            self.state.verification_tendency = min(1.0, self.state.verification_tendency + 0.05)
            self.state.risk_awareness = min(1.0, self.state.risk_awareness + 0.08)
        elif action == "verify":
            self.state.trust = max(0.0, self.state.trust - 0.08)
            # Verification is an active protective behaviour.  Keeping risk
            # awareness unchanged made a repeatedly verifying branch look
            # identical to a repeatedly complying branch downstream.
            self.state.risk_awareness = min(1.0, self.state.risk_awareness + 0.05)
        elif action == "comply":
            self.state.trust = min(1.0, self.state.trust + 0.05)
            self.state.compliance_tendency = min(1.0, self.state.compliance_tendency + 0.03)
        elif action == "delay":
            self.state.cognitive_load = max(0.0, self.state.cognitive_load - 0.05)

        return {
            "actor_id": self.state.actor_id,
            "action": action,
            "trust_delta": round(self.state.trust - 0.5, 3),
            "risk_awareness_delta": round(self.state.risk_awareness - 0.5, 3),
        }


# ── Verifier ──────────────────────────────────────────────────────────


class Verifier:
    """Independent verifier with access to RiskGraph evidence and RAG data.

    Has a DIFFERENT information set than ThreatActor and UserTwin.
    Can provide risk signals and safe-action guidance, but does NOT
    directly control UserTwin's decisions.
    """

    SYSTEM_ROLE = (
        "You are an independent fraud verifier. You have access to "
        "evidence from a risk knowledge graph, known scam patterns, "
        "and claims made in the current interaction. "
        "Your job is to cross-check claims against evidence, "
        "identify risk signals, and provide safe-action guidance. "
        "You do NOT control the user — you only provide information."
    )

    def __init__(
        self,
        actor_id: str = "verifier",
        evidence_refs: Optional[List[str]] = None,
        known_patterns: Optional[List[str]] = None,
    ):
        self.state = VerifierState(
            actor_id=actor_id,
            evidence_refs=evidence_refs or [],
            known_scam_patterns=known_patterns or [],
        )
        self.last_decision_source = "not_run"

    def observe(self, interaction_context: Dict[str, Any]) -> Dict[str, Any]:
        """Build observation from the current interaction state."""
        return {
            "threat_action": interaction_context.get("threat_action", ""),
            "user_action": interaction_context.get("user_action", ""),
            "threat_claimed_identity": interaction_context.get(
                "threat_claimed_identity", ""
            ),
            "round": interaction_context.get("round", 0),
        }

    def decide(
        self,
        observation: Dict[str, Any],
        llm_client=None,
    ) -> Dict[str, Any]:
        """Decide whether to intervene and with what information.

        Returns a dict with 'action' and 'info' keys.
        'info' is shared with UserTwin as observation.
        """
        if llm_client is not None:
            return self._llm_decide(observation, llm_client)
        self.last_decision_source = "deterministic_no_client"
        return self._deterministic_decide(observation)

    def _deterministic_decide(self, observation: Dict[str, Any]) -> Dict[str, Any]:
        """Deterministic verification — pattern matching against evidence."""
        threat_action = observation.get("threat_action", "")
        threat_identity = observation.get("threat_claimed_identity", "")

        risky_actions = {
            "request_transfer",
            "request_verification_code",
            "request_screen_share",
            "request_download",
            "apply_isolation",
        }

        risk_signals = []
        if threat_action in risky_actions:
            risk_signals.append(f"high_risk_action:{threat_action}")
        if threat_identity and any(
            kw in threat_identity
            for kw in ["客服", "公安", "银行", "官方", "征信", "监管"]
        ):
            risk_signals.append("claimed_official_identity")

        # Cross-check against known patterns
        for pattern in self.state.known_scam_patterns[:5]:
            if pattern.lower() in threat_action.lower():
                risk_signals.append(f"matches_known_pattern:{pattern}")

        if risk_signals:
            return {
                "action": "identify_risk_signal",
                "info": {
                    "risk_signals": risk_signals,
                    "safe_action": "通过官方渠道独立核验对方身份与请求",
                    "evidence_refs": self.state.evidence_refs[:3],
                },
            }

        # No clear risk — wait and observe
        if observation.get("round", 0) <= 1:
            return {
                "action": "wait",
                "info": {},
            }

        # Later rounds: suggest verification
        return {
            "action": "provide_safe_action",
            "info": {
                "risk_signals": ["unverified_interaction"],
                "safe_action": "暂停当前操作，通过独立渠道核实信息",
                "evidence_refs": self.state.evidence_refs[:3],
            },
        }

    def _llm_decide(
        self,
        observation: Dict[str, Any],
        llm_client,
    ) -> Dict[str, Any]:
        """Use shared LLM with a verifier system prompt."""
        import json

        messages = [
            {"role": "system", "content": self.SYSTEM_ROLE},
            {"role": "system", "content": (
                f"Evidence refs: {self.state.evidence_refs[:10]}. "
                f"Known patterns: {', '.join(self.state.known_scam_patterns[:10] or ['none'])}. "
                f"Previous verification results: {json.dumps(self.state.verification_results[-3:] or [], ensure_ascii=False)}."
            )},
            {"role": "system", "content": (
                "Choose exactly one next action from this list and return only the action token: "
                + ", ".join(VERIFIER_ACTIONS)
                + ". Do not explain or add punctuation."
            )},
            {"role": "user", "content": json.dumps(observation, ensure_ascii=False)},
        ]
        try:
            response = llm_client.chat(
                messages,
                temperature=0.3,
                max_tokens=256,
            )
            # Try to parse action
            for action in VERIFIER_ACTIONS:
                if action in (response or ""):
                    self.last_decision_source = "llm"
                    return {
                        "action": action,
                        "info": {
                            "risk_signals": ["llm_flag"],
                            "safe_action": response or "通过官方渠道核实",
                            "evidence_refs": self.state.evidence_refs[:3],
                        },
                    }
            self.last_decision_source = "deterministic_unparsed_llm"
            return self._deterministic_decide(observation)
        except Exception:
            self.last_decision_source = "deterministic_llm_error"
            return self._deterministic_decide(observation)

    def update_state(
        self, action: str, info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Record verification action and its outcome."""
        entry = {"action": action, "risk_signals": info.get("risk_signals", [])}
        self.state.verification_results.append(entry)
        self.state.memory.append(
            f"action={action} signals={info.get('risk_signals', [])}"
        )
        return {
            "actor_id": self.state.actor_id,
            "action": action,
            "risk_signals_found": len(info.get("risk_signals", [])),
        }
