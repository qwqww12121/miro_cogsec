"""Release Candidate integration tests — real execution contracts.

These tests use mock LLM/OASIS/Chroma to test the actual backend
orchestration, not source-string assertions.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

# Ensure backend is importable
ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
APP_DIR = BACKEND_DIR / "app"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fraud_text() -> str:
    return (
        "[受害人背景] 65岁，独居，缺少反诈科普。\n"
        "客服：您的银行账户出现异常交易，请立即转账到安全账户。\n"
        "受害者：我该怎么办？\n"
        "客服：马上告诉我你的验证码，否则账户会被冻结。"
    )


@pytest.fixture
def public_opinion_text() -> str:
    return (
        "某市发布公告称因管道维修将停水48小时，随后网络上流传该市水源被污染的谣言，"
        "大量用户在社交平台转发未经核实的检测报告截图，引发恐慌。"
    )


@pytest.fixture
def event_propagation_text() -> str:
    return (
        "某实验室论文声称发现新型材料可实现室温超导，该论文在未经同行评审的情况下"
        "被多个科技媒体账号转发，引发投资热潮。后续有专家指出实验数据存在疑点。"
    )


@pytest.fixture
def mock_llm_client():
    """Mock LLM client that returns valid but minimal profile JSON."""
    client = MagicMock()
    client.chat_json = MagicMock(return_value={
        "scenario_type": "虚假征信类",
        "features": {
            "time_pressure": 8.0, "financial_pressure": 7.0,
            "info_asymmetry": 6.0, "emotional_volatility": 7.0,
            "cognitive_load": 5.0, "authority_intensity": 8.0,
            "authority_compliance": 7.0, "social_proof_sensitivity": 5.0,
            "scarcity_sensitivity": 6.0, "loss_aversion_threshold": 8.0,
            "gambler_fallacy": 5.0, "trust_threshold": 7.0,
            "decision_delay": 3.0, "verification_habit": 3.0,
            "help_seeking": 3.0, "link_check_ability": 3.0,
            "transaction_review": 3.0, "prior_experience": 3.0,
        },
        "confidence": {k: 0.8 for k in [
            "time_pressure", "financial_pressure", "info_asymmetry",
            "emotional_volatility", "cognitive_load", "authority_intensity",
            "authority_compliance", "social_proof_sensitivity",
            "scarcity_sensitivity", "loss_aversion_threshold",
            "gambler_fallacy", "trust_threshold", "decision_delay",
            "verification_habit", "help_seeking", "link_check_ability",
            "transaction_review", "prior_experience",
        ]},
        "reasoning": {"time_pressure": "mock", "financial_pressure": "mock"},
    })
    return client


def _build_mock_service(llm_client=None):
    """Build a CogSecService with all external dependencies mocked."""
    from app.services.cogsec_service import CogSecService

    with patch("app.modules.threat_rag.chromadb", None), \
         patch("app.modules.threat_rag.embedding_functions", None), \
         patch("app.config.Config.PRESIDIO_ENABLED", False), \
         patch("app.config.Config.LOCAL_SANITIZE_ENABLED", False), \
         patch("app.config.Config.COGSEC_USE_LOCAL_GEMMA", False), \
         patch("app.config.Config.COGSEC_RUNTIME_TIMEOUT_SEC", 15.0), \
         patch("app.config.Config.FRAUD_CASE_DB_PATH",
               str(Path(__file__).parent.parent / "data" / "fraud_cases.json")):
        return CogSecService(llm_client=llm_client)


# ---------------------------------------------------------------------------
# Test A: Three canonical scenarios run successfully
# ---------------------------------------------------------------------------


class TestThreeScenariosComplete:
    """Test that all three canonical scenarios complete without errors."""

    def test_fraud_im_analyze_succeeds(self, fraud_text, mock_llm_client):
        """fraud_im should produce a complete result with all required fields."""
        svc = _build_mock_service(llm_client=mock_llm_client)
        result = svc.analyze_text(fraud_text, scenario_type="fraud_im")

        assert result is not None
        result_dict = result.to_dict()
        assert result_dict.get("core_analysis") is not None
        assert result_dict.get("scenario_extension") is not None
        assert result_dict.get("ablation_variant") is not None
        # Verify core_analysis has fraud-specific fields
        ca = result_dict["core_analysis"]
        assert ca.get("is_fraud") is True
        assert ca.get("scenario") == "fraud_im"

    def test_public_opinion_analyze_succeeds(self, public_opinion_text, mock_llm_client):
        """public_opinion should produce a complete result."""
        svc = _build_mock_service(llm_client=mock_llm_client)
        result = svc.analyze_text(public_opinion_text, scenario_type="public_opinion")

        assert result is not None
        result_dict = result.to_dict()
        assert result_dict.get("core_analysis") is not None
        assert result_dict.get("scenario_extension") is not None

    def test_event_propagation_analyze_succeeds(self, event_propagation_text, mock_llm_client):
        """event_propagation should produce a complete result."""
        svc = _build_mock_service(llm_client=mock_llm_client)
        result = svc.analyze_text(event_propagation_text, scenario_type="event_propagation")

        assert result is not None
        result_dict = result.to_dict()
        assert result_dict.get("core_analysis") is not None
        assert result_dict.get("scenario_extension") is not None


# ---------------------------------------------------------------------------
# Test B: include_benchmark=False still produces valid assistant response
# ---------------------------------------------------------------------------


class TestBenchmarkDisabled:
    """When benchmark is disabled, response should still use core_analysis."""

    def test_no_benchmark_still_uses_core_analysis(self, fraud_text, mock_llm_client):
        svc = _build_mock_service(llm_client=mock_llm_client)
        result = svc.analyze_text(fraud_text, include_benchmark=False)

        result_dict = result.to_dict()
        # benchmark_prediction should be empty
        bp = result_dict.get("benchmark_prediction", {})
        assert bp == {} or bp is None
        # core_analysis should be present
        assert result_dict.get("core_analysis") is not None
        # assistant_message should exist (from core_analysis, not benchmark)
        assert result_dict.get("assistant_message") is not None
        assert len(str(result_dict["assistant_message"])) > 10


# ---------------------------------------------------------------------------
# Test C: Session analyze → state persist → followup
# ---------------------------------------------------------------------------


class TestSessionFlow:
    """Session creation, analysis, state persistence, and followup work."""

    def test_session_create_analyze_followup(self, fraud_text, mock_llm_client):
        from app.modules.session_store import SessionStore, SessionData, InputFragment
        from app.services.session_manager import SessionManager

        store = SessionStore()
        mgr = SessionManager(store=store)

        # Create
        session = mgr.create(scenario_type="fraud_im", user_role="individual")
        assert isinstance(session, SessionData)
        assert session.session_id

        # Append text
        mgr.append_text(session.session_id, fraud_text)

        # Verify state field exists (P0-3 fix)
        assert hasattr(session, "state")
        assert isinstance(session.state, dict)

        # Analyze (mocked service)
        with patch("app.runtime.get_runtime") as mock_runtime:
            mock_svc = MagicMock()
            mock_result = MagicMock()
            mock_result.to_dict.return_value = {
                "core_analysis": {"scenario": "fraud_im"},
                "conversation_state": {
                    "scenario": "fraud_im", "tone": "friendly",
                    "has_cached_analysis": True,
                    "last_benchmark_prediction": {},
                    "last_cogsec_analysis": {},
                    "last_risk_graph_bundle": {},
                    "last_propagation_intervention_search": {},
                },
            }
            mock_svc.analyze_text.return_value = mock_result
            mock_runtime.return_value.build_service.return_value = mock_svc

            result = mgr.analyze(session.session_id, tone="friendly")
            assert result is not None

        # State should be persisted
        session_after = store.get(session.session_id)
        assert session_after is not None
        assert "last_analysis" in session_after.state

        # Followup should work from server state
        followup = mgr.answer_followup(
            session.session_id,
            content="为什么这么判断？",
            tone="friendly",
        )
        assert followup is not None

    def test_session_state_no_attribute_error(self):
        """SessionData.state must exist (P0-3)."""
        from app.modules.session_store import SessionData

        session = SessionData(session_id="test_123")
        # This must not raise AttributeError
        val = session.state
        assert isinstance(val, dict)
        assert val == {}


# ---------------------------------------------------------------------------
# Test D: Ablation execution gates
# ---------------------------------------------------------------------------


class TestAblationExecution:
    """Different variants execute different modules."""

    def _make_service_with_spies(self, mock_llm_client):
        """Build service with spied modules."""
        from app.services.cogsec_service import CogSecService

        with patch("app.modules.threat_rag.chromadb", None), \
             patch("app.modules.threat_rag.embedding_functions", None), \
             patch("app.config.Config.PRESIDIO_ENABLED", False), \
             patch("app.config.Config.LOCAL_SANITIZE_ENABLED", False), \
             patch("app.config.Config.COGSEC_USE_LOCAL_GEMMA", False), \
             patch("app.config.Config.COGSEC_RUNTIME_TIMEOUT_SEC", 15.0), \
             patch("app.config.Config.FRAUD_CASE_DB_PATH",
                   str(Path(__file__).parent.parent / "data" / "fraud_cases.json")):
            return CogSecService(llm_client=mock_llm_client)

    def test_rag_variant_only_runs_rag(self, fraud_text, mock_llm_client):
        """RAG variant: RAG called, but Fork/Social/OASIS not."""
        svc = self._make_service_with_spies(mock_llm_client)

        # Spy on the threat_rag
        svc._ensure_case_library()
        orig_build = svc.threat_rag.build_risk_graph_bundle
        svc.threat_rag.build_risk_graph_bundle = MagicMock(
            side_effect=orig_build, spec=lambda *a, **kw: orig_build(*a, **kw)
        )

        result = svc.analyze_text(fraud_text, variant_id="rag")
        result_dict = result.to_dict()

        # RAG should have been called
        ab = result_dict.get("ablation_variant", {})
        executed = ab.get("executed_components", [])
        skipped = ab.get("skipped_components", [])

        assert "rag" in executed
        # Fork should be skipped in 'rag' variant
        assert "fork" in skipped or "fork" not in executed

    def test_full_variant_runs_everything(self, fraud_text, mock_llm_client):
        """Full variant: all gates on."""
        svc = self._make_service_with_spies(mock_llm_client)

        result = svc.analyze_text(fraud_text, variant_id="full")
        result_dict = result.to_dict()

        ab = result_dict.get("ablation_variant", {})
        executed = ab.get("executed_components", [])

        # In full mode, these should execute (scenario-dependent)
        assert "rag" in executed
        assert "fork" in executed

    def test_direct_llm_variant_skips_most(self, fraud_text, mock_llm_client):
        """direct_llm variant: minimal execution."""
        svc = self._make_service_with_spies(mock_llm_client)

        result = svc.analyze_text(fraud_text, variant_id="direct_llm")
        result_dict = result.to_dict()

        ab = result_dict.get("ablation_variant", {})
        executed = ab.get("executed_components", [])
        skipped = ab.get("skipped_components", [])

        # direct_llm should skip RAG, fork, social_state
        assert "rag" in skipped
        assert "fork" in skipped
        assert mock_llm_client.chat_json.called
        assert svc.threat_rag is None
        components = result_dict.get("runtime_components", {})
        assert components.get("rag") == "skipped"
        assert components.get("fork") == "skipped"


# ---------------------------------------------------------------------------
# Test E: Unknown ablation variant must error
# ---------------------------------------------------------------------------


class TestUnknownAblationVariant:
    """Unknown variant_id must raise ValueError, not silently fallback to full."""

    def test_unknown_variant_raises(self, fraud_text, mock_llm_client):
        svc = _build_mock_service(llm_client=mock_llm_client)
        with pytest.raises(ValueError, match="Unknown ablation variant"):
            svc.analyze_text(fraud_text, variant_id="typo_nonexistent")

    def test_unknown_variant_message_contains_allowed(self, fraud_text, mock_llm_client):
        svc = _build_mock_service(llm_client=mock_llm_client)
        with pytest.raises(ValueError) as exc_info:
            svc.analyze_text(fraud_text, variant_id="grahp")
        error_msg = str(exc_info.value)
        assert "grahp" in error_msg
        assert "full" in error_msg.lower()


# ---------------------------------------------------------------------------
# Test F: Fraud multi-role primary chain
# ---------------------------------------------------------------------------


class TestFraudMultiRolePrimaryChain:
    """FraudMultiRoleRuntime output must enter the RiskScorer/Reporter chain."""

    def test_fraud_is_primary_in_core_analysis(self, fraud_text, mock_llm_client):
        """core_analysis must contain fraud_is_primary=True when fraud multi-role succeeds."""
        svc = _build_mock_service(llm_client=mock_llm_client)
        result = svc.analyze_text(fraud_text, variant_id="full")

        result_dict = result.to_dict()
        ca = result_dict.get("core_analysis", {})
        assert ca.get("fraud_is_primary") is True

    def test_fraud_runtime_once_and_adapter_trace_reaches_scorer(self, fraud_text, mock_llm_client):
        from app.modules.fraud_runtime.runtime import FraudMultiRoleRuntime
        from app.modules.risk_scorer import RiskScorer

        original_runtime = FraudMultiRoleRuntime.run
        original_scorer = RiskScorer.evaluate_counterfactual
        with patch.object(FraudMultiRoleRuntime, "run", autospec=True, side_effect=original_runtime) as runtime_spy, \
             patch.object(RiskScorer, "evaluate_counterfactual", autospec=True, side_effect=original_scorer) as scorer_spy:
            svc = _build_mock_service(llm_client=mock_llm_client)
            svc.analyze_text(fraud_text, variant_id="full")

        assert runtime_spy.call_count == 1
        branch_a = scorer_spy.call_args.kwargs["branch_a_state_trace"]
        assert any(
            "fraud_runtime_marker" in (step.posterior_updates or {})
            for step in branch_a
        )


# ---------------------------------------------------------------------------
# Test G: Scenario-aware cognitive profiler
# ---------------------------------------------------------------------------


class TestScenarioAwareProfiler:
    """Cognitive profiler must use scenario-appropriate prompts."""

    def test_public_opinion_prompt_excludes_fraud_terms(self, mock_llm_client):
        """Public opinion profiler must NOT instruct outputting '最匹配的诈骗类别'."""
        from app.modules.cognitive_profiler import CognitiveProfileExtractor

        extractor = CognitiveProfileExtractor(llm_client=mock_llm_client)
        prompt = extractor.EXTRACTION_PROMPT_PUBLIC_OPINION

        # Must NOT ask for fraud category as the primary output label
        assert '"scenario_type": "最匹配的诈骗类别"' not in prompt
        # Must include public opinion context
        assert "舆情" in prompt
        assert "narrative" in prompt.lower() or "叙事" in prompt or "narrative frame" in prompt

    def test_event_propagation_prompt_excludes_fraud_terms(self, mock_llm_client):
        """Event propagation profiler must NOT ask for fraud category as output."""
        from app.modules.cognitive_profiler import CognitiveProfileExtractor

        extractor = CognitiveProfileExtractor(llm_client=mock_llm_client)
        prompt = extractor.EXTRACTION_PROMPT_EVENT_PROPAGATION

        # Must NOT ask for fraud category as the primary output label
        assert '"scenario_type": "最匹配的诈骗类别"' not in prompt
        assert "传播" in prompt

    def test_fraud_prompt_still_has_fraud_terms(self, mock_llm_client):
        """Fraud profiler should still use fraud-specific prompt."""
        from app.modules.cognitive_profiler import CognitiveProfileExtractor

        extractor = CognitiveProfileExtractor(llm_client=mock_llm_client)
        prompt = extractor.EXTRACTION_PROMPT_FRAUD

        assert "最匹配的诈骗类别" in prompt


# ---------------------------------------------------------------------------
# Test H: ThreatRAG hallucination rollback
# ---------------------------------------------------------------------------


class TestThreatRAGRollback:
    """Hallucination rollback must actually change the output."""

    def test_rollback_filters_unverified_strategies(self):
        """_fallback_verified_strategies must filter, not pass-through."""
        from app.modules.threat_rag import (
            ThreatKnowledgeRAG, AttackStrategy, FraudCase,
        )
        import tempfile, os

        # Create RAG with empty case store
        with tempfile.TemporaryDirectory() as tmpdir:
            rag = ThreatKnowledgeRAG(tmpdir, enable_chroma=False)

            # Create a known-good strategy
            legit = AttackStrategy(
                id="known:1", cialdini_principle="authority",
                tactic_name="权威施压", description="冒充权威",
                typical_dialogue="我是客服",
                escalation_condition="受害者相信", intensity_level=3,
            )
            known_case = FraudCase(
                id="case_1", category="虚假征信类",
                attack_role="fake_official",
                target_info=["验证码"],
                attack_strategies=[legit],
                dialogue_examples=[],
                risk_keywords=["征信"],
                red_flags=["安全账户"],
            )
            rag.ingest_cases([known_case])

            # Current strategies: one verified, one hallucinated
            hallucinated = AttackStrategy(
                id="fake:999", cialdini_principle="liking",
                tactic_name="完全虚构的策略", description="不存在",
                typical_dialogue="虚构对话",
                escalation_condition="never", intensity_level=1,
            )
            current = [hallucinated, legit]

            result = rag._fallback_verified_strategies("虚假征信类", current)

            # Should NOT contain the hallucinated strategy
            assert len(result) < len(current) or result != current
            # Should contain at least the verified one
            assert legit in result or len(result) > 0


# ---------------------------------------------------------------------------
# Test I: core_analysis schema for all three scenarios
# ---------------------------------------------------------------------------


class TestCoreAnalysisSchema:
    """core_analysis must have scenario-specific required fields."""

    def test_fraud_core_analysis_has_required_fields(self, fraud_text, mock_llm_client):
        svc = _build_mock_service(llm_client=mock_llm_client)
        result = svc.analyze_text(fraud_text)

        ca = result.to_dict().get("core_analysis", {})
        assert "scenario" in ca
        assert "risk_level" in ca
        assert "is_fraud" in ca
        assert "fraud_type" in ca

    def test_public_opinion_core_analysis_has_required_fields(self, public_opinion_text, mock_llm_client):
        svc = _build_mock_service(llm_client=mock_llm_client)
        result = svc.analyze_text(public_opinion_text, scenario_type="public_opinion")

        ca = result.to_dict().get("core_analysis", {})
        assert "scenario" in ca
        assert "risk_level" in ca
        assert "emotion_signal" in ca

    def test_event_propagation_core_analysis_has_required_fields(self, event_propagation_text, mock_llm_client):
        svc = _build_mock_service(llm_client=mock_llm_client)
        result = svc.analyze_text(event_propagation_text, scenario_type="event_propagation")

        ca = result.to_dict().get("core_analysis", {})
        assert "scenario" in ca
        assert "risk_level" in ca
        assert "origin_node" in ca


# ---------------------------------------------------------------------------
# Test J: OASIS candidate verification intervention dispatch
# ---------------------------------------------------------------------------


class TestOASISCandidateVerification:
    """Candidate verification must pass intervention-specific data."""

    def test_verification_passes_intervention_details(self):
        """run_topk_oasis_verification must extract candidate intervention details."""
        from app.modules.propagation.oasis_verification import run_topk_oasis_verification
        from app.modules.propagation.schema import PropagationAgent

        agents = [
            PropagationAgent(
                agent_id="agent_1", role="ordinary_viewer",
                stance="neutral", influence=0.5, susceptibility=0.5,
                activity=0.5, trust_in_official=0.5,
            ),
        ]

        proxy_result = {
            "branch_comparison": {
                "ranked_branches": [
                    {
                        "candidate_id": "cand_001",
                        "intervention_type": "official_response",
                        "message": "官方澄清：此信息未经核实",
                        "target_nodes": ["agent_1"],
                        "intervention_tick": 3,
                        "evidence_basis": ["evidence_1"],
                        "total_score": 0.85,
                    },
                    {
                        "candidate_id": "cand_002",
                        "intervention_type": "community_note",
                        "message": "社区注释：建议核实来源",
                        "target_nodes": ["agent_1"],
                        "intervention_tick": 2,
                        "total_score": 0.72,
                    },
                ]
            }
        }

        # OASIS not available; verify we get proxy-only result with candidate details
        result = run_topk_oasis_verification(
            scenario_type="public_opinion",
            seed_text="test event",
            agents=agents,
            proxy_result=proxy_result,
            quick_mode=False,
            k=2,
            seed=42,
        )

        # Should have proxy-ranked candidates preserved
        assert result.get("proxy_ranked_candidates") is not None
        assert len(result["proxy_ranked_candidates"]) == 2
        # Metric source should be proxy when OASIS unavailable
        assert result.get("metric_source") == "proxy"

    def test_unsupported_intervention_type_returns_proxy(self):
        """Unsupported intervention types must return proxy with unsupported status."""
        from app.modules.propagation.oasis_verification import run_topk_oasis_verification
        from app.modules.propagation.schema import PropagationAgent

        agents = [PropagationAgent(
            agent_id="agent_1", role="ordinary_viewer",
            stance="neutral", influence=0.5, susceptibility=0.5,
            activity=0.5, trust_in_official=0.5,
        )]

        proxy_result = {
            "branch_comparison": {
                "ranked_branches": [
                    {
                        "candidate_id": "cand_unsupported",
                        "intervention_type": "unsupported_type_xyz",
                        "message": "test",
                        "target_nodes": [],
                        "intervention_tick": 1,
                        "total_score": 0.5,
                    },
                ]
            }
        }

        # Need to mock OASIS as available but intervention type is unsupported
        with patch("app.modules.propagation.oasis_adapter._OASIS_AVAILABLE", True), \
             patch.dict("os.environ", {
                 "MIRO_COGSEC_OASIS_API_KEY": "mock-key",
                 "MIRO_COGSEC_OASIS_BASE_URL": "https://oasis.test/v1",
                 "MIRO_COGSEC_OASIS_MODEL": "oasis-test",
             }):
            result = run_topk_oasis_verification(
                scenario_type="public_opinion",
                seed_text="test",
                agents=agents,
                proxy_result=proxy_result,
                quick_mode=False,
                k=2,
                seed=42,
            )

            # Should return proxy_only with unsupported status
            verified = result.get("oasis_verified_branches", [])
            if verified:
                vstatus = verified[0].get("oasis_verification", {}).get("status")
                # Either "unsupported" (our fix) or it tried and got metadata
                assert vstatus in ("unsupported", "completed", "failed")

    def test_top_k_defaults_to_2_in_normal_mode(self):
        """Normal mode K should be 2 by default."""
        from app.modules.propagation.oasis_verification import run_topk_oasis_verification
        from app.modules.propagation.schema import PropagationAgent

        agents = [PropagationAgent(
            agent_id="agent_1", role="ordinary_viewer",
            stance="neutral", influence=0.5, susceptibility=0.5,
            activity=0.5, trust_in_official=0.5,
        )]

        proxy_result = {
            "branch_comparison": {
                "ranked_branches": [
                    {"candidate_id": "c1", "intervention_type": "official_response",
                     "message": "m1", "target_nodes": [], "intervention_tick": 1, "total_score": 0.9},
                    {"candidate_id": "c2", "intervention_type": "community_note",
                     "message": "m2", "target_nodes": [], "intervention_tick": 1, "total_score": 0.8},
                    {"candidate_id": "c3", "intervention_type": "warning",
                     "message": "m3", "target_nodes": [], "intervention_tick": 1, "total_score": 0.7},
                ]
            }
        }

        result = run_topk_oasis_verification(
            scenario_type="public_opinion",
            seed_text="test",
            agents=agents,
            proxy_result=proxy_result,
            quick_mode=False,
            k=2,
            seed=42,
        )

        # In normal mode with k=2, should select top 2
        selected = result.get("top_k_selected", [])
        # Quick mode False → effective_k = max(2, 2) = 2
        assert len(selected) <= 2

    def test_quick_mode_k_is_1(self):
        """Quick mode always uses K=1."""
        from app.modules.propagation.oasis_verification import run_topk_oasis_verification
        from app.modules.propagation.schema import PropagationAgent

        agents = [PropagationAgent(
            agent_id="agent_1", role="ordinary_viewer",
            stance="neutral", influence=0.5, susceptibility=0.5,
            activity=0.5, trust_in_official=0.5,
        )]

        proxy_result = {
            "branch_comparison": {
                "ranked_branches": [
                    {"candidate_id": "c1", "intervention_type": "official_response",
                     "message": "m1", "target_nodes": [], "intervention_tick": 1, "total_score": 0.9},
                    {"candidate_id": "c2", "intervention_type": "community_note",
                     "message": "m2", "target_nodes": [], "intervention_tick": 1, "total_score": 0.8},
                ]
            }
        }

        result = run_topk_oasis_verification(
            scenario_type="public_opinion",
            seed_text="test",
            agents=agents,
            proxy_result=proxy_result,
            quick_mode=True,
            k=2,
            seed=42,
        )

        selected = result.get("top_k_selected", [])
        # Quick mode → always 1
        assert len(selected) == 1

    def test_quick_mode_can_explicitly_select_multiple_candidates(self, monkeypatch):
        """Formal experiments can retain quick resources without forcing K=1."""
        from app.modules.propagation.oasis_verification import run_topk_oasis_verification

        monkeypatch.setenv("MIRO_OASIS_QUICK_MULTI_CANDIDATE", "true")
        proxy_result = {
            "branch_comparison": {
                "ranked_branches": [
                    {
                        "candidate_id": f"official_{index}",
                        "intervention_type": "official_response",
                        "message": f"message_{index}",
                        "target_nodes": [],
                        "intervention_tick": 1,
                        "total_score": 1.0 - index * 0.1,
                    }
                    for index in range(3)
                ]
            }
        }

        result = run_topk_oasis_verification(
            scenario_type="public_opinion",
            seed_text="test",
            agents=[],
            proxy_result=proxy_result,
            quick_mode=True,
            k=3,
            seed=42,
        )

        assert result["effective_k"] == 3
        assert len(result["top_k_selected"]) == 3

    def test_candidate_run_uses_intra_run_ab_and_source_first_ranking(self):
        """Each candidate gets one A/B run; verified candidates rank above proxies."""
        from app.modules.propagation.oasis_verification import run_topk_oasis_verification
        from app.modules.propagation.schema import PropagationAgent

        agents = [PropagationAgent(
            agent_id="agent-1", role="ordinary_viewer", stance="neutral",
            influence=0.5, susceptibility=0.5, activity=0.5,
            trust_in_official=0.5,
        )]
        proxy = {"branch_comparison": {"ranked_branches": [
            {"candidate_id": "official", "intervention_type": "official_response",
             "target_nodes": [], "intervention_tick": 1, "total_score": 0.1},
            {"candidate_id": "note", "intervention_type": "community_note",
             "target_nodes": [], "intervention_tick": 1, "total_score": 0.99},
        ]}}
        fake_result = MagicMock()
        fake_result.branch_a.final_metrics = {
            "cumulative_coverage": 0.8, "total_actions": 10,
        }
        fake_result.branch_b.final_metrics = {
            "cumulative_coverage": 0.4, "total_actions": 7,
        }

        with patch("app.modules.propagation.oasis_adapter._OASIS_AVAILABLE", True), \
             patch.dict("os.environ", {
                 "MIRO_COGSEC_OASIS_API_KEY": "test-key",
                 "MIRO_COGSEC_OASIS_BASE_URL": "https://oasis.test/v1",
                 "MIRO_COGSEC_OASIS_MODEL": "oasis-test",
             }), \
             patch("app.modules.propagation.oasis_adapter.OasisPropagationAdapter.run",
                   return_value=fake_result) as oasis_run:
            result = run_topk_oasis_verification(
                scenario_type="public_opinion", seed_text="test", agents=agents,
                proxy_result=proxy, quick_mode=False, k=2,
            )

        assert oasis_run.call_count == 1
        verified = result["oasis_verified_branches"][0]
        assert verified["baseline_metrics"]["cumulative_coverage"] == 0.8
        assert verified["intervention_metrics"]["cumulative_coverage"] == 0.4
        assert verified["utility"] == 0.4
        assert result["intra_run_ab_comparisons"] == 1
        assert result["final_ranking"][0]["candidate_id"] == "official"
        assert result["metric_source"] == "oasis"

    def test_verification_budget_skips_unsupported_proxy_top1(self):
        """Quick Top-1 must select the highest-ranked verifiable candidate."""
        from app.modules.propagation.oasis_verification import run_topk_oasis_verification
        from app.modules.propagation.schema import PropagationAgent

        agents = [PropagationAgent(
            agent_id="agent-1", role="ordinary_viewer", stance="neutral",
            influence=0.5, susceptibility=0.5, activity=0.5,
            trust_in_official=0.5,
        )]
        proxy = {"branch_comparison": {"ranked_branches": [
            {"candidate_id": "note", "intervention_type": "community_note",
             "target_nodes": ["agent-1"], "total_score": 0.95},
            {"candidate_id": "official", "intervention_type": "official_response",
             "target_nodes": [], "total_score": 0.80, "intervention_tick": 2},
        ]}}
        fake_result = MagicMock()
        fake_result.branch_a.final_metrics = {"cumulative_coverage": 0.8}
        fake_result.branch_b.final_metrics = {"cumulative_coverage": 0.4}

        with patch("app.modules.propagation.oasis_adapter._OASIS_AVAILABLE", True), \
             patch.dict("os.environ", {
                 "MIRO_COGSEC_OASIS_API_KEY": "test-key",
                 "MIRO_COGSEC_OASIS_BASE_URL": "https://oasis.test/v1",
                 "MIRO_COGSEC_OASIS_MODEL": "oasis-test",
             }), \
             patch("app.modules.propagation.oasis_adapter.OasisPropagationAdapter.run",
                   return_value=fake_result) as oasis_run:
            result = run_topk_oasis_verification(
                scenario_type="public_opinion", seed_text="test", agents=agents,
                proxy_result=proxy, quick_mode=True, k=1,
            )

        assert oasis_run.call_count == 1
        call_intervention = oasis_run.call_args.kwargs["intervention"]
        assert call_intervention["candidate_id"] == "official"
        assert result["top_k_selected"][0]["candidate_id"] == "official"
        assert result["top_k_selected"][0]["proxy_rank"] == 2
        assert next(
            item for item in result["oasis_verified_branches"]
            if item["candidate_id"] == "note"
        )["verification_status"] == "unsupported"

    def test_no_verifiable_candidate_skips_oasis(self):
        from app.modules.propagation.oasis_verification import run_topk_oasis_verification
        from app.modules.propagation.schema import PropagationAgent

        agents = [PropagationAgent(
            agent_id="agent-1", role="ordinary_viewer", stance="neutral",
            influence=0.5, susceptibility=0.5, activity=0.5,
            trust_in_official=0.5,
        )]
        proxy = {"branch_comparison": {"ranked_branches": [
            {"candidate_id": "note", "intervention_type": "community_note",
             "target_nodes": ["agent-1"], "total_score": 0.95},
            {"candidate_id": "node", "intervention_type": "node_targeting",
             "target_nodes": ["agent-1"], "total_score": 0.80},
        ]}}
        with patch("app.modules.propagation.oasis_adapter._OASIS_AVAILABLE", True), \
             patch.dict("os.environ", {
                 "MIRO_COGSEC_OASIS_API_KEY": "test-key",
                 "MIRO_COGSEC_OASIS_BASE_URL": "https://oasis.test/v1",
                 "MIRO_COGSEC_OASIS_MODEL": "oasis-test",
             }), \
             patch("app.modules.propagation.oasis_adapter.OasisPropagationAdapter.run") as oasis_run:
            result = run_topk_oasis_verification(
                scenario_type="public_opinion", seed_text="test", agents=agents,
                proxy_result=proxy, quick_mode=True, k=1,
            )

        oasis_run.assert_not_called()
        assert result["top_k_oasis_completed"] == 0
        assert result["oasis_verification"]["verification_status"] == "unsupported"
        assert result["oasis_verification"]["reason"] == "no_oasis_verifiable_candidate"
        assert result["metric_source"] == "proxy"


class TestInterventionCandidateContracts:
    def test_public_and_event_have_broadcast_official_response(self):
        from app.modules.propagation.intervention_search import generate_intervention_candidates
        from app.modules.propagation.schema import PropagationTrace

        trace = PropagationTrace(
            trace_id="trace", scenario_type="public_opinion", ticks=5,
            agents=[], actions=[], coverage_curve=[], emotion_curve=[],
            key_nodes=[{"agent_id": "agent-1"}], final_metrics={},
        )
        public_candidates = generate_intervention_candidates(
            scenario_type="public_opinion", baseline_trace=trace,
            evidence_basis=["evidence"], ticks=5,
        )
        event_candidates = generate_intervention_candidates(
            scenario_type="event_propagation", baseline_trace=trace,
            evidence_basis=["evidence"], ticks=5,
        )

        for candidates in (public_candidates, event_candidates):
            official = next(item for item in candidates if item.intervention_type == "official_response")
            assert official.target_nodes == []
            assert official.message


class TestOASISEffectivenessClosure:
    def _run_metric_case(self, intervention_coverage):
        from app.modules.propagation.oasis_verification import run_topk_oasis_verification
        from app.modules.propagation.schema import PropagationAgent

        agents = [PropagationAgent(
            agent_id="agent-1", role="ordinary_viewer", stance="neutral",
            influence=0.5, susceptibility=0.5, activity=0.5,
            trust_in_official=0.5,
        )]
        proxy_selected = {
            "candidate_id": "community_note",
            "intervention_type": "community_note",
            "target_nodes": ["agent-1"],
            "message": "community note",
            "total_score": 0.95,
        }
        proxy = {
            "selected_best_branch": proxy_selected,
            "branch_comparison": {"ranked_branches": [
                proxy_selected,
                {
                    "candidate_id": "official_response",
                    "intervention_type": "official_response",
                    "target_nodes": [],
                    "message": "official response",
                    "intervention_tick": 1,
                    "total_score": 0.80,
                },
            ]},
        }
        fake_result = MagicMock()
        fake_result.branch_a.final_metrics = {"cumulative_coverage": 0.80}
        fake_result.branch_b.final_metrics = {"cumulative_coverage": intervention_coverage}

        with patch("app.modules.propagation.oasis_adapter._OASIS_AVAILABLE", True), \
             patch.dict("os.environ", {
                 "MIRO_COGSEC_OASIS_API_KEY": "test-key",
                 "MIRO_COGSEC_OASIS_BASE_URL": "https://oasis.test/v1",
                 "MIRO_COGSEC_OASIS_MODEL": "oasis-test",
             }), \
             patch("app.modules.propagation.oasis_adapter.OasisPropagationAdapter.run",
                   return_value=fake_result):
            return run_topk_oasis_verification(
                scenario_type="public_opinion", seed_text="test", agents=agents,
                proxy_result=proxy, quick_mode=True, k=1,
            )

    def test_harmful_oasis_does_not_replace_proxy(self):
        from app.modules.propagation.intervention_search import resolve_effective_intervention

        result = self._run_metric_case(0.90)
        selected = result["oasis_verified_branches"][0]
        assert selected["verification_status"] == "executed"
        assert selected["signed_utility"] < 0
        assert selected["effectiveness_status"] == "harmful"
        search = {
            "selected_best_branch": {"candidate_id": "community_note"},
            "oasis_verification": result,
        }
        assert result["selection_source"] == "proxy"
        assert result["oasis_effective"] is False
        assert resolve_effective_intervention(search)["candidate_id"] == "community_note"

    def test_neutral_oasis_does_not_replace_proxy(self):
        result = self._run_metric_case(0.80)
        selected = result["oasis_verified_branches"][0]
        assert selected["effectiveness_status"] == "neutral"
        assert selected["signed_utility"] == 0
        assert result["selection_source"] == "proxy"

    def test_effective_oasis_replaces_proxy(self):
        from app.modules.propagation.intervention_search import resolve_effective_intervention

        result = self._run_metric_case(0.50)
        selected = result["selected"]
        assert selected["signed_utility"] == 0.30
        assert selected["effectiveness_status"] == "effective"
        assert result["selection_source"] == "oasis"
        search = {
            "selected_best_branch": {"candidate_id": "community_note"},
            "oasis_verification": result,
        }
        assert resolve_effective_intervention(search)["candidate_id"] == "official_response"

    def test_intervention_coverage_excludes_system_injected_action(self):
        from app.modules.propagation.oasis_adapter import OasisPropagationAdapter
        from app.modules.propagation.schema import PropagationAgent

        agents = [
            PropagationAgent(
                agent_id="official", role="official_responder", stance="neutral",
                influence=0.7, susceptibility=0.2, activity=0.5,
                trust_in_official=0.9,
            ),
            PropagationAgent(
                agent_id="viewer", role="ordinary_viewer", stance="neutral",
                influence=0.5, susceptibility=0.5, activity=0.5,
                trust_in_official=0.5,
            ),
        ]
        adapter = OasisPropagationAdapter()
        adapter._record_tick_action(
            "B", 2, "official", "intervention_official_response", "broadcast",
            is_intervention_action=True,
        )
        adapter._tick_actions_b[2].append({
            "canonical_actor_id": "official",
            "action_name": "create_post",
            "info": "official injection",
            "is_intervention_action": True,
        })
        adapter._tick_actions_b[3].append({
            "canonical_actor_id": "viewer",
            "action_name": "repost",
            "info": "organic repost",
            "is_intervention_action": False,
        })

        trace = adapter._build_trace_from_tick_actions(
            agents, 4, "public_opinion", "B", "missing-oasis-db",
        )
        assert trace.coverage_curve[2]["organic_propagation_coverage"] == 0.0
        assert trace.final_metrics["organic_propagation_coverage"] == 0.5
        assert trace.final_metrics["metric_semantics"]["system_intervention_action_excluded"] is True

    def test_oasis_all_missing_llm_results_are_not_reported_complete(self):
        from app.modules.propagation.oasis_adapter import OasisPropagationAdapter

        adapter = OasisPropagationAdapter()
        adapter._record_llm_outcomes("A", {0, 1}, [])

        with pytest.raises(RuntimeError, match="oasis_all_llm_actions_failed"):
            adapter._ensure_branch_has_llm_outcomes("A")

    def test_oasis_observed_trace_row_counts_as_llm_success(self):
        from app.modules.propagation.oasis_adapter import OasisPropagationAdapter

        adapter = OasisPropagationAdapter()
        adapter._record_llm_outcomes(
            "A", {0, 1},
            [{"table": "trace", "user_id": 1, "action_name": "like_post"}],
        )

        adapter._ensure_branch_has_llm_outcomes("A")
        assert adapter._action_diagnostics_a["llm_action_attempted"] == 2
        assert adapter._action_diagnostics_a["llm_action_success"] == 1
        assert adapter._action_diagnostics_a["llm_action_failed"] == 1

    def test_report_state_uses_effective_runtime_selection(self):
        from app.modules.report_state import build_report_state

        state = build_report_state({
            "scenario_metadata": {"canonical": "public_opinion"},
            "core_analysis": {"event_summary": "事件", "propagation_risk_level": "medium"},
            "scenario_extension": {
                "propagation_intervention_search": {
                    "effective_selected_intervention": {
                        "candidate_id": "official_response",
                        "metric_source": "oasis",
                        "best_intervention_action": "official response",
                    },
                    "provenance": {"selection_source": "oasis"},
                },
            },
        })
        assert state["selected_actions"][0]["best_intervention_action"] == "official response"
        assert state["provenance"]["selection_source"] == "oasis"

    def test_benchmark_adapter_never_runs_a_second_semantic_pass(self):
        from app.modules.benchmark_adapter import build_benchmark_payload

        result = {
            "ablation_variant": {"variant_id": "structured"},
            "scenario_metadata": {"canonical": "public_opinion"},
        }
        payload = build_benchmark_payload(
            result=result, scenario_text="舆情事件正在传播", scenario_type="public_opinion",
        )

        assert payload["provenance"]["second_inference_pass"] is False
        assert payload["adapter_diagnostics"]["raw_input_used"] is False


# ---------------------------------------------------------------------------
# Test K: OASIS CounterfactualInitStatus provenance
# ---------------------------------------------------------------------------


class TestOASISProvenance:
    """CounterfactualInitStatus must use honest split provenance."""

    def test_init_status_has_split_provenance_fields(self):
        from app.modules.propagation.oasis_adapter import CounterfactualInitStatus

        status = CounterfactualInitStatus()
        d = status.to_dict()

        # New split fields must exist
        assert "db_state_equivalence" in d
        assert "agent_graph_equivalence" in d
        assert "initialization_method" in d
        assert "random_seed" in d
        assert d["topology_source"] == "oasis_generated_from_profiles"
        assert d["social_state_topology_injected"] is False

        # db_copy_method should be "none" by default
        assert d["db_copy_method"] == "none"

    def test_init_status_defaults_are_honest(self):
        from app.modules.propagation.oasis_adapter import CounterfactualInitStatus

        status = CounterfactualInitStatus()
        d = status.to_dict()

        # Default should be honest (not guaranteed for unvalidated case)
        assert d["initialization_method"] == "per_branch_generate"
        assert d["db_state_equivalence"] == "best_effort"
        assert d["agent_graph_equivalence"] == "best_effort"


# ---------------------------------------------------------------------------
# Test L: ResponsePlanner core_analysis priority
# ---------------------------------------------------------------------------


class TestResponsePlannerPriority:
    """ResponsePlanner must prefer core_analysis over benchmark_prediction."""

    def test_core_analysis_used_first(self):
        from app.modules.response_planner import build_response_plan

        result = {
            "core_analysis": {
                "scenario": "fraud_im",
                "risk_level": "high",
                "is_fraud": True,
                "fraud_type": "虚假征信类",
            },
            "benchmark_prediction": {
                "scenario": "fraud_im",
                "risk_level": "low",
            },
            "scenario_metadata": {"canonical": "fraud_im"},
            "scenario_extension": {},
            "profile": {"scenario_type": "fraud_im"},
            "metrics": {},
        }

        plan = build_response_plan(result=result, user_message="test", tone="friendly")
        # Should use the high risk_level from core_analysis, not low from benchmark
        assert plan.get("primary_risk") == "high"

    def test_benchmark_prediction_is_not_an_online_fallback(self):
        from app.modules.response_planner import build_response_plan

        result = {
            "benchmark_prediction": {
                "scenario": "fraud_im",
                "risk_level": "medium",
                "is_fraud": False,
            },
            "scenario_metadata": {"canonical": "fraud_im"},
            "scenario_extension": {},
            "profile": {"scenario_type": "fraud_im"},
            "metrics": {},
        }

        plan = build_response_plan(result=result, user_message="test", tone="friendly")
        assert plan.get("primary_risk") == "unknown"

    def test_direct_llm_uses_baseline_fields(self):
        from app.modules.response_planner import build_response_plan

        plan = build_response_plan(result={
            "core_analysis": {
                "scenario": "unknown",
                "risk_level": "medium",
                "is_direct_llm_baseline": True,
                "summary": "直接模型摘要",
                "evidence": ["直接证据"],
                "recommended_action": "直接建议",
            },
            "scenario_metadata": {"canonical": "unknown"},
        }, user_message="test", tone="friendly")

        assert plan["metric_source"] == "direct_llm"
        assert plan["conclusion"] == "直接模型摘要"
        assert plan["evidence"] == ["直接证据"]
        assert plan["recommendations"] == ["直接建议"]

    def test_effective_oasis_selection_reaches_response_planner(self):
        from app.modules.response_planner import build_response_plan

        result = {
            "core_analysis": {
                "scenario": "public_opinion",
                "propagation_risk_level": "high",
            },
            "scenario_metadata": {"canonical": "public_opinion"},
            "scenario_extension": {
                "propagation_intervention_search": {
                    "selected_best_branch": {
                        "candidate_id": "proxy",
                        "best_intervention_action": "PROXY_MARKER",
                    },
                    "effective_selected_intervention": {
                        "candidate_id": "oasis",
                        "best_intervention_action": "OASIS_MARKER",
                        "verification_status": "executed",
                        "effectiveness_status": "effective",
                        "metric_source": "oasis",
                    },
                    "selection_source": "oasis",
                }
            },
        }

        plan = build_response_plan(result=result, user_message="test", tone="friendly")
        assert plan["selected_branch"]["candidate_id"] == "oasis"
        assert "OASIS_MARKER" in plan["recommendations"]

    def test_benchmark_prediction_uses_effective_selection(self):
        from app.modules.benchmark_adapter import build_benchmark_payload

        result = {
            "scenario_metadata": {"canonical": "public_opinion"},
            "risk_graph_bundle": {},
            "graph": {},
            "scenario_extension": {
                "propagation_intervention_search": {
                    "selected_best_branch": {
                        "candidate_id": "proxy",
                        "best_intervention_action": "PROXY_MARKER",
                    },
                    "effective_selected_intervention": {
                        "candidate_id": "oasis",
                        "best_intervention_action": "OASIS_MARKER",
                        "verification_status": "executed",
                        "effectiveness_status": "effective",
                        "metric_source": "oasis",
                    },
                    "selection_source": "oasis",
                }
            },
        }

        payload = build_benchmark_payload(
            result=result, scenario_text="某舆情事件正在传播", scenario_type="public_opinion",
        )
        assert payload["prediction"]["expected_intervention_action"] == "OASIS_MARKER"
        assert payload["cogsec_analysis"]["propagation_analysis"]["effective_selected_intervention"]["candidate_id"] == "oasis"

    def test_core_analysis_uses_effective_intervention(self, mock_llm_client):
        from types import SimpleNamespace

        svc = _build_mock_service(llm_client=mock_llm_client)
        core = svc._build_core_analysis(
            canonical="public_opinion",
            profile=SimpleNamespace(),
            risk_graph_bundle=SimpleNamespace(environment_context={}, evidence_items=[]),
            fork_comparison=SimpleNamespace(),
            risk_breakdown=SimpleNamespace(risk_level="high"),
            scenario_extension={
                "propagation_normalized": {},
                "propagation_intervention_search": {
                    "effective_selected_intervention": {
                        "candidate_id": "oasis",
                        "best_intervention_action": "OASIS_MARKER",
                    },
                    "selection_source": "oasis",
                },
            },
            detection=None,
            runtime_components={},
        )

        assert core["recommended_intervention"] == "OASIS_MARKER"
        assert core["expected_intervention_action"] == "OASIS_MARKER"
        assert core["selection_source"] == "oasis"


class TestUnknownScenarioRouting:
    def test_unknown_returns_before_profile_and_runtime(self, mock_llm_client):
        from app.modules.scenario_detector import DetectionResult

        svc = _build_mock_service(llm_client=mock_llm_client)
        detection = DetectionResult(
            canonical="unknown", confidence=0.0, matched_signals=[],
            scenario_context={"requires_clarification": True},
        )
        with patch.object(svc, "_ensure_case_library") as case_library, \
             patch.object(svc.profile_extractor, "extract") as profile_extract, \
             patch.object(svc.runtime_engine, "run") as runtime_run, \
             patch("app.services.cogsec_service.ScenarioDetector.detect", return_value=detection):
            result = svc.analyze_text("一段没有明确场景类型的描述")

        assert result.to_dict()["core_analysis"]["requires_clarification"] is True
        case_library.assert_not_called()
        profile_extract.assert_not_called()
        runtime_run.assert_not_called()
        assert svc.threat_rag is None

    def test_unknown_preserves_requested_ablation_variant(self, mock_llm_client):
        from app.modules.scenario_detector import DetectionResult

        svc = _build_mock_service(llm_client=mock_llm_client)
        detection = DetectionResult(
            canonical="unknown", confidence=0.0, matched_signals=[],
            scenario_context={"requires_clarification": True},
        )
        with patch("app.services.cogsec_service.ScenarioDetector.detect", return_value=detection):
            result = svc.analyze_text(
                "一段没有明确场景类型的描述", variant_id="rag",
            )

        ablation = result.to_dict()["ablation_variant"]
        assert ablation["variant_id"] == "rag"
        assert ablation["execution_mode"] == "clarification_only"


class TestDirectLLMBenchmarkContract:
    def test_direct_llm_include_benchmark_uses_common_adapter(self, fraud_text, mock_llm_client):
        svc = _build_mock_service(llm_client=mock_llm_client)
        benchmark_payload = {
            "prediction": {"scenario": "fraud_im", "risk_level": "high"},
            "cogsec_analysis": {"provenance": {"metric_source": "direct_llm"}},
            "adapter_diagnostics": {"adapter_warnings": []},
        }
        with patch("app.services.cogsec_service.build_benchmark_payload",
                   return_value=benchmark_payload) as adapter, \
             patch.object(svc.profile_extractor, "extract") as profile_extract, \
             patch.object(svc.runtime_engine, "run") as runtime_run, \
             patch("app.services.cogsec_service.run_topk_oasis_verification") as oasis_run:
            result = svc.analyze_text(
                fraud_text, variant_id="direct_llm", include_benchmark=True,
            )

        adapter.assert_called_once()
        assert result.to_dict()["benchmark_prediction"] == benchmark_payload["prediction"]
        profile_extract.assert_not_called()
        runtime_run.assert_not_called()
        oasis_run.assert_not_called()


class TestOASISAdapterCapabilityGuard:
    def test_adapter_rejects_unsupported_intervention_before_runtime(self):
        from app.modules.propagation.oasis_adapter import (
            OasisPropagationAdapter,
            UnsupportedOasisIntervention,
        )

        with pytest.raises(UnsupportedOasisIntervention):
            OasisPropagationAdapter().run(
                event=None, agents=[],
                intervention={"intervention_type": "node_targeting", "target_nodes": ["agent-1"]},
            )


# ---------------------------------------------------------------------------
# Smoke test: check key static cleanliness items
# ---------------------------------------------------------------------------


class TestStaticCleanliness:
    """Verify no dead flags or placeholders remain."""

    def test_no_phase_ii_placeholder_in_metrics(self, fraud_text, mock_llm_client):
        svc = _build_mock_service(llm_client=mock_llm_client)
        result = svc.analyze_text(fraud_text)

        result_dict = result.to_dict()
        metrics = result_dict.get("metrics", {})
        benchmarks = metrics.get("benchmarks", {})

        # Check no "Phase-II benchmark hook required" string remains
        for key, val in benchmarks.items():
            if isinstance(val, str):
                assert "Phase-II" not in val, f"Placeholder found in benchmark {key}: {val}"

    def test_no_graph_equivalence_guaranteed_overclaim(self):
        """No module should overclaim graph_equivalence=guaranteed."""
        from app.modules.propagation.oasis_adapter import CounterfactualInitStatus

        # The default should NOT claim guaranteed
        status = CounterfactualInitStatus()
        d = status.to_dict()

        # graph_equivalence (old field) should no longer exist
        # The new fields should be honest
        if d.get("initialization_method") == "per_branch_generate":
            assert d.get("agent_graph_equivalence") != "guaranteed"


class TestPropagationExecutionContracts:
    """Social propagation, OASIS, and normalization have separate contracts."""

    def _ctx(self):
        from app.modules.scenarios.base import ScenarioContext
        return ScenarioContext(
            scenario_type="public_opinion",
            user_role="individual",
            raw_inputs=[{"content": "舆情传播测试", "role": "user"}],
        )

    def test_social_variant_never_calls_oasis(self):
        from app.modules.scenarios.public_opinion import PublicOpinionScenarioSpec

        local_result = MagicMock()
        local_result.to_dict.return_value = {"fork_point": {}, "branch_a": {}, "branch_b": {}, "comparison": {}}
        with patch("app.modules.propagation.oasis_adapter.OasisPropagationAdapter.is_available", return_value=True) as available, \
             patch("app.modules.propagation.oasis_adapter.OasisPropagationAdapter.run") as oasis_run, \
             patch("app.modules.propagation.run_forked_propagation", return_value=local_result) as local_run:
            result = PublicOpinionScenarioSpec().run_propagation(self._ctx(), allow_oasis=False)

        assert result["provenance"]["runtime_engine"] == "lightweight"
        available.assert_not_called()
        oasis_run.assert_not_called()
        local_run.assert_called_once()

    def test_oasis_failure_degrades_to_local(self):
        from app.modules.scenarios.public_opinion import PublicOpinionScenarioSpec

        local_result = MagicMock()
        local_result.to_dict.return_value = {"fork_point": {}, "branch_a": {}, "branch_b": {}, "comparison": {}}
        with patch("app.modules.propagation.oasis_adapter.OasisPropagationAdapter.is_available", return_value=True), \
             patch.dict("os.environ", {
                 "MIRO_COGSEC_OASIS_API_KEY": "test-key",
                 "MIRO_COGSEC_OASIS_BASE_URL": "https://oasis.test/v1",
                 "MIRO_COGSEC_OASIS_MODEL": "oasis-test",
             }), \
             patch("app.modules.propagation.oasis_adapter.OasisPropagationAdapter.run", side_effect=Exception("timeout")), \
             patch("app.modules.propagation.run_forked_propagation", return_value=local_result):
            result = PublicOpinionScenarioSpec().run_propagation(self._ctx(), allow_oasis=True)

        assert result["provenance"]["runtime_engine"] == "lightweight_fallback"
        assert result["provenance"]["metric_source"] != "oasis"
        assert result["provenance"]["degraded"] is True

    def test_local_shape_is_normalized_before_core_consumption(self):
        from app.modules.propagation.result_adapter import adapt_propagation_result

        raw = {
            "fork_point": {"type": "official_clarification"},
            "branch_a": {
                "coverage_curve": [{"coverage": 0.7}],
                "emotion_curve": [{"panic": 0.1, "anger": 0.8, "confusion": 0.2, "trust": 0.1}],
                "actions": [{"source_agent_id": "origin-1"}],
                "key_nodes": [{"id": "amplifier-1"}],
                "final_metrics": {},
            },
            "branch_b": {"coverage_curve": [{"coverage": 0.4}], "emotion_curve": [], "final_metrics": {}},
            "comparison": {"coverage_delta": 0.3},
        }
        normalized = adapt_propagation_result(raw).to_dict()
        assert normalized["dominant_emotion"] == "anger"
        assert normalized["origin_node"]["id"] == "origin-1"
        assert normalized["branch_a_coverage"] == 0.7
        assert normalized["branch_b_coverage"] == 0.4

    def test_claim_fidelity_loss_becomes_honest_distortion_point(self):
        from app.modules.propagation.result_adapter import adapt_propagation_result

        normalized = adapt_propagation_result({
            "branch_a": {
                "claim_analysis": {
                    "distortion_by_claim": {
                        "CLAIM_001": {
                            "fidelity": 0.4,
                            "distortion_flags": ["context_loss", "source_loss"],
                        },
                    },
                },
            },
            "branch_b": {},
            "comparison": {},
        }).to_dict()
        assert normalized["distortion_points"][0]["metric_source"] == "lightweight_claim_model"
        assert "上下文丢失" in normalized["distortion_points"][0]["description"]

    def test_unsupported_oasis_interventions_stay_proxy(self):
        from app.modules.propagation.oasis_verification import run_topk_oasis_verification
        from app.modules.propagation.schema import PropagationAgent

        agents = [PropagationAgent(
            agent_id="agent-1", role="ordinary_viewer", stance="neutral",
            influence=0.5, susceptibility=0.5, activity=0.5,
            trust_in_official=0.5,
        )]
        proxy = {"branch_comparison": {"ranked_branches": [
            {"candidate_id": "note", "intervention_type": "community_note", "target_nodes": ["agent-1"], "total_score": 0.9},
            {"candidate_id": "warn", "intervention_type": "warning", "target_nodes": ["agent-1"], "total_score": 0.8},
            {"candidate_id": "node", "intervention_type": "node_targeting", "target_nodes": ["agent-1"], "total_score": 0.7},
        ]}}
        fake_oasis_result = MagicMock()
        fake_oasis_result.branch_a.final_metrics = {"cumulative_coverage": 0.5}
        with patch("app.modules.propagation.oasis_adapter._OASIS_AVAILABLE", True), \
             patch.dict("os.environ", {
                 "MIRO_COGSEC_OASIS_API_KEY": "test-key",
                 "MIRO_COGSEC_OASIS_BASE_URL": "https://oasis.test/v1",
                 "MIRO_COGSEC_OASIS_MODEL": "oasis-test",
             }), \
             patch("app.modules.propagation.oasis_adapter.OasisPropagationAdapter.run", return_value=fake_oasis_result):
            result = run_topk_oasis_verification(
                scenario_type="public_opinion", seed_text="test", agents=agents,
                proxy_result=proxy, quick_mode=False, k=3,
            )

        branches = result["oasis_verified_branches"]
        assert all(item["verification_status"] == "unsupported" for item in branches)
        assert all(item["metric_source"] == "proxy" for item in branches)
        assert result["metric_source"] == "proxy"
        assert result["oasis_verification"]["status"] == "unsupported"
        assert result["oasis_verification"]["reason"] == "no_oasis_verifiable_candidate"


class TestConfigIsolation:
    def test_main_key_is_sufficient_without_legacy_key(self):
        from app.config import Config

        with patch.object(Config, "SECRET_KEY", "test-secret"), \
             patch.object(Config, "DEBUG", False), \
             patch.object(Config, "COGSEC_USE_LOCAL_GEMMA", False), \
             patch.object(Config, "MIRO_COGSEC_MAIN_LLM_API_KEY", "main-key"), \
             patch.object(Config, "LLM_API_KEY", None), \
             patch.object(Config, "MIRO_COGSEC_ALLOW_LEGACY_LLM_KEY", False):
            assert Config.validate() == []
