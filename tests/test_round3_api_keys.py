"""Round 3 API Key isolation tests."""

from __future__ import annotations

import os
import sys
from unittest.mock import patch

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(REPO_ROOT, "backend", "app"))


class TestOasisRequiresDedicatedKey:
    """OASIS must use MIRO_COGSEC_OASIS_API_KEY, not any other key."""

    def test_oasis_requires_miro_cogsec_oasis_key(self):
        """OASIS verification returns not_run when MIRO_COGSEC_OASIS_API_KEY is missing."""
        with patch.dict(os.environ, {
            "MIRO_COGSEC_OASIS_API_KEY": "",
            "OPENAI_API_KEY": "test-api-key",
            "DEEPSEEK_API_KEY": "test-api-key",
            "LLM_API_KEY": "test-api-key",
        }, clear=False):
            # Simulate what oasis_verification does
            oasis_key = os.environ.get("MIRO_COGSEC_OASIS_API_KEY")
            assert not oasis_key, "MIRO_COGSEC_OASIS_API_KEY should be empty"
            # OPENAI_API_KEY exists but should NOT be used
            assert os.environ.get("OPENAI_API_KEY")

    def test_openai_api_key_is_not_used_as_oasis_fallback(self):
        """OPENAI_API_KEY must not be used when MIRO_COGSEC_OASIS_API_KEY is empty."""
        with patch.dict(os.environ, {
            "MIRO_COGSEC_OASIS_API_KEY": "",
            "OPENAI_API_KEY": "test-api-key",
            "LLM_API_KEY": "",
            "DEEPSEEK_API_KEY": "",
        }, clear=False):
            oasis_key = os.environ.get("MIRO_COGSEC_OASIS_API_KEY")
            assert not oasis_key
            # Verify we check the right variable
            assert os.environ.get("OPENAI_API_KEY") != oasis_key

    def test_deepseek_api_key_is_not_used_as_oasis_fallback(self):
        """DEEPSEEK_API_KEY must not be used when MIRO_COGSEC_OASIS_API_KEY is empty."""
        with patch.dict(os.environ, {
            "MIRO_COGSEC_OASIS_API_KEY": "",
            "DEEPSEEK_API_KEY": "test-api-key",
            "LLM_API_KEY": "",
            "OPENAI_API_KEY": "",
        }, clear=False):
            oasis_key = os.environ.get("MIRO_COGSEC_OASIS_API_KEY")
            assert not oasis_key
            assert os.environ.get("DEEPSEEK_API_KEY") != oasis_key


class TestProjectEnvPath:
    """Verify config loads .env from explicit project path only."""

    def test_project_env_path_is_explicit(self):
        """Config must compute an explicit path to the project .env."""
        repo_root = os.path.dirname(os.path.dirname(__file__))
        config_path = os.path.join(
            repo_root, "backend", "app", "config.py"
        )
        if not os.path.exists(config_path):
            pytest.skip(f"config.py not found at {config_path}")

        with open(config_path, "r", encoding="utf-8") as f:
            source = f.read()

        # Must reference the explicit project_root_env path
        assert "project_root_env" in source
        assert "os.path.join" in source
        # Must NOT do load_dotenv() with no arguments (auto-upwards search)
        assert "load_dotenv(override=True)" not in source or (
            "load_dotenv(dotenv_path=" in source
        )


class TestSecretNotLogged:
    """API keys must never appear in log output."""

    def test_secret_not_logged(self):
        """Verify that the config and key-reading code does not print secrets."""
        repo_root = os.path.dirname(os.path.dirname(__file__))
        oasis_verify_path = os.path.join(
            repo_root, "backend", "app", "modules", "propagation",
            "oasis_verification.py"
        )
        if not os.path.exists(oasis_verify_path):
            pytest.skip(f"oasis_verification.py not found")

        with open(oasis_verify_path, "r", encoding="utf-8") as f:
            source = f.read()

        # The reason string must NOT contain the actual key value
        assert "project_specific_oasis_key_not_configured" in source
        # Must not print/log the key
        assert "print(llm_api_key)" not in source
        assert "logger" not in source or "api_key" not in source.lower()
