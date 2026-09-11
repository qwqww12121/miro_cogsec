from __future__ import annotations

import os


def test_pytest_disables_project_dotenv_before_app_imports() -> None:
    assert os.environ.get("MIRO_DISABLE_DOTENV") == "true"


def test_importing_evaluation_scripts_does_not_reenable_live_credentials() -> None:
    os.environ.pop("JUDGE_API_KEY", None)
    os.environ.pop("MIRO_COGSEC_OASIS_API_KEY", None)
    import scripts.run_closed_model_judge  # noqa: F401
    import scripts.run_llm_baseline  # noqa: F401

    assert "JUDGE_API_KEY" not in os.environ
    assert "MIRO_COGSEC_OASIS_API_KEY" not in os.environ
