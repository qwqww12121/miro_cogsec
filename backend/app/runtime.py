"""CogSec shared runtime — long-lived resources reused across requests.

This module provides a process-level singleton that holds expensive resources
(LLM client, local Gemma model, Chroma client, embedding model, case library)
so they are initialised once and reused, rather than being rebuilt for every
HTTP request.

Usage::

    from app.runtime import get_runtime
    rt = get_runtime()
    svc = rt.build_service()
"""

from __future__ import annotations

import threading
from typing import Any, Dict, Optional

from .config import Config
from .utils.logger import get_logger

logger = get_logger("mirofish.runtime")


class CogSecRuntime:
    """Long-lived runtime that owns shared heavy resources.

    *Not* a per-request service — use :meth:`build_service` to obtain a
    per-request ``CogSecService`` that borrows resources from this runtime.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._reporter_lock = threading.Lock()
        self._llm_client: Any = None
        self._llm_client_initialised = False
        self._local_gemma_client: Any = None
        self._local_gemma_initialised = False
        self._reporter_client: Any = None
        self._reporter_client_initialised = False
        self._threat_rag: Any = None
        self._case_library_loaded = False
        self._chroma_init_count = 0
        self._gemma_init_count = 0
        self._case_ingest_count = 0

    # ------------------------------------------------------------------
    # LLM client (shared across requests)
    # ------------------------------------------------------------------

    def get_llm_client(self) -> Optional[Any]:
        """Return the shared LLM client (LocalGemma or external API).

        The client is created once and cached.  External LLM clients are
        stateless, so sharing is safe.  Local Gemma models are loaded once
        and reused.
        """
        if self._llm_client_initialised:
            return self._llm_client

        with self._lock:
            if self._llm_client_initialised:
                return self._llm_client

            self._llm_client = self._safe_build_llm_client()
            self._llm_client_initialised = True
            return self._llm_client

    def _safe_build_llm_client(self) -> Optional[Any]:
        """Build LLM client — local Gemma or external API."""
        if getattr(Config, "COGSEC_USE_LOCAL_GEMMA", False):
            try:
                from .utils.local_gemma_client import LocalGemmaClient

                client = LocalGemmaClient(
                    model_path=Config.COGSEC_LOCAL_MODEL_PATH,
                    device=Config.COGSEC_LOCAL_GEMMA_DEVICE,
                    torch_dtype=Config.COGSEC_LOCAL_GEMMA_DTYPE,
                    max_new_tokens=Config.COGSEC_LOCAL_GEMMA_MAX_NEW_TOKENS,
                    offload_folder=Config.COGSEC_LOCAL_GEMMA_OFFLOAD_DIR,
                )
                self._gemma_init_count += 1
                self._local_gemma_client = client
                self._local_gemma_initialised = True
                logger.info("Local Gemma client initialised (init count=%d)", self._gemma_init_count)
                return client
            except Exception as exc:
                logger.warning("Local Gemma init failed; trying configured external main LLM: %s", exc)

        # Final: use project-specific main LLM key ONLY.
        # Legacy LLM_API_KEY is only allowed when explicitly enabled.
        main_key = getattr(Config, "MIRO_COGSEC_MAIN_LLM_API_KEY", None)
        if not main_key and getattr(Config, "MIRO_COGSEC_ALLOW_LEGACY_LLM_KEY", False):
            main_key = Config.LLM_API_KEY
        if not main_key:
            return None
        try:
            from .utils.llm_client import LLMClient

            return LLMClient(
                api_key=main_key,
                connect_timeout=Config.MIRO_COGSEC_MAIN_LLM_CONNECT_TIMEOUT_SEC,
                read_timeout=Config.MIRO_COGSEC_MAIN_LLM_READ_TIMEOUT_SEC,
                max_retries=Config.MIRO_COGSEC_MAIN_LLM_RETRIES,
                mode_name="main_llm",
            )
        except Exception as exc:
            logger.warning("LLM client init failed, falling back to heuristic: %s", exc)
            return None

    def get_reporter_client(self) -> Optional[Any]:
        """Return the internal final-answer client without changing the HTTP API."""
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
            if self._reporter_client_initialised:
                return self._reporter_client
            with self._reporter_lock:
                if self._reporter_client_initialised:
                    return self._reporter_client
                if not dedicated_ready:
                    self._reporter_client = None
                else:
                    try:
                        from .utils.llm_client import LLMClient

                        self._reporter_client = LLMClient(
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
                        logger.warning("Remote reporter client init failed; deterministic fallback remains available: %s", exc)
                        self._reporter_client = None
                self._reporter_client_initialised = True
                return self._reporter_client
        if mode not in {"local_model", "trained_policy"}:
            return self._reporter_twin(self.get_llm_client())
        if self._reporter_client_initialised:
            return self._reporter_client

        with self._reporter_lock:
            if self._reporter_client_initialised:
                return self._reporter_client
            model_path = getattr(Config, "MIRO_REPORTER_MODEL_PATH", None)
            adapter_path = getattr(Config, "MIRO_REPORTER_ADAPTER_PATH", None)
            if not model_path or (mode == "trained_policy" and not adapter_path):
                self._reporter_client = None
            else:
                try:
                    from .utils.local_gemma_client import LocalGemmaClient

                    self._reporter_client = LocalGemmaClient(
                        model_path=model_path,
                        adapter_path=adapter_path,
                        device=Config.MIRO_REPORTER_DEVICE,
                        torch_dtype=Config.MIRO_REPORTER_DTYPE,
                        max_new_tokens=Config.MIRO_REPORTER_MAX_NEW_TOKENS,
                        offload_folder=Config.MIRO_REPORTER_OFFLOAD_DIR,
                    )
                except Exception as exc:
                    logger.warning("Reporter client init failed; deterministic reporter remains available: %s", exc)
                    self._reporter_client = None
            self._reporter_client_initialised = True
            return self._reporter_client

    @staticmethod
    def _reporter_twin(main_client: Any) -> Any:
        """Share the main client's credentials but pin the reporter thinking switch.

        MIRO_REPORTER_ENABLE_THINKING defaults to false; reusing the raw main
        client lets the provider default run, which can spend the whole output
        budget on reasoning and return empty content (finish_reason=length).
        Non-LLMClient objects (e.g. LocalGemmaClient) are returned unchanged.
        """
        if main_client is None:
            return None
        try:
            from .utils.llm_client import LLMClient, clone_llm_client_with_thinking
            if isinstance(main_client, LLMClient):
                return clone_llm_client_with_thinking(
                    main_client, enable_thinking=Config.MIRO_REPORTER_ENABLE_THINKING
                )
        except Exception as exc:
            logger.warning("Reporter thinking-twin build failed; sharing main client as-is: %s", exc)
        return main_client

    # ------------------------------------------------------------------
    # ThreatKnowledgeRAG (shared Chroma + embedding + case library)
    # ------------------------------------------------------------------

    def get_threat_rag(self) -> Any:
        """Return a shared ThreatKnowledgeRAG instance.

        Chroma PersistentClient and ONNX embedding model are created once.
        The case library is ingested only on first access.
        """
        if self._threat_rag is not None:
            return self._threat_rag

        with self._lock:
            if self._threat_rag is not None:
                return self._threat_rag

            from .modules.threat_rag import ThreatKnowledgeRAG

            self._threat_rag = ThreatKnowledgeRAG(Config.CHROMA_PATH)
            self._chroma_init_count += 1
            logger.info("ThreatKnowledgeRAG initialised (chroma init count=%d)", self._chroma_init_count)
            return self._threat_rag

    def ensure_case_library(self) -> None:
        """Load and ingest the fraud case library *once*."""
        if self._case_library_loaded:
            return

        with self._lock:
            if self._case_library_loaded:
                return

            rag = self.get_threat_rag()
            try:
                from .modules.threat_rag import FraudCase

                loaded = rag.load_cases_from_file(Config.FRAUD_CASE_DB_PATH)
            except Exception as exc:
                logger.warning(
                    "Failed to load fraud case file (%s: %s), using built-in defaults. Path: %s",
                    type(exc).__name__, exc, Config.FRAUD_CASE_DB_PATH,
                )
                loaded = []

            if loaded:
                self._case_library_loaded = True
                self._case_ingest_count += 1
                logger.info("Loaded %d fraud cases from file (ingest count=%d)", len(loaded), self._case_ingest_count)
                return

            # Fallback to built-in defaults
            fallback = [FraudCase.from_dict(item) for item in _DEFAULT_CASE_LIBRARY]
            rag.ingest_cases(fallback)
            self._case_library_loaded = True
            self._case_ingest_count += 1
            logger.warning(
                "Fraud case file empty or missing; loaded built-in defaults (ingest count=%d). "
                "Expected path: %s", self._case_ingest_count, Config.FRAUD_CASE_DB_PATH,
            )

    # ------------------------------------------------------------------
    # Per-request service factory
    # ------------------------------------------------------------------

    def build_service(self) -> Any:
        """Create a per-request CogSecService that borrows shared resources."""
        from .services.cogsec_service import CogSecService

        return CogSecService(runtime=self)

    # ------------------------------------------------------------------
    # Stats (for testing / diagnostics)
    # ------------------------------------------------------------------

    def stats(self) -> Dict[str, Any]:
        return {
            "gemma_init_count": self._gemma_init_count,
            "chroma_init_count": self._chroma_init_count,
            "case_ingest_count": self._case_ingest_count,
            "llm_client_initialised": self._llm_client_initialised,
            "reporter_client_initialised": self._reporter_client_initialised,
            "case_library_loaded": self._case_library_loaded,
        }


# ------------------------------------------------------------------
# Built-in default case library (moved from CogSecService)
# ------------------------------------------------------------------

_DEFAULT_CASE_LIBRARY = [
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


# ------------------------------------------------------------------
# Process-level singleton
# ------------------------------------------------------------------

_runtime: Optional[CogSecRuntime] = None
_runtime_lock = threading.Lock()


def get_runtime() -> CogSecRuntime:
    """Return the process-level CogSecRuntime singleton."""
    global _runtime
    if _runtime is not None:
        return _runtime
    with _runtime_lock:
        if _runtime is not None:
            return _runtime
        _runtime = CogSecRuntime()
        return _runtime


def reset_runtime() -> None:
    """Reset the runtime singleton (for testing only)."""
    global _runtime
    with _runtime_lock:
        _runtime = None
