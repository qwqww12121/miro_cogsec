"""CogSec 场景分析编排服务。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import time
from typing import Any, Dict, List, Optional

from ..config import Config
from ..modules import (
    CognitiveProfile,
    CognitiveProfileExtractor,
    InputPackage,
    CounterfactualReporter,
    FraudCase,
    MiroFishRuntime,
    PrivacySanitizer,
    RiskScorer,
    T0FastResponder,
    ThreatKnowledgeRAG,
    build_canonical_case,
    build_scenario_context,
    get_spec,
    resolve_canonical,
    scenario_metadata,
)
from ..modules.benchmark_adapter import build_benchmark_payload
from ..modules.conversational_response import build_conversational_response
from ..modules.report_state import build_report_state
from ..modules.propagation import run_proxy_intervention_search
from ..modules.propagation.intervention_search import resolve_effective_intervention
from ..modules.propagation.oasis_verification import run_topk_oasis_verification
from ..modules.propagation.result_adapter import adapt_propagation_result
from ..modules.scenario_detector import ScenarioDetector
from ..modules.social_state.schema import attach_graph_behaviors, propagation_trace_actions
from ..utils.logger import get_logger

logger = get_logger("mirofish.cogsec")


@dataclass
class CogSecAnalysisResult:
    """CogSec 全量分析结果。"""

    profile: Dict[str, Any]
    persona_state_vector: Dict[str, Any]
    strategies: List[Dict[str, Any]]
    graph: Dict[str, Any]
    risk_graph_bundle: Dict[str, Any]
    world_state_snapshot: Dict[str, Any]
    branch_a_log: List[Dict[str, Any]]
    branch_b_log: List[Dict[str, Any]]
    fork_comparison: Dict[str, Any]
    counterfactual_report: Dict[str, Any]
    intervention_prescriptions: List[Dict[str, Any]]
    t0_fast_response: Dict[str, Any]
    sanitization: Dict[str, Any]
    metrics: Dict[str, Any]
    anomalies: List[str]
    implementation_status: Dict[str, Any]
    scenario_metadata: Dict[str, Any] = field(default_factory=dict)
    scenario_extension: Dict[str, Any] | None = None
    benchmark_prediction: Dict[str, Any] | None = None
    cogsec_analysis: Dict[str, Any] | None = None
    report_state: Dict[str, Any] | None = None
    benchmark_field_provenance: Dict[str, Any] | None = None
    adapter_diagnostics: Dict[str, Any] | None = None
    role_report: Dict[str, Any] | None = None
    assistant_message: str | None = None
    # Dual-view output: LLM-translated plain-language view of
    # assistant_message (same coverage, non-expert wording) and the single
    # key action extracted by the reporter.  None -> frontend local fallback.
    plain_view: str | None = None
    most_important_action: str | None = None
    response_plan: Dict[str, Any] | None = None
    graph_payload: Dict[str, Any] | None = None
    suggested_followups: List[str] | None = None
    latency_profile: Dict[str, Any] | None = None
    conversation_state: Dict[str, Any] | None = None
    reporter_provenance: Dict[str, Any] | None = None
    fraud_interaction: Dict[str, Any] | None = None
    tone: str = "friendly"

    # -- new unified status fields (Round 1 upgrade) --
    status: str = "complete"               # complete | degraded | partial | failed
    degraded_reasons: List[str] = field(default_factory=list)
    runtime_components: Dict[str, str] = field(default_factory=dict)

    # -- RC fix: core_analysis and ablation_variant must be persisted (P0-2) --
    core_analysis: Dict[str, Any] | None = None
    ablation_variant: Dict[str, Any] | None = None

    # -- new timing fields (Round 1 upgrade) --
    request_total_ms: float = 0.0
    timing_breakdown: Dict[str, Optional[float]] = field(default_factory=dict)

    # -- new payload stats (Round 1 upgrade) --
    response_payload_bytes: int = 0
    payload_duplicate_fields: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典。"""
        return asdict(self)


