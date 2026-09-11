"""API blueprints with explicit core/legacy route loading."""

from __future__ import annotations

from flask import Blueprint


graph_bp = Blueprint("graph", __name__)
simulation_bp = Blueprint("simulation", __name__)
report_bp = Blueprint("report", __name__)
cogsec_bp = Blueprint("cogsec", __name__)
classify_bp = Blueprint("classify", __name__)

_core_loaded = False
_legacy_loaded = False


def load_core_routes() -> None:
    """Load the maintained CogSec and classification routes."""
    global _core_loaded
    if _core_loaded:
        return
    from . import cogsec, classify  # noqa: F401
    _core_loaded = True


def load_legacy_routes() -> None:
    """Load optional original-MiroFish graph/simulation/report routes."""
    global _legacy_loaded
    if _legacy_loaded:
        return
    from . import graph, simulation, report  # noqa: F401
    _legacy_loaded = True
