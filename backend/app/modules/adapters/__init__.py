"""Adapters — responsibility-separated output adapters.

- ``user_response_adapter``: Core Result → user-readable response.
- ``frontend_adapter``: Core Result → graph_payload / UI fields.
- ``benchmark_adapter``: Core Result → benchmark prediction (offline / explicit).
"""

from .user_response_adapter import build_user_response
from .frontend_adapter import build_frontend_payload

__all__ = [
    "build_user_response",
    "build_frontend_payload",
]