class CogSecService:
    """认知安全分析服务。

    Can be created standalone (backward-compatible) or via a shared
    ``CogSecRuntime`` to reuse expensive resources.
    """

    def __init__(self, runtime=None, llm_client=None):
        """Build the service.

        Parameters
        ----------
        runtime:
            Optional shared ``CogSecRuntime``.  When provided, all heavy
            resources (LLM, RAG, case library) are borrowed from the runtime
            instead of being created per-request.
        llm_client:
            Direct LLM client override (backward-compatible path).
        """
        self._runtime = runtime

        if runtime is not None:
            self.llm_client = runtime.get_llm_client()
            self.reporter_client = runtime.get_reporter_client()
            # Lazily acquire RAG so direct_llm can execute without Chroma or
            # embedding initialization.
            self.threat_rag = None
        else:
            self.llm_client = llm_client or self._safe_build_llm_client()
            self.reporter_client = self._safe_build_reporter_client(self.llm_client)
            self.threat_rag = None

        self.profile_extractor = CognitiveProfileExtractor(self.llm_client)
        self.runtime_engine = MiroFishRuntime()
        self.reporter = CounterfactualReporter()
        self.t0_responder = T0FastResponder(getattr(Config, "T0_PATTERNS_PATH", None))
        self.privacy_sanitizer = PrivacySanitizer(
            enabled=Config.PRESIDIO_ENABLED and Config.LOCAL_SANITIZE_ENABLED
        )
        self._case_library_loaded = False
        self._case_library_source = "not_loaded"
        self._case_library_count = 0
        self._case_library_fallback_used = False
        self._case_library_fallback_reason = None

    def analyze_text(
        self,
        scenario_text: str,
        questionnaire: Optional[Dict[str, Any]] = None,
        scenario_type: Optional[str] = None,
        user_role: str = "individual",
        tone: str = "friendly",
        conversation_id: Optional[str] = None,
        turn_id: Optional[str] = None,
        include_benchmark: bool = False,
        variant_id: Optional[str] = None,
        input_fragments: Optional[List[Dict[str, Any]]] = None,
    ) -> CogSecAnalysisResult:
        """从场景文本生成完整的 CogSec 分析结果。"""
        request_started = time.perf_counter()
        timing: Dict[str, Optional[float]] = {}

        canonical = resolve_canonical(scenario_type)

        # Resolve ablation variant (controls which modules run)
        variant_flags: Dict[str, bool] = {}
        variant_label: str = "full"
        executed_components: List[str] = []
        skipped_components: List[str] = []
        if variant_id:
            from ..modules.ablation_config import get_variant, PRESET_VARIANTS
            try:
                variant = get_variant(variant_id)
                variant_flags = variant.feature_flags
                variant_label = variant.variant_id
            except KeyError:
                raise ValueError(
                    f"Unknown ablation variant '{variant_id}'. "
                    f"Allowed variants: {list(PRESET_VARIANTS.keys())}"
                ) from None

        def _should_run(flag: str) -> bool:
            """Check if a module should run under the current variant."""
            if not variant_id:
                return True  # no variant → run everything
            return variant_flags.get(flag, True)

        def _track(component: str, ran: bool) -> None:
            if ran:
                executed_components.append(component)
            else:
                skipped_components.append(component)

        runtime_components: Dict[str, str] = {
            "profile": "skipped",
            "rag": "skipped",
            "risk_graph": "skipped",
            "fork": "skipped",
            "social": "skipped",
            "intervention_search": "skipped",
            "oasis": "skipped",
            "oasis_verification": "skipped",
            "fraud_interaction": "skipped",
        }
        degraded_reasons: List[str] = []

        # === Phase 0 — sanitize FIRST (Round 1 upgrade) ===
        # Previously: ScenarioContext built with raw text, then sanitized,
        # then propagation/OASIS still used the raw context.  Now we sanitize
        # before anything else so every downstream module only sees sanitized text.
        t0_sanitize = time.perf_counter()
        sanitization_result = self.privacy_sanitizer.sanitize_with_retry(
            scenario_text,
            storage_policy="session_only",
            max_retries=1,
        )
        if sanitization_result.pii_leak_detected:
            raise RuntimeError("PII leak detected after sanitization retry")
        analysis_text = sanitization_result.sanitized_text or scenario_text
        timing["privacy_ms"] = round((time.perf_counter() - t0_sanitize) * 1000, 2)

        if variant_label == "direct_llm":
            return self._analyze_direct_llm(
                analysis_text=analysis_text,
                scenario_type=scenario_type,
                user_role=user_role,
                tone=tone,
                conversation_id=conversation_id,
                turn_id=turn_id,
                include_benchmark=include_benchmark,
                sanitization=sanitization_result.to_dict(),
                timing=timing,
                request_started=request_started,
                executed_components=executed_components,
                skipped_components=skipped_components,
                runtime_components=runtime_components,
            )

        # === Phase 1 — normalize sanitized input into identity-preserving evidence ===
        # Round 1 upgrade: raw_inputs now carries sanitized content so
        # propagation / OASIS cannot leak raw PII to external LLMs.
        safe_input_fragments = self._sanitize_input_fragments(
            input_fragments=input_fragments,
            fallback_text=analysis_text,
        )
        scenario_ctx = build_scenario_context(
            scenario_type=scenario_type,
            user_role=user_role,
            raw_inputs=safe_input_fragments,
        )

        # T0 fast scan (regex, ms-level)
        t0_t0 = time.perf_counter()
        t0_result = self.t0_responder.scan(analysis_text)
        timing["t0_ms"] = round((time.perf_counter() - t0_t0) * 1000, 2)

        # Scenario detection
        t0_detect = time.perf_counter()
        detection = ScenarioDetector().detect(
            text=analysis_text,
            t0_result=t0_result,
            user_declared=scenario_type,
        )
        canonical = detection.canonical
        timing["scenario_detection_ms"] = round((time.perf_counter() - t0_detect) * 1000, 2)

        if canonical == "unknown":
            return self._build_unknown_result(
                analysis_text=analysis_text,
                user_role=user_role,
                tone=tone,
                conversation_id=conversation_id,
                turn_id=turn_id,
                sanitization=sanitization_result.to_dict(),
                t0_result=t0_result,
                detection=detection,
                timing=timing,
                request_started=request_started,
                executed_components=executed_components,
                skipped_components=skipped_components,
                runtime_components=runtime_components,
                variant_id=variant_id,
                variant_label=variant_label,
            )

        self._ensure_case_library()

        # === Phase 2 — cognitive profile ===
        t0_profile = time.perf_counter()
        if _should_run("use_structured_frame"):
            profile_mode = str(
                getattr(Config, "MIRO_COGSEC_PROFILE_MODE", "auto") or "auto"
            ).lower()
            use_llm_profile = profile_mode == "llm" or (
                profile_mode == "auto" and canonical == "fraud_im"
            )
            if use_llm_profile:
                profile_extractor = self.profile_extractor
                runtime_components["profile"] = "complete" if self.llm_client is not None else "heuristic"
            else:
                from ..modules.cognitive_profiler import CognitiveProfileExtractor
                profile_extractor = CognitiveProfileExtractor(llm_client=None)
                runtime_components["profile"] = "heuristic"
            profile = profile_extractor.extract(
                scenario=analysis_text,
                questionnaire=questionnaire,
                scenario_type=scenario_type or canonical,
                canonical_scenario=canonical,
            )
            _track("structured_frame", True)
        else:
            # Minimal profile without structured LLM extraction
            from ..modules.cognitive_profiler import CognitiveProfile
            profile = CognitiveProfile(scenario_type=canonical)
            _track("structured_frame", False)
            runtime_components["profile"] = "skipped"
        persona_state_vector = profile.to_persona_state_vector()
        timing["profile_ms"] = round((time.perf_counter() - t0_profile) * 1000, 2)

        # CanonicalCase is internal only: it preserves evidence identity and
        # stable observed actor IDs without changing the public request shape.
        input_package = InputPackage.from_fragments(
            primary_text=analysis_text,
            fragments=safe_input_fragments,
            explicit_scenario=scenario_type,
            metadata={"sanitized": True},
        )
        canonical_case = build_canonical_case(
            input_package,
            scenario_type=canonical,
            scenario_confidence=detection.confidence,
            cognitive_profile=profile,
        )
        scenario_ctx.scenario_type = canonical
        scenario_ctx.canonical_case = canonical_case
        scenario_ctx.cognitive_profile = profile

        # Prefer the concrete fraud subtype for RAG so 虚假贷款代办信用卡类
        # retrieves matching cases instead of a generic fraud_im bag.
        rag_scenario_type = canonical
        profile_subtype = getattr(profile, "scenario_type", "") or ""
        declared_subtype = str((questionnaire or {}).get("scenario_category") or scenario_type or "")
        if profile_subtype and profile_subtype not in ("fraud_im", "unknown", canonical):
            rag_scenario_type = profile_subtype
        elif declared_subtype and declared_subtype not in ("fraud_im", "unknown", canonical):
            rag_scenario_type = declared_subtype

        # === Phase 3 — RAG / risk graph ===
        t0_rag = time.perf_counter()
        if _should_run("use_rag"):
            risk_graph_bundle = self.threat_rag.build_risk_graph_bundle(
                scenario_text=analysis_text,
                scenario_type=rag_scenario_type,
                cognitive_profile=profile,
                persona_state_vector=persona_state_vector,
                n_results=3,
                build_graph=_should_run("use_risk_graph"),
            )
            _track("rag", True)
            runtime_components["rag"] = "complete"
            # _track reflects ACTUAL execution, not config intention
            _track("risk_graph", _should_run("use_risk_graph"))
            runtime_components["risk_graph"] = "complete" if _should_run("use_risk_graph") else "skipped"
        else:
            # Minimal placeholder when RAG is skipped
            from ..modules.runtime_schema import RiskGraphBundle
            risk_graph_bundle = RiskGraphBundle(
                schema_version="cogsec.mainline.v1",
                threat_template_nodes=[],
                evidence_items=[],
                persuasion_principles=[],
                persona_weakness_hits=[],
                asset_targets=[],
                environment_context={"scenario_type": canonical},
                fork_points=[],
                nodes=[],
                edges=[],
            )
            _track("rag", False)
            _track("risk_graph", False)
            runtime_components["rag"] = "skipped"
            runtime_components["risk_graph"] = "skipped"
        timing["rag_ms"] = round((time.perf_counter() - t0_rag) * 1000, 2)

        # Build one canonical initial social world (S0) after risk/evidence
        # extraction and before any propagation or counterfactual branch.
        simulation_state = None
        if canonical in {"public_opinion", "event_propagation"} and _should_run("use_social_state"):
            from ..modules.social_state import build_social_state
            from ..modules.social_state.builder import demo_agent_count

            simulation_state = build_social_state(
                scenario_text=canonical_case.summary,
                scenario_type=canonical_case.scenario_type,
                cognitive_profile=canonical_case.cognitive_profile,
                risk_graph=risk_graph_bundle,
                n_agents=demo_agent_count(canonical),
                seed=42,
                canonical_case=canonical_case,
            )
            from ..modules.social_state import create_snapshot
            simulation_snapshot = create_snapshot(simulation_state, seed=42)
            scenario_ctx.simulation_state = simulation_state
            scenario_ctx.simulation_snapshot = simulation_snapshot

        # === Phase 4 — FORK runtime ===
        t0_fork = time.perf_counter()
        if _should_run("use_fork"):
            runtime_result = self.runtime_engine.run(
                persona_state_vector=persona_state_vector,
                risk_graph_bundle=risk_graph_bundle,
                current_input=analysis_text,
                deadline_sec=getattr(Config, "COGSEC_RUNTIME_TIMEOUT_SEC", 15.0),
                scenario_type=canonical,
            )
            _track("fork", True)
            runtime_components["fork"] = "complete"
        else:
            # Empty fork result when FORK is skipped
            from ..modules.mainline_runtime import RuntimeResult
            from ..modules.runtime_schema import (
                ForkComparisonResult, WorldStateSnapshot, BranchTraceStep,
            )
            empty_state = WorldStateSnapshot(
                step=0, stage="skipped", action="variant_skipped_fork",
                trust_score=50.0, cognitive_mode="SYSTEM_2",
                asset_exposure=0.0, intervention_window=0.5,
                posterior_risk=0.1, reversibility=0.9,
            )
            empty_step = BranchTraceStep(
                branch="A", step=1, action="variant_skipped",
                action_type="skipped", fork_point_type="no_valid_fork",
                world_state=empty_state, posterior_updates={},
            )
            empty_comparison = ForkComparisonResult(
                fork_point_type="no_valid_fork", fork_node_id="fork:skipped",
                branch_a_state_trace=[empty_step],
                branch_b_state_trace=[empty_step],
                posterior_updates=[], reversibility_curve=[],
                persona_hit_chain=[], evidence_graph_consistency=0.0,
                trajectory_gap=0.0, irreversibility_loss=0.0,
                anomaly_flags=["fork_skipped_by_variant"],
            )
            runtime_result = RuntimeResult(
                initial_world_state=empty_state,
                fork_comparison=empty_comparison,
                degraded=False, degraded_reason="",
            )
            _track("fork", False)
            runtime_components["fork"] = "skipped"
        timing["fork_ms"] = round((time.perf_counter() - t0_fork) * 1000, 2)

        branch_a_log = [step.to_dict() for step in runtime_result.fork_comparison.branch_a_state_trace]
        branch_b_log = [step.to_dict() for step in runtime_result.fork_comparison.branch_b_state_trace]

        # === Phase 4b — fraud multi-role interaction (fraud_im only) ===
        # There is one fraud runtime call, before RiskScorer/Reporter.
        fraud_interaction_result: Optional[Dict[str, Any]] = None
        fraud_is_primary: bool = False
        effective_fork_comparison = runtime_result.fork_comparison
        effective_branch_a_log = branch_a_log
        effective_branch_b_log = branch_b_log

        grounded_strategies = [
            item for item in (getattr(risk_graph_bundle, "attack_strategy_chain", None) or [])
            if isinstance(item, dict) and item.get("grounding_status", "observed") == "observed"
        ]
        grounded_fraud_evidence = bool(
            grounded_strategies or getattr(risk_graph_bundle, "fork_points", None)
        )
        if canonical == "fraud_im" and _should_run("use_fraud_interaction") and grounded_fraud_evidence:
            try:
                from ..modules.fraud_runtime import FraudMultiRoleRuntime
                from ..modules.fraud_runtime.runtime import adapt_fraud_to_fork_comparison
                fraud_policy_mode = str(
                    getattr(Config, "MIRO_FRAUD_AGENT_POLICY_MODE", "deterministic")
                    or "deterministic"
                ).lower()
                fraud_rt = FraudMultiRoleRuntime(
                    llm_client=self.llm_client if fraud_policy_mode in {"llm", "auto"} else None,
                    policy_mode=fraud_policy_mode,
                )
                fraud_result_obj = fraud_rt.run(
                    scenario_text=analysis_text,
                    cognitive_profile=profile,
                    risk_graph_bundle=risk_graph_bundle,
                    scenario_type=canonical,
                    max_rounds=4,
                )
                fraud_interaction_result = fraud_result_obj.to_dict()
                # A complete deterministic trace is still the fraud mechanism
                # result and should feed the scorer.  Its provenance remains
                # degraded; only the old code discarded it merely because the
                # LLM decision source failed.
                adapted_fork = adapt_fraud_to_fork_comparison(
                    fraud_result_obj,
                    existing_fork=runtime_result.fork_comparison,
                )
                if adapted_fork is not None:
                    # The fraud interaction is the primary counterfactual
                    # source for fraud_im.  Keep the original FORK result in
                    # the supplementary field, but make the adapted trace
                    # feed RiskScorer and the final provenance flag.
                    effective_fork_comparison = adapted_fork
                    effective_branch_a_log = [
                        step.to_dict()
                        for step in adapted_fork.branch_a_state_trace
                    ]
                    effective_branch_b_log = [
                        step.to_dict()
                        for step in adapted_fork.branch_b_state_trace
                    ]
                    runtime_components["fraud_interaction"] = fraud_result_obj.status
                    if fraud_result_obj.status != "complete":
                        degraded_reasons.extend(
                            fraud_result_obj.degraded_reasons
                            or ["fraud_interaction_degraded_fallback"]
                        )
                else:
                    runtime_components["fraud_interaction"] = "failed"
                    degraded_reasons.append("fraud_adapter_failed")
            except Exception as exc:
                logger.warning("fraud multi-role runtime failed: %s", exc)
                fraud_interaction_result = {
                    "runtime_mode": "deterministic_fallback",
                    "status": "degraded",
                    "error": str(exc),
                }
                runtime_components["fraud_interaction"] = "failed"
                degraded_reasons.append("fraud_interaction_failed")
        elif canonical == "fraud_im":
            runtime_components["fraud_interaction"] = "skipped_no_grounded_evidence"
            degraded_reasons.append("fraud_interaction_skipped_no_grounded_evidence")

        triggered_fork_count = self._count_triggered_forks(analysis_text)
        scorer_a = RiskScorer(profile)
        scorer_b = RiskScorer(profile)
        self._score_branch(effective_branch_a_log, scorer_a)
        self._score_branch(effective_branch_b_log, scorer_b)
        risk_breakdown = RiskScorer(profile).evaluate_counterfactual(
            branch_a_state_trace=effective_fork_comparison.branch_a_state_trace,
            branch_b_state_trace=effective_fork_comparison.branch_b_state_trace,
            fork_point_type=effective_fork_comparison.fork_point_type,
            posterior_updates=effective_fork_comparison.posterior_updates,
            reversibility_curve=effective_fork_comparison.reversibility_curve,
            persona_hit_chain=effective_fork_comparison.persona_hit_chain,
            evidence_graph_consistency=effective_fork_comparison.evidence_graph_consistency,
            anomaly_flags=effective_fork_comparison.anomaly_flags,
            irreversibility_loss=effective_fork_comparison.irreversibility_loss,
            fork_count=triggered_fork_count,
        )
        fraud_is_primary = bool(
            runtime_components.get("fraud_interaction") in {"complete", "degraded"}
            and getattr(effective_fork_comparison, "runtime_source", None) == "fraud_multi_role"
        )

        case_evidence = self._build_case_evidence(profile.scenario_type, risk_graph_bundle.attack_strategy_chain)
        report = self.reporter.generate_report(
            branch_a_log=effective_branch_a_log,
            branch_b_log=effective_branch_b_log,
            scorer_a=scorer_a,
            scorer_b=scorer_b,
            cognitive_profile=profile,
            case_evidence=case_evidence,
            persona_state_vector=persona_state_vector,
            risk_graph_bundle=risk_graph_bundle,
            fork_comparison=effective_fork_comparison,
            risk_breakdown=risk_breakdown,
        )

        anomalies = self._collect_anomalies(
            sanitization_result=sanitization_result.to_dict(),
            risk_graph_bundle=risk_graph_bundle.to_dict(),
            fork_comparison=effective_fork_comparison.to_dict(),
            runtime_result=runtime_result.to_dict(),
            risk_breakdown=risk_breakdown.to_dict(),
        )
        implementation_status = report.implementation_status or {
            "stable_base": [],
            "new_mainline": [],
            "phase_ii": [],
        }

        sc_meta = scenario_metadata(canonical)
        sc_meta["resolved_from"] = scenario_type
        sc_meta["user_role"] = user_role

        # Initialize scenario_extension BEFORE any propagation phase uses it
        canonical_case_payload = canonical_case.to_dict()
        canonical_case_payload["grounding"] = dict(canonical_case.provenance)
        scenario_extension: Dict[str, Any] = {
            "detection": detection.to_dict(),
            "canonical_case": canonical_case_payload,
        }
        if simulation_state is not None:
            scenario_extension["canonical_case"].update({
                "simulation_state_id": simulation_state.simulation_state_id,
                "grounding": dict(canonical_case.provenance),
            })
            scenario_extension["social_state_summary"] = simulation_state.summary()
            scenario_extension["propagation_graph"] = simulation_state.to_display_graph(max_nodes=24)

        # Carry over runtime-level degraded state
        if runtime_result.degraded:
            degraded_reasons.append(runtime_result.degraded_reason or "fork_runtime_degraded")
            runtime_components["fork"] = "degraded"

        # === Phase 5 — propagation extension ===

        try:
            spec = get_spec(canonical)
        except KeyError:
            spec = None

        # Unknown routing is a clarification state, not a runtime failure.
        if canonical == "unknown":
            scenario_extension["requires_clarification"] = True

        if spec is not None and hasattr(spec, "supports_propagation") and spec.supports_propagation() and _should_run("use_social_state"):
            _track("social_state", True)

            t0_oasis = time.perf_counter()
            propagation_result: Optional[Dict[str, Any]] = None
            try:
                propagation_result = spec.run_propagation(
                    scenario_ctx,
                    quick_mode=True,
                    allow_oasis=_should_run("use_oasis"),
                )
                scenario_extension["propagation"] = propagation_result
                scenario_extension["propagation_normalized"] = adapt_propagation_result(
                    propagation_result
                ).to_dict()
                runtime_components["social"] = "complete"
                propagation_provenance = propagation_result.get("provenance", {})
                if propagation_provenance.get("runtime_engine") == "oasis":
                    runtime_components["oasis"] = "complete"
                elif _should_run("use_oasis") and propagation_provenance.get("degraded"):
                    runtime_components["oasis"] = "degraded"
                    degraded_reasons.append(
                        propagation_provenance.get("degraded_reason", "oasis_runtime_degraded")
                    )
                else:
                    runtime_components["oasis"] = "skipped"
                _track("oasis", propagation_provenance.get("runtime_engine") == "oasis")
                graph = scenario_extension.get("propagation_graph")
                if isinstance(graph, dict):
                    oasis_ran = runtime_components.get("oasis") == "complete"
                    graph["source"] = "oasis" if oasis_ran else "lightweight_propagation"
                    graph["engine"] = "oasis" if oasis_ran else "social_state"
                    graph["oasis_status"] = runtime_components.get("oasis", "skipped")
                    attach_graph_behaviors(graph, propagation_trace_actions(propagation_result))
            except Exception as exc:
                logger.warning("scenario propagation failed for %s: %s", canonical, exc)
                scenario_extension["propagation_error"] = str(exc)
                runtime_components["social"] = "failed"
                runtime_components["oasis"] = "failed" if _should_run("use_oasis") else "skipped"
                _track("oasis", False)
                degraded_reasons.append("propagation_runtime_failed")
            timing["oasis_ms"] = round((time.perf_counter() - t0_oasis) * 1000, 2)

            # Step 1: Proxy intervention search — gated by use_intervention_search
            proxy_result: Optional[Dict[str, Any]] = None
            if _should_run("use_intervention_search"):
                t0_intervention = time.perf_counter()
                try:
                    proxy_result = run_proxy_intervention_search(
                        scenario_type=canonical,
                        seed_text=analysis_text,
                        risk_graph_bundle=risk_graph_bundle.to_dict(),
                        propagation_result=propagation_result,
                        quick_mode=True,
                        social_state=simulation_state,
                        canonical_case=canonical_case,
                    )
                    scenario_extension["propagation_intervention_search"] = proxy_result
                    _track("intervention_search", True)
                    runtime_components["intervention_search"] = "complete"
                except Exception as exc:
                    logger.warning("proxy intervention search failed for %s: %s", canonical, exc)
                    scenario_extension["propagation_intervention_search_error"] = str(exc)
                    runtime_components["intervention_search"] = "failed"
                    _track("oasis_verification", False)
                    runtime_components["oasis_verification"] = "skipped"
                    degraded_reasons.append("intervention_search_failed")
                else:
                    # Step 2: OASIS candidate verification is a separate
                    # runtime contract; its failure must not rewrite proxy
                    # search provenance.
                    if _should_run("use_oasis") and proxy_result is not None:
                        try:
                            _oasis_agents = _build_propagation_agents_from_social_state(
                                canonical, analysis_text,
                                social_state=simulation_state,
                            )
                            oasis_verified = run_topk_oasis_verification(
                                scenario_type=canonical,
                                seed_text=analysis_text,
                                agents=_oasis_agents,
                                proxy_result=proxy_result,
                                quick_mode=Config.MIRO_OASIS_VERIFICATION_QUICK_MODE,
                                k=Config.MIRO_OASIS_VERIFICATION_K,
                                seed=Config.MIRO_OASIS_VERIFICATION_SEED,
                                snapshot=scenario_ctx.simulation_snapshot,
                                simulation_state_id=(
                                    simulation_state.simulation_state_id
                                    if simulation_state is not None else None
                                ),
                            )
                        except Exception as exc:
                            logger.warning("OASIS candidate verification failed for %s: %s", canonical, exc)
                            oasis_verified = {
                                "proxy_ranked_candidates": (
                                    proxy_result.get("branch_comparison", {}).get("ranked_branches", [])
                                ),
                                "top_k_selected": [],
                                "oasis_verified_branches": [],
                                "final_ranking": (
                                    proxy_result.get("branch_comparison", {}).get("ranked_branches", [])
                                ),
                                "selected": proxy_result.get("selected_best_branch", {}),
                                "oasis_verification": {
                                    "attempted": True,
                                    "completed": False,
                                    "status": "degraded",
                                    "verification_status": "failed",
                                    "reason": "oasis_verification_failed",
                                },
                                "provenance": "proxy_only",
                                "simulation_state_id": (
                                    simulation_state.simulation_state_id
                                    if simulation_state is not None else None
                                ),
                                "initial_state_source": (
                                    "canonical_social_state"
                                    if simulation_state is not None else "legacy_agent_input"
                                ),
                                "shared_initial_world": simulation_state is not None,
                                "selection_source": "proxy",
                                "metric_source": "proxy",
                                "oasis_verified": False,
                                "oasis_effective": False,
                                "requested_k": Config.MIRO_OASIS_VERIFICATION_K,
                                "effective_k": (
                                    1 if Config.MIRO_OASIS_VERIFICATION_QUICK_MODE
                                    else max(2, Config.MIRO_OASIS_VERIFICATION_K)
                                ),
                                "verifiable_candidate_count": 0,
                                "top_k_oasis_attempted": 0,
                                "top_k_oasis_completed": 0,
                            }
                            scenario_extension["propagation_intervention_search"]["oasis_verification"] = oasis_verified
                            runtime_components["oasis_verification"] = "degraded"
                            _track("oasis_verification", False)
                            degraded_reasons.append("oasis_verification_failed")
                        else:
                            scenario_extension["propagation_intervention_search"]["oasis_verification"] = oasis_verified
                            if oasis_verified.get("top_k_oasis_completed", 0) > 0:
                                runtime_components["oasis_verification"] = "complete"
                            else:
                                oasis_status = oasis_verified.get("oasis_verification", {})
                                if oasis_status.get("status") == "unsupported":
                                    runtime_components["oasis_verification"] = "skipped"
                                elif oasis_status.get("status") == "degraded":
                                    runtime_components["oasis_verification"] = "degraded"
                                    if oasis_status.get("reason"):
                                        degraded_reasons.append(oasis_status["reason"])
                                elif oasis_status.get("attempted"):
                                    runtime_components["oasis_verification"] = "degraded"
                                    if oasis_status.get("reason"):
                                        degraded_reasons.append(oasis_status["reason"])
                                else:
                                    runtime_components["oasis_verification"] = "skipped"
                            _track(
                                "oasis_verification",
                                oasis_verified.get("top_k_oasis_completed", 0) > 0,
                            )
                    else:
                        _track("oasis_verification", False)
                        runtime_components["oasis_verification"] = "skipped"
                if proxy_result is not None:
                    proxy_selected = proxy_result.get("selected_best_branch") or {}
                    effective_selected = resolve_effective_intervention(proxy_result)
                    oasis_state = proxy_result.get("oasis_verification") or {}
                    oasis_selected = oasis_state.get("selected") or {}
                    oasis_effective = (
                        oasis_selected.get("verification_status") == "executed"
                        and oasis_selected.get("effectiveness_status") == "effective"
                        and oasis_selected.get("metric_source") == "oasis"
                    )
                    selection_source = "oasis" if oasis_effective else "proxy"
                    proxy_result.update({
                        "proxy_selected_intervention": dict(proxy_selected),
                        "effective_selected_intervention": dict(effective_selected),
                        "selection_source": selection_source,
                        "oasis_verified": bool(
                            oasis_state.get("oasis_verified")
                            or oasis_selected.get("verification_status") == "executed"
                        ),
                        "oasis_effective": oasis_effective,
                        "selection_provenance": {
                            "selection_source": selection_source,
                            "proxy_candidate_id": proxy_selected.get("candidate_id"),
                            "effective_candidate_id": effective_selected.get("candidate_id"),
                            "oasis_verified": bool(
                                oasis_state.get("oasis_verified")
                                or oasis_selected.get("verification_status") == "executed"
                            ),
                            "oasis_effective": oasis_effective,
                        },
                    })
                timing["intervention_ms"] = round((time.perf_counter() - t0_intervention) * 1000, 2)
            else:
                _track("intervention_search", False)
                _track("oasis_verification", False)
                runtime_components["intervention_search"] = "skipped"
                runtime_components["oasis_verification"] = "skipped"
                timing["intervention_ms"] = None
        else:
            if not _should_run("use_social_state"):
                _track("social_state", False)
            _track("oasis", False)
            _track("oasis_verification", False)
            timing["oasis_ms"] = None
            timing["intervention_ms"] = None

        # Determine unified status
        if degraded_reasons:
            has_failure = any("failed" in v for v in runtime_components.values())
            status = "failed" if has_failure else "degraded"
        else:
            status = "complete"

        # === Build result (pre-report/adapter/conversational) ===
        result_dict = {
            "profile": profile.to_dict(),
            "persona_state_vector": persona_state_vector.to_dict(),
            "strategies": risk_graph_bundle.attack_strategy_chain,
            "graph": risk_graph_bundle.to_dict(),
            "risk_graph_bundle": risk_graph_bundle.to_dict(),
            "world_state_snapshot": runtime_result.initial_world_state.to_dict(),
            "branch_a_log": effective_branch_a_log,
            "branch_b_log": effective_branch_b_log,
            "fork_comparison": effective_fork_comparison.to_dict(),
            "counterfactual_report": report.to_dict(),
            "intervention_prescriptions": report.intervention_prescriptions or [],
            "t0_fast_response": t0_result,
            "sanitization": sanitization_result.to_dict(),
            "scenario_metadata": sc_meta,
            "scenario_extension": scenario_extension,
            "fraud_interaction": fraud_interaction_result,
            "ablation_variant": {
                "variant_id": variant_id or "full",
                "variant_label": variant_label,
                "executed_components": executed_components,
                "skipped_components": skipped_components,
            },
            "core_analysis": self._build_core_analysis(
                canonical=canonical,
                profile=profile,
                risk_graph_bundle=risk_graph_bundle,
                fork_comparison=effective_fork_comparison,
                risk_breakdown=risk_breakdown,
                scenario_extension=scenario_extension,
                detection=detection,
                fraud_is_primary=fraud_is_primary,
                runtime_components=runtime_components,
            ),
            "role_report": None,
            "report_state": None,
            "metrics": {
                "t0_latency_ms": t0_result.get("latency_ms"),
                "t0_target_met": t0_result.get("target_met"),
                "end_to_end_ms": 0.0,  # placeholder — filled below
                "end_to_end_target_met": False,
                "benchmarks": {
                    "T0 latency < 500ms": bool(t0_result.get("target_met")),
                    "End-to-end inference < 30s": False,
                    "FSA > 70%": {
                        "value": None,
                        "available": False,
                        "reason": "offline_benchmark_only",
                    },
                    "CPA > 60%": {
                        "value": None,
                        "available": False,
                        "reason": "offline_benchmark_only",
                    },
                    "EWT > 2 steps": effective_fork_comparison.best_intervention_window.get("open_step", 0) >= 2,
                    "FPR < 15%": {
                        "value": None,
                        "available": False,
                        "reason": "offline_benchmark_only",
                    },
                    "CAL < 0.2": {
                        "value": None,
                        "available": False,
                        "reason": "offline_benchmark_only",
                    },
                    "EAR > 65%": risk_breakdown.evidence_consistency >= 0.65,
                },
                "risk_breakdown": risk_breakdown.to_dict(),
                "case_library": {
                    "case_library_source": self._case_library_source,
                    "case_library_count": self._case_library_count,
                    "fallback_used": self._case_library_fallback_used,
                    "fallback_reason": self._case_library_fallback_reason,
                },
            },
            "anomalies": anomalies,
            "implementation_status": implementation_status,
            "tone": tone,
            "status": status,
            "degraded_reasons": degraded_reasons,
            "runtime_components": runtime_components,
            "timing_breakdown": timing,
        }

        analysis_result = CogSecAnalysisResult(
            **{k: v for k, v in result_dict.items() if k in CogSecAnalysisResult.__dataclass_fields__}
        )
        # Set fields that don't match dataclass init directly
        for k, v in result_dict.items():
            if hasattr(analysis_result, k) and k not in {
                "profile", "persona_state_vector", "strategies", "graph",
                "risk_graph_bundle", "world_state_snapshot", "branch_a_log",
                "branch_b_log", "fork_comparison", "counterfactual_report",
                "intervention_prescriptions", "t0_fast_response", "sanitization",
                "metrics", "anomalies", "implementation_status",
                "scenario_metadata", "scenario_extension", "role_report",
                "tone", "status", "degraded_reasons", "runtime_components",
                "timing_breakdown",
                "core_analysis", "ablation_variant",
                "report_state",
            }:
                setattr(analysis_result, k, v)

        # === Phase 6 — role report ===
        t0_report = time.perf_counter()
        try:
            from ..modules.reporters import render_role_report

            result_dict_full = analysis_result.to_dict()
            role_report = render_role_report(
                result_dict=result_dict_full,
                user_role=user_role,
                scenario_type=canonical,
            )
            analysis_result.role_report = role_report
        except Exception as exc:
            logger.warning("role report rendering failed: %s", exc)
            analysis_result.role_report = {
                "error": str(exc),
                "role": user_role,
            }
        timing["report_ms"] = round((time.perf_counter() - t0_report) * 1000, 2)

        # === Phase 7 — canonical Report State ===
        # Build the user-facing state before any benchmark-only export.  This
        # ordering is a hard data-flow boundary: benchmark adapters may observe
        # runtime state, but can never modify what the Reporter consumes.
        analysis_result.report_state = build_report_state(analysis_result.to_dict())

        # === Phase 8 — benchmark adapter (conditional, export only) ===
        if include_benchmark:
            try:
                benchmark_payload = build_benchmark_payload(
                    result=analysis_result.to_dict(),
                    scenario_text=analysis_text,
                    scenario_type=canonical,
                )
                analysis_result.benchmark_prediction = benchmark_payload["prediction"]
                analysis_result.cogsec_analysis = benchmark_payload["cogsec_analysis"]
                analysis_result.benchmark_field_provenance = benchmark_payload.get("benchmark_field_provenance", {})
                analysis_result.adapter_diagnostics = benchmark_payload["adapter_diagnostics"]
            except Exception as exc:
                logger.warning("benchmark adapter failed: %s", exc)
                analysis_result.benchmark_prediction = {}
                analysis_result.cogsec_analysis = {}
                analysis_result.benchmark_field_provenance = {}
                analysis_result.adapter_diagnostics = {"adapter_warnings": [str(exc)]}
        else:
            analysis_result.benchmark_prediction = {}
            analysis_result.cogsec_analysis = {}
            analysis_result.benchmark_field_provenance = {}
            analysis_result.adapter_diagnostics = {"adapter_warnings": ["benchmark_adapter_not_requested"]}

        # === Phase 9 — conversational response ===
        try:
            conversational = build_conversational_response(
                result=analysis_result.to_dict(),
                user_message=analysis_text,
                tone=tone,
                conversation_id=conversation_id,
                turn_id=turn_id,
                reporter_client=self.reporter_client,
                reporter_mode=Config.MIRO_REPORTER_POLICY_MODE,
                reporter_checkpoint_path=Config.MIRO_REPORTER_ADAPTER_PATH,
                reporter_max_tokens=Config.MIRO_REPORTER_OUTPUT_MAX_TOKENS,
            )
            analysis_result.assistant_message = conversational["assistant_message"]
            analysis_result.plain_view = conversational.get("plain_view")
            analysis_result.most_important_action = conversational.get("most_important_action")
            analysis_result.reporter_provenance = conversational["reporter_provenance"]
            analysis_result.response_plan = conversational["response_plan"]
            analysis_result.graph_payload = conversational["graph_payload"]
            analysis_result.suggested_followups = conversational["suggested_followups"]
            analysis_result.latency_profile = conversational["latency_profile"]
            analysis_result.conversation_state = conversational["conversation_state"]
        except Exception as exc:
            logger.warning("conversational response rendering failed: %s", exc)
            analysis_result.assistant_message = "结论：系统已完成结构化分析，但自然语言回答层生成失败。"
            analysis_result.plain_view = None
            analysis_result.most_important_action = None
            analysis_result.reporter_provenance = {
                "backend": "deterministic",
                "fallback_used": True,
                "fallback_reason": f"reporter_pipeline_failed:{type(exc).__name__}",
            }
            analysis_result.response_plan = {"error": str(exc), "tone": tone}
            analysis_result.graph_payload = {}
            analysis_result.suggested_followups = []
            analysis_result.latency_profile = {"fallback_reason": str(exc)}
            analysis_result.conversation_state = {"tone": tone, "has_cached_analysis": False}

        # === Final timing & payload stats ===
        t0_serialize = time.perf_counter()
        final_dict = analysis_result.to_dict()
        import json
        payload_json = json.dumps(final_dict, ensure_ascii=False, default=str)
        timing["serialization_ms"] = round((time.perf_counter() - t0_serialize) * 1000, 2)

        request_total_ms = round((time.perf_counter() - request_started) * 1000, 2)
        timing["request_total_ms"] = request_total_ms

        # Update metrics (backward-compatible end_to_end_ms now equals request_total_ms)
        analysis_result.metrics["end_to_end_ms"] = request_total_ms
        analysis_result.metrics["end_to_end_target_met"] = request_total_ms < 30000
        analysis_result.metrics["benchmarks"]["End-to-end inference < 30s"] = request_total_ms < 30000
        analysis_result.metrics["latency_profile"] = timing

        analysis_result.request_total_ms = request_total_ms
        analysis_result.timing_breakdown = timing

        # Payload stats
        analysis_result.response_payload_bytes = len(payload_json.encode("utf-8"))
        analysis_result.payload_duplicate_fields = self._find_duplicate_fields(final_dict)

        return analysis_result

    def _build_unknown_result(
        self,
        *,
        analysis_text: str,
        user_role: str,
        tone: str,
        conversation_id: Optional[str],
        turn_id: Optional[str],
        sanitization: Dict[str, Any],
        t0_result: Dict[str, Any],
        detection: Any,
        timing: Dict[str, Optional[float]],
        request_started: float,
        executed_components: List[str],
        skipped_components: List[str],
        runtime_components: Dict[str, str],
        variant_id: Optional[str],
        variant_label: str,
    ) -> CogSecAnalysisResult:
        """Return clarification without initializing architecture runtimes."""
        del user_role
        summary = "当前输入不足以可靠判断属于诈骗即时通讯、舆情分析或事件传播场景。"
        action = "请补充事件背景、传播渠道或对话上下文。"
        core = {
            "scenario": "unknown",
            "scenario_type": "unknown",
            "risk_level": "unknown",
            "requires_clarification": True,
            "summary": summary,
            "recommended_action": action,
            "evidence": list(detection.matched_signals or []),
            "provenance": {
                "metric_source": "none",
                "has_counterfactual_runtime": False,
                "has_rag": False,
                "has_risk_graph": False,
                "has_social_runtime": False,
                "has_oasis": False,
                "runtime_components": dict(runtime_components),
            },
        }
        skipped = list(skipped_components) + [
            "profile", "rag", "risk_graph", "fork", "social",
            "intervention_search", "oasis", "oasis_verification", "fraud_interaction",
        ]
        result = CogSecAnalysisResult(
            profile={}, persona_state_vector={}, strategies=[], graph={},
            risk_graph_bundle={}, world_state_snapshot={}, branch_a_log=[],
            branch_b_log=[], fork_comparison={}, counterfactual_report={},
            intervention_prescriptions=[], t0_fast_response=t0_result,
            sanitization=sanitization,
            metrics={"benchmarks": {}}, anomalies=[],
            implementation_status={"clarification": "complete"},
            scenario_metadata={"canonical": "unknown", "recognised": False},
            scenario_extension={
                "detection": detection.to_dict(),
                "requires_clarification": True,
            },
            benchmark_prediction={}, cogsec_analysis={},
            adapter_diagnostics={"adapter_warnings": ["scenario_requires_clarification"]},
            runtime_components=dict(runtime_components), status="complete",
            core_analysis=core,
            ablation_variant={
                "variant_id": variant_id or "full",
                "variant_label": variant_label,
                "execution_mode": "clarification_only",
                "executed_components": list(executed_components),
                "skipped_components": skipped,
            },
            tone=tone,
        )
        try:
            conversational = build_conversational_response(
                result=result.to_dict(), user_message=analysis_text, tone=tone,
                conversation_id=conversation_id, turn_id=turn_id,
                reporter_client=self.reporter_client,
                reporter_mode=Config.MIRO_REPORTER_POLICY_MODE,
                reporter_checkpoint_path=Config.MIRO_REPORTER_ADAPTER_PATH,
                reporter_max_tokens=Config.MIRO_REPORTER_OUTPUT_MAX_TOKENS,
            )
            result.assistant_message = conversational["assistant_message"]
            result.plain_view = conversational.get("plain_view")
            result.most_important_action = conversational.get("most_important_action")
            result.reporter_provenance = conversational["reporter_provenance"]
            result.response_plan = conversational["response_plan"]
            result.graph_payload = conversational["graph_payload"]
            result.suggested_followups = conversational["suggested_followups"]
            result.latency_profile = conversational["latency_profile"]
            result.conversation_state = conversational["conversation_state"]
        except Exception as exc:
            result.assistant_message = f"{summary}\n建议：{action}"
            result.plain_view = None
            result.most_important_action = None
            result.reporter_provenance = {
                "backend": "deterministic",
                "fallback_used": True,
                "fallback_reason": f"reporter_pipeline_failed:{type(exc).__name__}",
            }
            result.response_plan = {"error": str(exc), "tone": tone}
            result.graph_payload = {}
            result.suggested_followups = []
            result.latency_profile = {"metric_source": "none"}
            result.conversation_state = {"tone": tone, "has_cached_analysis": False}
        timing["request_total_ms"] = round((time.perf_counter() - request_started) * 1000, 2)
        result.request_total_ms = timing["request_total_ms"] or 0.0
        result.timing_breakdown = timing
        result.metrics["end_to_end_ms"] = result.request_total_ms
        result.metrics["end_to_end_target_met"] = result.request_total_ms < 30000
        result.metrics["latency_profile"] = timing
        return result

    def _sanitize_input_fragments(
        self,
        *,
        input_fragments: Optional[List[Dict[str, Any]]],
        fallback_text: str,
    ) -> List[Dict[str, Any]]:
        """Preserve fragment identity while applying the existing sanitizer."""
        if not input_fragments:
            return [{"content": fallback_text, "role": "user", "source": "chat"}]

        safe: List[Dict[str, Any]] = []
        for index, raw_item in enumerate(input_fragments, start=1):
            item = dict(raw_item) if isinstance(raw_item, dict) else {
                "content": str(raw_item),
            }
            content = str(item.get("content", "") or "")
            if not content:
                continue
            result = self.privacy_sanitizer.sanitize_with_retry(
                content,
                storage_policy="session_only",
                max_retries=1,
            )
            if result.pii_leak_detected:
                raise RuntimeError("PII leak detected in input fragment after sanitization retry")
            item["content"] = result.sanitized_text or content
            item.setdefault("fragment_id", f"EVIDENCE_{index:03d}")
            safe.append(item)
        return safe or [{"content": fallback_text, "role": "user", "source": "chat"}]

    def _analyze_direct_llm(
        self,
        *,
        analysis_text: str,
        scenario_type: Optional[str],
        user_role: str,
        tone: str,
        conversation_id: Optional[str],
        turn_id: Optional[str],
        include_benchmark: bool,
        sanitization: Dict[str, Any],
        timing: Dict[str, Optional[float]],
        request_started: float,
        executed_components: List[str],
        skipped_components: List[str],
        runtime_components: Dict[str, str],
    ) -> CogSecAnalysisResult:
        """Run the same-model direct baseline without architecture modules."""
        del user_role
        if self.llm_client is None:
            raise RuntimeError("Direct LLM baseline requires the project main LLM client")

        import json

        messages = [
            {
                "role": "system",
                "content": (
                    "你是 Miro-CogSec 的 direct LLM baseline。仅根据输入输出一个 JSON 对象，"
                    "字段必须包含 scenario_type、risk_level、summary、evidence、recommended_action、assistant_message。"
                    "evidence 必须是字符串数组；不要调用或假设任何画像、RAG、图谱、传播或反事实运行时。"
                    "assistant_message 是直接给用户看的完整自然中文回答，应具体、简洁、可执行，"
                    "不得暴露 JSON 字段名，也不要使用固定评测模板。"
                ),
            },
            {"role": "user", "content": analysis_text},
        ]
        t0_llm = time.perf_counter()
        if hasattr(self.llm_client, "chat_json"):
            raw = self.llm_client.chat_json(messages, temperature=0.0, max_tokens=1024)
        else:
            response = self.llm_client.chat(
                messages, temperature=0.0, max_tokens=1024,
                response_format={"type": "json_object"},
            )
            raw = json.loads(response)
        timing["direct_llm_ms"] = round((time.perf_counter() - t0_llm) * 1000, 2)
        raw = raw if isinstance(raw, dict) else {}

        requested_canonical = resolve_canonical(scenario_type)
        output_canonical = resolve_canonical(raw.get("scenario_type"))
        canonical = output_canonical if output_canonical != "unknown" else requested_canonical
        evidence = raw.get("evidence", [])
        if isinstance(evidence, str):
            evidence = [evidence]
        if not isinstance(evidence, list):
            evidence = []
        risk_level = raw.get("risk_level") or "unknown"
        assessment = raw.get("summary") or raw.get("assessment") or "模型未提供摘要。"
        recommended_action = raw.get("recommended_action") or "请通过独立渠道核验关键信息。"
        direct_assistant_message = raw.get("assistant_message") or f"{assessment}\n\n建议：{recommended_action}"
        runtime_components = dict(runtime_components)
        runtime_components["main_llm"] = "complete"
        executed = list(executed_components) + ["main_llm"]
        skipped = list(skipped_components) + [
            "profile", "rag", "risk_graph", "fork", "social",
            "intervention_search", "oasis", "oasis_verification", "fraud_interaction",
        ]
        core = {
            "scenario": canonical,
            "scenario_type": raw.get("scenario_type") or canonical,
            "risk_level": risk_level,
            "summary": assessment,
            "assessment": assessment,
            "evidence": evidence,
            "recommended_action": recommended_action,
            "assistant_message": direct_assistant_message,
            "is_direct_llm_baseline": True,
            "provenance": {
                "metric_source": "direct_llm",
                "has_counterfactual_runtime": False,
                "has_rag": False,
                "has_risk_graph": False,
                "has_social_runtime": False,
                "has_oasis": False,
                "runtime_components": runtime_components,
            },
        }
        result = CogSecAnalysisResult(
            profile={}, persona_state_vector={}, strategies=[], graph={},
            risk_graph_bundle={}, world_state_snapshot={}, branch_a_log=[],
            branch_b_log=[], fork_comparison={}, counterfactual_report={},
            intervention_prescriptions=[], t0_fast_response={},
            sanitization=sanitization, metrics={"benchmarks": {}}, anomalies=[],
            implementation_status={"direct_llm_baseline": "complete"},
            scenario_metadata={"canonical": canonical, "recognised": canonical != "unknown"},
            scenario_extension={"direct_llm": {"input_sanitized": True}},
            benchmark_prediction={}, cogsec_analysis={},
            adapter_diagnostics={"adapter_warnings": ["direct_llm_baseline"]},
            runtime_components=runtime_components,
            status="complete", core_analysis=core,
            ablation_variant={
                "variant_id": "direct_llm",
                "variant_label": "Direct LLM (baseline)",
                "executed_components": executed,
                "skipped_components": skipped,
            },
            tone=tone,
        )

        # The direct-LLM baseline obeys the same boundary as the full runtime.
        result.report_state = build_report_state(result.to_dict())

        if include_benchmark:
            try:
                benchmark_payload = build_benchmark_payload(
                    result=result.to_dict(),
                    scenario_text=analysis_text,
                    scenario_type=canonical,
                )
                result.benchmark_prediction = benchmark_payload["prediction"]
                result.cogsec_analysis = benchmark_payload["cogsec_analysis"]
                result.adapter_diagnostics = benchmark_payload["adapter_diagnostics"]
            except Exception as exc:
                logger.warning("direct LLM benchmark adapter failed: %s", exc)
                result.benchmark_prediction = {}
                result.cogsec_analysis = {}
                result.adapter_diagnostics = {"adapter_warnings": [str(exc)]}
        else:
            result.benchmark_prediction = {}
            result.cogsec_analysis = {}
            result.adapter_diagnostics = {"adapter_warnings": ["benchmark_adapter_not_requested"]}

        try:
            conversational = build_conversational_response(
                result=result.to_dict(),
                user_message=analysis_text,
                tone=tone,
                conversation_id=conversation_id,
                turn_id=turn_id,
                reporter_client=self.reporter_client,
                reporter_mode=Config.MIRO_REPORTER_POLICY_MODE,
                reporter_checkpoint_path=Config.MIRO_REPORTER_ADAPTER_PATH,
                reporter_max_tokens=Config.MIRO_REPORTER_OUTPUT_MAX_TOKENS,
            )
            result.assistant_message = conversational["assistant_message"]
            result.plain_view = conversational.get("plain_view")
            result.most_important_action = conversational.get("most_important_action")
            result.reporter_provenance = conversational["reporter_provenance"]
            result.response_plan = conversational["response_plan"]
            result.graph_payload = conversational["graph_payload"]
            result.suggested_followups = conversational["suggested_followups"]
            result.latency_profile = conversational["latency_profile"]
            result.conversation_state = conversational["conversation_state"]
        except Exception as exc:
            result.assistant_message = str(assessment)
            result.plain_view = None
            result.most_important_action = None
            result.reporter_provenance = {
                "backend": "deterministic",
                "fallback_used": True,
                "fallback_reason": f"reporter_pipeline_failed:{type(exc).__name__}",
            }
            result.response_plan = {"error": str(exc), "tone": tone}
            result.graph_payload = {}
            result.suggested_followups = []
            result.latency_profile = {"metric_source": "direct_llm"}
            result.conversation_state = {"tone": tone, "has_cached_analysis": False}

        request_total_ms = round((time.perf_counter() - request_started) * 1000, 2)
        timing["request_total_ms"] = request_total_ms
        result.request_total_ms = request_total_ms
        result.timing_breakdown = timing
        result.metrics["end_to_end_ms"] = request_total_ms
        result.metrics["end_to_end_target_met"] = request_total_ms < 30000
        result.metrics["latency_profile"] = timing
        payload = json.dumps(result.to_dict(), ensure_ascii=False, default=str)
        result.response_payload_bytes = len(payload.encode("utf-8"))
        result.payload_duplicate_fields = self._find_duplicate_fields(result.to_dict())
        return result

    # ------------------------------------------------------------------
    # Dead / legacy methods kept below this point are unused by the online
    # analyze path except ``_score_branch``, which now rolls CHS/ASS/SSS/EES
    # on the mainline 6-step traces.

    def _score_branch(self, branch_log: List[Dict[str, Any]], scorer: RiskScorer) -> None:
        """滚动更新分支分数，并写回每步分数增量。"""
        previous = scorer.scores
        for item in branch_log:
            updated = scorer.update_scores(
                agent_action=item.get("agent_action", ""),
                triggered_principles=item.get("triggered_principles", []),
                is_protection_action=item.get("is_protection_action", False),
                asset_exposure_coefficient=item.get("asset_exposure_coefficient", 0.0),
            )
            item["score_delta"] = {
                "CHS": round(updated.CHS - previous.CHS, 2),
                "ASS": round(updated.ASS - previous.ASS, 2),
                "SSS": round(updated.SSS - previous.SSS, 2),
                "EES": round(updated.EES - previous.EES, 2),
            }
            item["scores_after"] = updated.to_dict()
            previous = updated

    def _build_branch(
        self,
        profile: CognitiveProfile,
        strategies: List[Any],
        branch_name: str,
        defensive: bool,
    ) -> List[Dict[str, Any]]:
        """根据策略构造危险分支与防御分支。"""
        max_steps = min(Config.MAX_SIMULATION_STEPS, max(3, len(strategies) + 1))
        branch_log: List[Dict[str, Any]] = []

        if not strategies:
            strategies = self._fallback_strategies()

        for index in range(max_steps):
            strategy = strategies[min(index, len(strategies) - 1)]
            principles = [strategy.cialdini_principle]
            if index % 2 == 1 and not defensive:
                principles.append("scarcity" if strategy.cialdini_principle != "scarcity" else "authority")

            if defensive:
                action = self.threat_rag.constrain_action(
                    '受害者通过官方渠道核验，并对"' + strategy.tactic_name + '"保持距离',
                    strategy,
                )
                response = "选择回拨官方客服、暂停转账并向家人求助"
                asset_exposure = 0.01 if index == 0 else 0.0
                protection = True
            else:
                action = self.threat_rag.constrain_action(
                    '攻击者使用"' + strategy.tactic_name + '"推进对话，要求进一步操作',
                    strategy,
                )
                response = f"受害者在 {strategy.typical_dialogue[:18]} 的引导下继续配合"
                asset_exposure = min(0.32, 0.08 + index * 0.07)
                protection = False

            branch_log.append(
                {
                    "step": index + 1,
                    "branch": branch_name,
                    "strategy_id": strategy.id,
                    "triggered_principles": principles,
                    "agent_action": action,
                    "victim_response": response,
                    "is_protection_action": protection,
                    "asset_exposure_coefficient": asset_exposure,
                    "evidence_case_id": strategy.id.split(":")[0] if ":" in strategy.id else None,
                    "evidence_similarity": round(0.58 + index * 0.06, 2),
                }
            )

        return branch_log

    def _build_graph(self, profile: CognitiveProfile, strategies: List[Any]) -> Dict[str, Any]:
        """构造前端图谱可视化数据。"""
        nodes: List[Dict[str, Any]] = [
            {
                "id": "profile",
                "name": profile.scenario_type or "未知场景",
                "category": "scenario",
                "value": profile.overall_vulnerability_score(),
                "symbolSize": 64,
                "risk": profile.overall_vulnerability_score(),
                "description": profile.summary(),
            }
        ]
        links: List[Dict[str, Any]] = []
        categories = [
            {"name": "scenario"},
            {"name": "state"},
            {"name": "vulnerability"},
            {"name": "protection"},
            {"name": "strategy"},
        ]

        feature_map = {
            "state": ["time_pressure", "financial_pressure", "info_asymmetry", "emotional_volatility"],
            "vulnerability": ["authority_compliance", "social_proof_sensitivity", "scarcity_sensitivity", "trust_threshold"],
            "protection": ["decision_delay", "verification_habit", "help_seeking", "link_check_ability"],
        }

        for group_name, feature_keys in feature_map.items():
            for feature_name in feature_keys:
                score = getattr(profile, feature_name, 5.0)
                node_id = f"feature:{feature_name}"
                nodes.append(
                    {
                        "id": node_id,
                        "name": feature_name,
                        "category": group_name,
                        "value": score,
                        "risk": score if group_name != "protection" else 10 - score,
                        "symbolSize": 28 + score * 2.4,
                        "description": profile.reasoning.get(feature_name, ""),
                    }
                )
                links.append(
                    {
                        "source": "profile",
                        "target": node_id,
                        "value": round(score, 2),
                        "label": feature_name,
                    }
                )

        for strategy in strategies[:3]:
            strategy_id = f"strategy:{strategy.id}"
            nodes.append(
                {
                    "id": strategy_id,
                    "name": strategy.tactic_name,
                    "category": "strategy",
                    "value": strategy.intensity_level * 3,
                    "risk": 6 + strategy.intensity_level,
                    "symbolSize": 30 + strategy.intensity_level * 10,
                    "description": strategy.description,
                }
            )
            links.append(
                {
                    "source": "profile",
                    "target": strategy_id,
                    "value": strategy.intensity_level,
                    "label": strategy.cialdini_principle,
                }
            )

        return {"nodes": nodes, "links": links, "categories": categories}

    def _build_core_analysis(
        self,
        canonical: str,
        profile: Any,
        risk_graph_bundle: Any,
        fork_comparison: Any,
        risk_breakdown: Any,
        scenario_extension: Dict[str, Any],
        detection: Any,
        fraud_is_primary: bool = False,
        runtime_components: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Build a core_analysis dict from runtime results.

        This replaces the benchmark_adapter as the primary data source
        for response_planner.  It contains only facts produced during
        analysis — no benchmark-specific labels or heuristics.
        """
        # ── Common fields ──────────────────────────────────────
        core: Dict[str, Any] = {
            "scenario": canonical,
            "risk_level": _risk_level_from_breakdown(risk_breakdown),
            "risk_type": {
                "fraud_im": "诈骗诱导",
                "public_opinion": "虚假信息",
                "event_propagation": "虚假信息",
            }.get(canonical, "认知风险"),
            "retrieval_backend": getattr(risk_graph_bundle, "retrieval_backend", "keyword_fallback"),
        }
        case_provenance = (scenario_extension or {}).get("canonical_case", {}) or {}
        social_summary = (scenario_extension or {}).get("social_state_summary", {}) or {}
        if social_summary:
            core["agent_count"] = social_summary.get("actor_count") or social_summary.get("agent_count")
            core["topology_type"] = social_summary.get("topology_type")
        if case_provenance:
            core["provenance"] = {
                "canonical_case_id": case_provenance.get("case_id"),
                "grounding": case_provenance.get("grounding", {}),
                "simulation_state_id": case_provenance.get("simulation_state_id"),
            }
        selection_search = (scenario_extension or {}).get("propagation_intervention_search", {}) or {}
        effective_selection = selection_search.get("effective_selected_intervention", {})
        if isinstance(effective_selection, dict) and effective_selection:
            selected_action = (
                effective_selection.get("best_intervention_action")
                or effective_selection.get("message")
                or ""
            )
            core["effective_selected_intervention"] = effective_selection
            core["selection_source"] = selection_search.get("selection_source", "proxy")
            core["recommended_intervention"] = selected_action
            core["recommended_action"] = selected_action

        if canonical == "unknown":
            core.update({
                "requires_clarification": True,
                "assessment": "当前材料缺少足够场景信号，暂不进入特定场景运行时。",
            })

        # ── Fraud-specific ─────────────────────────────────────
        if canonical == "fraud_im":
            core["is_fraud"] = True
            core["fraud_type"] = _fraud_type_from_profile(profile)
            # Do not collapse two different quantities.  The counterfactual
            # score estimates this user's outcome risk under the simulated
            # branches; observed high-risk requests describe threat severity.
            # A resilient profile must not turn an explicit transfer or
            # credential request into a "low-threat" message.
            core["personalized_outcome_risk_level"] = _risk_level_from_breakdown(risk_breakdown)
            core["fraud_is_primary"] = fraud_is_primary

            # Asset targets from RiskGraph
            assets = []
            for item in getattr(risk_graph_bundle, "asset_targets", []) or []:
                if isinstance(item, dict):
                    assets.append({"label": item.get("label", ""), "type": item.get("type", "")})
                else:
                    assets.append({"label": getattr(item, "label", ""), "type": getattr(item, "type", "")})
            core["asset_targets"] = assets

            # Fork points from RiskGraph
            forks = []
            for item in getattr(risk_graph_bundle, "fork_points", []) or []:
                if isinstance(item, dict):
                    forks.append({"label": item.get("label", item.get("type", "")), "type": item.get("type", ""), "id": item.get("id", "")})
                else:
                    forks.append({"label": getattr(item, "label", getattr(item, "type", "")), "type": getattr(item, "type", ""), "id": getattr(item, "id", "")})
            core["fork_points"] = forks
            core["threat_level"] = _fraud_threat_level(
                forks=forks,
                fallback=core["personalized_outcome_risk_level"],
            )
            core["risk_level"] = core["threat_level"]

            # Intervention window from fork comparison
            window = getattr(fork_comparison, "best_intervention_window", {}) or {}
            core["intervention_window"] = {
                "start_turn": window.get("open_step", 1),
                "end_turn": window.get("close_step", 2),
                "rationale": window.get("label", ""),
            }
            core["expected_warning"] = "请通过官方渠道核实对方身份和请求"
            core["expected_safe_action"] = "暂停当前操作，拨打官方客服电话确认"

            # Counterfactual paths
            core["counterfactual_paths"] = {
                "trajectory_gap": getattr(fork_comparison, "trajectory_gap", 0.0),
                "key_divergence": "Branch B 通过核验和延迟决策降低风险暴露",
            }

        # ── Public opinion ─────────────────────────────────────
        elif canonical == "public_opinion":
            prop = (scenario_extension or {}).get("propagation_normalized", {}) or {}
            narrative = prop.get("narrative_analysis", {}) or {}
            core["event_summary"] = str(case_provenance.get("summary") or "")
            core["propagation_risk_level"] = _risk_level_from_breakdown(risk_breakdown)
            core["narrative_threads"] = (
                prop.get("narrative_threads")
                or case_provenance.get("claims")
                or []
            )
            # Read only the canonical propagation contract.
            core["emotion_signal"] = {
                "dominant_emotion": prop.get("dominant_emotion") or "unknown",
                "amplification_level": prop.get("amplification_level") or "unknown",
            }
            core["official_response_gap"] = {
                "status": "unknown",
                "severity": _risk_level_from_breakdown(risk_breakdown),
                "description": prop.get("response_gap_description", "权威信息源回应状态待核实"),
            }
            core["uncertainty_points"] = prop.get("distortion_points", [])
            core["expected_intervention_action"] = (
                core.get("recommended_intervention")
                or prop.get("recommended_action")
                or "权威信息源发布核实结果，降低信息不确定性"
            )
            core["expected_safe_public_action"] = (
                prop.get("recommended_public_action")
                or "公众通过多源交叉验证后再转发"
            )
            core["narrative_analysis"] = _compact_public_narrative_summary(narrative)

        # ── Event propagation ──────────────────────────────────
        elif canonical == "event_propagation":
            prop = (scenario_extension or {}).get("propagation_normalized", {}) or {}
            core["event_summary"] = str(case_provenance.get("summary") or "")
            core["coverage_risk"] = _risk_level_from_breakdown(risk_breakdown)
            core["origin_node"] = prop.get("origin_node")
            core["amplifier_nodes"] = prop.get("amplifier_nodes") or []
            core["propagation_path"] = prop.get("propagation_path") or []
            core["distortion_points"] = prop.get("distortion_points") or []
            core["claim_analysis"] = prop.get("claim_analysis") or {}
            core["claims"] = case_provenance.get("claims") or []
            core["expected_containment_action"] = (
                core.get("recommended_intervention")
                or prop.get("recommended_containment")
                or "事实核查机构介入，核对传播链关键节点信息"
            )

        # ── Evidence trace (all scenarios) ─────────────────────
        evidence_trace = []
        for item in case_provenance.get("evidence_items", []) or []:
            if isinstance(item, dict) and str(item.get("content") or "").strip():
                evidence_trace.append({
                    "id": item.get("evidence_id", ""),
                    "text": str(item.get("content")),
                    "source": "canonical_case",
                })
        for item in getattr(risk_graph_bundle, "evidence_items", []) or []:
            if isinstance(item, dict):
                evidence_trace.append({
                    "id": item.get("id", ""),
                    "text": item.get("detail", item.get("label", "")),
                    "source": "risk_graph",
                })
            else:
                evidence_trace.append({
                    "id": getattr(item, "id", ""),
                    "text": getattr(item, "detail", getattr(item, "label", "")),
                    "source": "risk_graph",
                })
        core["evidence_trace"] = evidence_trace

        # ── Evidence spans ─────────────────────────────────────
        core["evidence_spans"] = [
            {"id": e["id"], "text": e["text"], "source": e["source"]}
            for e in evidence_trace[:6]
        ]

        # ── Provenance ─────────────────────────────────────────
        components = runtime_components or {}
        normalized_prop = (scenario_extension or {}).get("propagation_normalized", {}) or {}
        core["provenance"] = {
            "metric_source": normalized_prop.get("metric_source") or "runtime",
            "has_counterfactual_runtime": (
                components.get("fork") == "complete"
                or components.get("fraud_interaction") in {"complete", "degraded"}
            ),
            "has_rag": components.get("rag") == "complete",
            "has_risk_graph": components.get("risk_graph") == "complete",
            "has_social_runtime": components.get("social") == "complete",
            "has_oasis": components.get("oasis") == "complete",
            "has_oasis_verification": components.get("oasis_verification") == "complete",
            "runtime_components": dict(components),
        }

        return core

    def _build_case_evidence(self, scenario_type: str, strategies: List[Any]) -> str:
        """拼装案例证据摘要。"""
        if not strategies:
            return (
                f"未检索到与 {scenario_type or '当前场景'} 直接对应的具体攻击话术；"
                "案例库模板不会被当作本次输入中已经发生的事实。"
            )
        grounded = [
            strategy for strategy in strategies
            if self._strategy_field(strategy, "grounding_status") != "inferred"
        ]
        if not grounded:
            return (
                f"{scenario_type or '当前场景'}只有知识库候选线索，"
                "输入没有直接出现具体攻击动作，因此不把候选话术写成已发生事实。"
            )
        evidence = "；".join(
            f"{self._strategy_field(strategy, 'tactic_name')}（{self._strategy_field(strategy, 'cialdini_principle')}，强度 {self._strategy_field(strategy, 'intensity_level')}）"
            for strategy in grounded[:3]
        )
        return '与"' + str(scenario_type) + '"最相关的真实攻击话术包括：' + evidence + '。'

    def _strategy_field(self, strategy: Any, key: str) -> Any:
        if isinstance(strategy, dict):
            return strategy.get(key, "")
        return getattr(strategy, key, "")

    def _collect_anomalies(
        self,
        sanitization_result: Dict[str, Any],
        risk_graph_bundle: Dict[str, Any],
        fork_comparison: Dict[str, Any],
        runtime_result: Dict[str, Any],
        risk_breakdown: Dict[str, Any],
    ) -> List[str]:
        anomalies = set()
        if sanitization_result.get("pii_leak_detected"):
            anomalies.add("pii_leak_detected")
        if risk_graph_bundle.get("hallucination_rollback"):
            anomalies.add("hallucination_rollback")
        for item in fork_comparison.get("anomaly_flags", []):
            anomalies.add(item)
        if runtime_result.get("degraded"):
            anomalies.add("timeout_degraded")
        if risk_breakdown.get("audit_required"):
            anomalies.add("audit_required")
        return sorted(anomalies)

    def _ensure_case_library(self) -> None:
        """加载欺诈案例库 (delegates to shared runtime when available)."""
        if self._case_library_loaded:
            return

        if self._runtime is not None:
            self.threat_rag = self._runtime.get_threat_rag()
            self._runtime.ensure_case_library()
            self._case_library_source = "shared_runtime"
            self._case_library_count = len(getattr(self.threat_rag, "cases", []) or [])
            self._case_library_loaded = True
            return

        # Standalone path (backward-compatible)
        try:
            if self.threat_rag is None:
                self.threat_rag = ThreatKnowledgeRAG(Config.CHROMA_PATH)
            loaded_cases = self.threat_rag.load_cases_from_file(Config.FRAUD_CASE_DB_PATH)
        except Exception as exc:
            logger.warning("加载欺诈案例文件失败（%s），已降级到内置案例库。路径：%s 错误：%s",
                           type(exc).__name__, Config.FRAUD_CASE_DB_PATH, exc)
            loaded_cases = []
            self._case_library_fallback_used = True
            self._case_library_fallback_reason = f"{type(exc).__name__}: {exc}"

        if loaded_cases:
            self._case_library_source = "file"
            self._case_library_count = len(loaded_cases)
            self._case_library_loaded = True
            logger.info("已从文件加载 %s 条欺诈案例（路径：%s）", len(loaded_cases), Config.FRAUD_CASE_DB_PATH)
            return

        fallback_cases = [FraudCase.from_dict(item) for item in self._default_case_library()]
        self.threat_rag.ingest_cases(fallback_cases)
        self._case_library_source = "builtin_default"
        self._case_library_count = len(fallback_cases)
        self._case_library_fallback_used = True
        self._case_library_fallback_reason = self._case_library_fallback_reason or "file_empty_or_missing"
        self._case_library_loaded = True
        logger.warning("欺诈案例文件为空或不存在，已加载内置默认案例库。期望路径：%s", Config.FRAUD_CASE_DB_PATH)

    def _safe_build_llm_client(self):
        """Create LLM client (standalone path only — runtime handles its own)."""
        if getattr(Config, "COGSEC_USE_LOCAL_GEMMA", False):
            try:
                from ..utils import LocalGemmaClient
                return LocalGemmaClient(
                    model_path=Config.COGSEC_LOCAL_MODEL_PATH,
                    device=Config.COGSEC_LOCAL_GEMMA_DEVICE,
                    torch_dtype=Config.COGSEC_LOCAL_GEMMA_DTYPE,
                    max_new_tokens=Config.COGSEC_LOCAL_GEMMA_MAX_NEW_TOKENS,
                    offload_folder=Config.COGSEC_LOCAL_GEMMA_OFFLOAD_DIR,
                )
            except Exception as exc:
                logger.warning("本地 Gemma 初始化失败，继续尝试项目主 LLM: %s", exc)

        # Final: project-specific key only; legacy LLM_API_KEY gated
        main_key = Config.MIRO_COGSEC_MAIN_LLM_API_KEY
        if not main_key and Config.MIRO_COGSEC_ALLOW_LEGACY_LLM_KEY:
            main_key = Config.LLM_API_KEY
        if not main_key:
            return None
        try:
            from ..utils.llm_client import LLMClient
            return LLMClient(
                api_key=main_key,
                connect_timeout=Config.MIRO_COGSEC_MAIN_LLM_CONNECT_TIMEOUT_SEC,
                read_timeout=Config.MIRO_COGSEC_MAIN_LLM_READ_TIMEOUT_SEC,
                max_retries=Config.MIRO_COGSEC_MAIN_LLM_RETRIES,
                mode_name="main_llm",
            )
        except Exception as exc:
            logger.warning("LLM 客户端初始化失败，转为启发式模式: %s", exc)
            return None

    def _safe_build_reporter_client(self, main_client):
        """Build an optional dedicated local reporter or reuse the main client."""
        mode = str(getattr(Config, "MIRO_REPORTER_POLICY_MODE", "auto") or "auto").lower()
        if mode == "deterministic":
            return None
        dedicated_key = getattr(Config, "MIRO_REPORTER_API_KEY", None)
        dedicated_ready = bool(
            dedicated_key
            and getattr(Config, "MIRO_REPORTER_BASE_URL", None)
            and getattr(Config, "MIRO_REPORTER_MODEL", None)
        )
        if mode in {"remote_model", "dedicated_llm"} or (mode == "auto" and dedicated_ready):
            if not dedicated_ready:
                return None
            try:
                from ..utils.llm_client import LLMClient
                return LLMClient(
                    api_key=dedicated_key,
                    base_url=Config.MIRO_REPORTER_BASE_URL,
                    model=Config.MIRO_REPORTER_MODEL,
                    connect_timeout=Config.MIRO_REPORTER_CONNECT_TIMEOUT_SEC,
                    read_timeout=Config.MIRO_REPORTER_READ_TIMEOUT_SEC,
                    max_retries=Config.MIRO_REPORTER_RETRIES,
                    mode_name="remote_reporter",
                    enable_thinking=Config.MIRO_REPORTER_ENABLE_THINKING,
                )
            except Exception as exc:
                logger.warning("远程 Reporter 客户端初始化失败，保留确定性回退: %s", exc)
                return None
        if mode not in {"local_model", "trained_policy"}:
            # Pin the reporter thinking switch on a twin of the main client;
            # see CogSecRuntime._reporter_twin for why the raw shared client
            # must not be returned unchanged.
            try:
                from ..utils.llm_client import LLMClient, clone_llm_client_with_thinking
                if isinstance(main_client, LLMClient):
                    return clone_llm_client_with_thinking(
                        main_client, enable_thinking=Config.MIRO_REPORTER_ENABLE_THINKING
                    )
            except Exception:
                pass
            return main_client

        model_path = getattr(Config, "MIRO_REPORTER_MODEL_PATH", None)
        adapter_path = getattr(Config, "MIRO_REPORTER_ADAPTER_PATH", None)
        if not model_path or (mode == "trained_policy" and not adapter_path):
            return None
        try:
            from ..utils import LocalGemmaClient
            return LocalGemmaClient(
                model_path=model_path,
                adapter_path=adapter_path,
                device=Config.MIRO_REPORTER_DEVICE,
                torch_dtype=Config.MIRO_REPORTER_DTYPE,
                max_new_tokens=Config.MIRO_REPORTER_MAX_NEW_TOKENS,
                offload_folder=Config.MIRO_REPORTER_OFFLOAD_DIR,
            )
        except Exception as exc:
            logger.warning("Reporter 客户端初始化失败，保留确定性回退: %s", exc)
            return None

    def _count_triggered_forks(self, text: str) -> int:
        """统计场景文本中触发的 fork 规则数量，用于多规则叠加计分。"""
        from ..modules.mainline_runtime import MiroFishRuntime
        text_lower = (text or "").lower()
        count = sum(
            1 for rule in MiroFishRuntime.FORK_RULES
            if any(kw.lower() in text_lower for kw in rule["keywords"])
        )
        return max(1, count)

    def _fallback_strategies(self) -> List[Any]:
        """无案例时使用的默认策略。"""
        cases = [FraudCase.from_dict(case) for case in self._default_case_library()[:3]]
        return [case.attack_strategies[0] for case in cases if case.attack_strategies]

    def _default_case_library(self) -> List[Dict[str, Any]]:
        """内置默认案例库。"""
        return [
            {
                "id": "case_credit_001",
                "category": "虚假征信类",
                "attack_role": "fake_credit_officer",
                "target_info": ["银行卡", "验证码", "屏幕共享"],
                "attack_strategies": [
                    {
                        "id": "case_credit_001:authority_call",
                        "cialdini_principle": "authority",
                        "tactic_name": "征信中心权威施压",
                        "description": "冒充征信或监管人员，以影响征信和司法风险制造服从压力。",
                        "typical_dialogue": "你的征信即将受影响，请立即按我说的做。",
                        "escalation_condition": "受害者表达担忧或害怕账户冻结时。",
                        "intensity_level": 3,
                    }
                ],
                "dialogue_examples": [{"attacker": "马上核验", "victim": "我有点担心"}],
                "risk_keywords": ["征信", "安全账户", "司法风险", "冻结"],
                "red_flags": ["要求屏幕共享", "要求向安全账户转账"],
            },
            {
                "id": "case_rebate_001",
                "category": "刷单返利类",
                "attack_role": "task_operator",
                "target_info": ["垫付款", "收款码", "银行卡"],
                "attack_strategies": [
                    {
                        "id": "case_rebate_001:small_profit",
                        "cialdini_principle": "reciprocity",
                        "tactic_name": "小额返利建立信任",
                        "description": "先给受害者小额甜头，再引导进入更大金额任务。",
                        "typical_dialogue": "这单你已经赚到了，继续做高级单返佣更高。",
                        "escalation_condition": "受害者体验到首次返利后。",
                        "intensity_level": 2,
                    }
                ],
                "dialogue_examples": [{"attacker": "再做一单就能提现", "victim": "那我继续"}],
                "risk_keywords": ["返利", "任务", "垫付", "佣金"],
                "red_flags": ["先返小利后要大额垫付", "提现前还要继续充值"],
            },
            {
                "id": "case_invest_001",
                "category": "虚假网络投资理财类",
                "attack_role": "investment_advisor",
                "target_info": ["投资本金", "证券账户", "转账凭证"],
                "attack_strategies": [
                    {
                        "id": "case_invest_001:expert_packaging",
                        "cialdini_principle": "authority",
                        "tactic_name": "导师包装与内幕背书",
                        "description": "包装专业导师身份，提供内幕消息和稳赚预期。",
                        "typical_dialogue": "我是内部老师，这波行情只有小范围学员能跟上。",
                        "escalation_condition": "受害者表现出赚钱意愿时。",
                        "intensity_level": 2,
                    }
                ],
                "dialogue_examples": [{"attacker": "大家都跟上了", "victim": "我也想试试"}],
                "risk_keywords": ["导师", "内幕", "群聊", "盈利截图"],
                "red_flags": ["承诺稳赚不赔", "展示可伪造收益截图"],
            },
        ]

    def _find_duplicate_fields(self, obj: Any, path: str = "", max_depth: int = 4) -> List[Dict[str, Any]]:
        """Identify fields that appear at multiple paths in the payload.

        Returns top duplicate fields with path locations and sizes.
        Not used to modify output — informational only.
        """
        import json
        from collections import defaultdict

        signatures: Dict[str, List[tuple]] = defaultdict(list)
        _collect_signatures(obj, path, signatures, depth=0, max_depth=max_depth)

        duplicates = []
        for sig, locations in signatures.items():
            if len(locations) > 1:
                # Estimate size of one copy
                for loc_path, val in locations:
                    try:
                        size = len(json.dumps(val, ensure_ascii=False, default=str).encode("utf-8"))
                    except Exception:
                        size = 0
                    duplicates.append({
                        "field_signature": sig,
                        "occurrences": len(locations),
                        "paths": [p for p, _ in locations],
                        "approx_bytes_per_copy": size,
                    })
                    break  # one size estimate per signature
        duplicates.sort(key=lambda d: d["approx_bytes_per_copy"] * d["occurrences"], reverse=True)
        return duplicates[:5]


def _collect_signatures(obj, path, signatures, depth, max_depth):
    """Recursively collect field signatures with their paths."""
    if depth > max_depth:
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            child_path = f"{path}.{k}" if path else k
            if isinstance(v, (dict, list)):
                # For structured children, hash a compact representation
                try:
                    import json
                    sig = f"{k}:{_structure_shape(v)}"
                except Exception:
                    sig = f"{k}:<unhashable>"
            else:
                sig = f"{k}"
            signatures[sig].append((child_path, v))
            if isinstance(v, dict):
                _collect_signatures(v, child_path, signatures, depth + 1, max_depth)
            elif isinstance(v, list) and len(v) > 0:
                # Sample first element of lists
                if isinstance(v[0], dict):
                    _collect_signatures(v[0], f"{child_path}[0]", signatures, depth + 1, max_depth)


def _structure_shape(obj):
    """Return a compact string describing the structural shape of an object."""
    import json
    if isinstance(obj, dict):
        keys = sorted(obj.keys())[:20]
        return "{" + ",".join(keys[:10]) + "}"
    if isinstance(obj, list):
        if len(obj) == 0:
            return "[]"
        return f"[{len(obj)}]{_structure_shape(obj[0]) if obj else ''}"
    return str(type(obj).__name__)


def _amplification_from_propagation(prop: Dict[str, Any]) -> str:
    """Extract amplification level from propagation result, defaulting to 'unknown'."""
    if not prop:
        return "unknown"
    cov = prop.get("cumulative_coverage") or prop.get("final_coverage")
    if cov is not None:
        try:
            cov_val = float(cov)
            if cov_val > 0.6:
                return "high"
            if cov_val > 0.3:
                return "medium"
            return "low"
        except (TypeError, ValueError):
            pass
    return prop.get("amplification_level", "unknown")


def _risk_level_from_breakdown(risk_breakdown: Any) -> str:
    """Extract risk level string from CounterfactualRiskBreakdown."""
    try:
        rl = getattr(risk_breakdown, "risk_level", None)
        if rl:
            return str(rl).lower()
    except Exception:
        pass
    return "medium"


def _fraud_threat_level(*, forks: List[Dict[str, Any]], fallback: str) -> str:
    """Estimate observed fraud threat severity from domain-level actions.

    This is intentionally independent of benchmark cases and wording.  It
    protects the user-facing safety level from being diluted by a resilient
    persona prior in the counterfactual outcome score.
    """
    observed = {str(item.get("type") or "") for item in forks if isinstance(item, dict)}
    high_impact = {
        "transfer_money",
        "verification_code",
        "screen_share",
        "unknown_app_download",
        "phishing_link_entry",
        "identity_asset_exchange",
    }
    if observed & high_impact:
        return "high"
    if observed & {"private_contact_lure", "social_isolation", "unlicensed_financial_service"}:
        return "medium"
    return str(fallback or "medium").lower()


def _fraud_type_from_profile(profile: Any) -> str:
    """Extract fraud type label from CognitiveProfile."""
    try:
        st = getattr(profile, "scenario_type", None)
        if st and st != "unknown":
            return str(st)
    except Exception:
        pass
    return "可疑即时通讯场景"


def _clip_text(obj: Any, max_len: int = 120) -> str:
    """Extract a short text from an object for display."""
    if isinstance(obj, dict):
        for key in ("scenario_type", "description", "label", "text"):
            v = obj.get(key, "")
            if v:
                return str(v)[:max_len]
    return str(obj)[:max_len]


def _compact_public_narrative_summary(narrative: Any) -> Dict[str, Any]:
    """Keep core_analysis small while exposing public-opinion-specific facts."""
    if not isinstance(narrative, dict):
        return {
            "dominant_narrative": None,
            "narrative_distribution": {},
            "polarization": 0.0,
            "fragmentation": 0.0,
            "most_contested_communities": [],
            "metric_semantics": "simulation_proxy",
        }
    community = narrative.get("community_narrative_distribution", {})
    contested = []
    if isinstance(community, dict):
        for community_id, distribution in community.items():
            if not isinstance(distribution, dict):
                continue
            ordered = sorted(distribution.items(), key=lambda item: float(item[1] or 0.0), reverse=True)
            if len(ordered) >= 2:
                contested.append({
                    "community": community_id,
                    "top_narratives": [item[0] for item in ordered[:2]],
                    "disagreement": round(max(0.0, float(ordered[0][1]) - float(ordered[1][1])), 6),
                })
    contested.sort(key=lambda item: item["disagreement"])
    provenance = narrative.get("provenance", {})
    return {
        "dominant_narrative": narrative.get("dominant_narrative"),
        "narrative_distribution": narrative.get("narrative_share", {}),
        "narrative_entropy": narrative.get("narrative_entropy", 0.0),
        "polarization": narrative.get("narrative_polarization", narrative.get("stance_polarization", 0.0)),
        "stance_polarization": narrative.get("stance_polarization", 0.0),
        "fragmentation": narrative.get("community_fragmentation", 0.0),
        "cross_community_disagreement": narrative.get("cross_community_disagreement", 0.0),
        "narrative_switch_rate": narrative.get("narrative_switch_rate", 0.0),
        "most_contested_communities": contested[:3],
        "intervention_outcome": narrative.get("intervention_outcome", {}),
        "metric_semantics": provenance.get("metric_semantics", "simulation_proxy") if isinstance(provenance, dict) else "simulation_proxy",
    }


def _build_propagation_agents_from_social_state(
    scenario_type: str,
    scenario_text: str,
    social_state: Any = None,
) -> list:
    """Map the shared SocialState actors for Top-K OASIS verification."""
    if social_state is not None:
        from ..modules.social_state import actor_to_propagation_agent
        return [actor_to_propagation_agent(actor) for actor in social_state.actors]
    try:
        from ..modules.social_state import build_social_state, actor_to_propagation_agent
        from ..modules.social_state.builder import demo_agent_count
        state = build_social_state(
            scenario_text=scenario_text,
            scenario_type=scenario_type,
            n_agents=demo_agent_count(scenario_type),
            seed=42,
        )
        return [actor_to_propagation_agent(a) for a in state.actors]
    except Exception:
        from ..modules.social_state.builder import demo_agent_count
        from ..modules.propagation.agent_factory import build_agents
        return build_agents(
            scenario_type,
            n_agents=demo_agent_count(scenario_type),
            seed=42,
            scenario_text=scenario_text,
        )
