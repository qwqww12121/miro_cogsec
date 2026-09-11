"""UserResponseAdapter — converts Core Result to user-readable natural language.

Delegates to the existing conversational_response module but ensures
it reads from ``core_analysis``, not benchmark_prediction.
"""

from __future__ import annotations

from typing import Any, Dict

from ..conversational_response import build_conversational_response


def build_user_response(
    core_result: Dict[str, Any],
    user_message: str = "",
    tone: str = "friendly",
    conversation_id: str | None = None,
    turn_id: str | None = None,
) -> Dict[str, Any]:
    """Build a user-facing response from a Core Result.

    This is a thin wrapper over ``build_conversational_response``
    that ensures the response planner uses ``core_analysis`` fields
    rather than benchmark-specific fields.
    """
    return build_conversational_response(
        result=core_result,
        user_message=user_message,
        tone=tone,
        conversation_id=conversation_id,
        turn_id=turn_id,
    )
