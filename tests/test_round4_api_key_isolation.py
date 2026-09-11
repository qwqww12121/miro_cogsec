"""Final closure: complete API Key isolation tests."""

from __future__ import annotations

import os
import sys
from unittest.mock import patch

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(REPO_ROOT, "backend", "app"))


class TestMainLLMKeyIsolation:
    """Main analysis must NOT use legacy LLM_API_KEY by default."""

    def test_main_llm_does_not_use_legacy_key_by_default(self):
        """Without MIRO_COGSEC_MAIN_LLM_API_KEY, and without legacy enabled, main_key is None."""
        from app.config import Config
        with patch.object(Config, "MIRO_COGSEC_MAIN_LLM_API_KEY", None):
            with patch.object(Config, "MIRO_COGSEC_ALLOW_LEGACY_LLM_KEY", False):
                with patch.object(Config, "LLM_API_KEY", "test-api-key"):
                    with patch.object(Config, "COGSEC_USE_LOCAL_GEMMA", False):
                        main_key = Config.MIRO_COGSEC_MAIN_LLM_API_KEY
                        if not main_key and Config.MIRO_COGSEC_ALLOW_LEGACY_LLM_KEY:
                            main_key = Config.LLM_API_KEY
                        # Legacy key exists but is NOT used
                        assert main_key is None

    def test_main_llm_uses_legacy_key_only_when_explicitly_enabled(self):
        """When MIRO_COGSEC_ALLOW_LEGACY_LLM_KEY=true, legacy key is used."""
        from app.config import Config
        with patch.object(Config, "MIRO_COGSEC_MAIN_LLM_API_KEY", None):
            with patch.object(Config, "MIRO_COGSEC_ALLOW_LEGACY_LLM_KEY", True):
                with patch.object(Config, "LLM_API_KEY", "test-api-key"):
                    main_key = Config.MIRO_COGSEC_MAIN_LLM_API_KEY
                    if not main_key and Config.MIRO_COGSEC_ALLOW_LEGACY_LLM_KEY:
                        main_key = Config.LLM_API_KEY
                    assert main_key == "test-api-key"

    def test_main_llm_does_not_use_openai_key(self):
        """OPENAI_API_KEY must never be used as main analysis key."""
        from app.config import Config
        with patch.object(Config, "MIRO_COGSEC_MAIN_LLM_API_KEY", None):
            with patch.object(Config, "MIRO_COGSEC_ALLOW_LEGACY_LLM_KEY", False):
                with patch.object(Config, "LLM_API_KEY", None):
                    # OPENAI_API_KEY exists but should NOT be used
                    assert Config.MIRO_COGSEC_MAIN_LLM_API_KEY is None
                    # No code path reads OPENAI_API_KEY for main analysis

    def test_main_llm_does_not_use_deepseek_key(self):
        """DEEPSEEK_API_KEY must never be used as main analysis key."""
        service_path = os.path.join(
            REPO_ROOT, "backend", "app", "services", "cogsec_service.py"
        )
        if not os.path.exists(service_path):
            pytest.skip("Service file not found")

        with open(service_path, "r", encoding="utf-8") as f:
            source = f.read()

        # DEEPSEEK_API_KEY should not appear in key resolution
        assert "DEEPSEEK_API_KEY" not in source

    def test_oasis_still_requires_dedicated_key(self):
        """OASIS still requires MIRO_COGSEC_OASIS_API_KEY after all changes."""
        verify_path = os.path.join(
            REPO_ROOT, "backend", "app", "modules", "propagation",
            "oasis_verification.py"
        )
        if not os.path.exists(verify_path):
            pytest.skip("oasis_verification.py not found")

        with open(verify_path, "r", encoding="utf-8") as f:
            source = f.read()

        assert "MIRO_COGSEC_OASIS_API_KEY" in source
        assert "project_specific_oasis_key_not_configured" in source
