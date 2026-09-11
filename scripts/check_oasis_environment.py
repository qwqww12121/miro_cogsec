"""Print the OASIS dependency/configuration preflight without printing keys."""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.modules.propagation.oasis_experiment import oasis_environment_status  # noqa: E402


if __name__ == "__main__":
    print(json.dumps(oasis_environment_status(), ensure_ascii=False, indent=2))
