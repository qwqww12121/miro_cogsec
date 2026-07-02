"""
API路由模块
"""

from flask import Blueprint

graph_bp = Blueprint('graph', __name__)
simulation_bp = Blueprint('simulation', __name__)
report_bp = Blueprint('report', __name__)
cogsec_bp = Blueprint('cogsec', __name__)
classify_bp = Blueprint('classify', __name__)

try:
    from . import graph  # noqa: E402, F401
except Exception:
    graph = None

try:
    from . import simulation  # noqa: E402, F401
except Exception:
    simulation = None

try:
    from . import report  # noqa: E402, F401
except Exception:
    report = None

from . import cogsec  # noqa: E402, F401
from . import classify  # noqa: E402, F401
