"""Canonical session data models — ConversationTurn, CogSecSession.

These are the standard types for multi-turn input assembly.
The legacy InputFragment / SessionData in session_store.py remain
for backward compatibility with /append and /upload routes.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List

# ---------------------------------------------------------------------------
# role normalisation
# ---------------------------------------------------------------------------

VALID_TURN_ROLES = {"user", "counterparty", "system", "file_excerpt"}


def normalize_turn_role(role: str | None) -> tuple[str, dict]:
    """Normalise *role* to one of VALID_TURN_ROLES.

    Returns (normalised_role, metadata_delta).
    Unknown roles are downgraded to "user" with ``original_role`` recorded.
    """
    if not role:
        return "user", {}
    role = str(role).strip()
    if role in VALID_TURN_ROLES:
        return role, {}
    return "user", {"original_role": role}


# ---------------------------------------------------------------------------
# ConversationTurn
# ---------------------------------------------------------------------------


@dataclass
class ConversationTurn:
    """A single turn in a multi-turn CogSec session."""

    turn_id: str
    role: str
    content: str
    timestamp: float
    source: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        role: str,
        content: str,
        source: str = "chat",
        metadata: Dict[str, Any] | None = None,
    ) -> "ConversationTurn":
        normalized_role, role_meta = normalize_turn_role(role)
        merged_metadata: Dict[str, Any] = {}
        merged_metadata.update(role_meta)
        merged_metadata.update(metadata or {})
        return cls(
            turn_id=str(uuid.uuid4()),
            role=normalized_role,
            content=content,
            timestamp=time.time(),
            source=source,
            metadata=merged_metadata,
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# CogSecSession
# ---------------------------------------------------------------------------


@dataclass
class CogSecSession:
    """A multi-turn analysis session composed of ConversationTurns."""

    session_id: str
    user_role: str
    scenario_type: str
    turns: List[ConversationTurn]
    state: Dict[str, Any]
    created_at: float
    updated_at: float

    @classmethod
    def create(
        cls,
        scenario_type: str,
        user_role: str = "individual",
    ) -> "CogSecSession":
        now = time.time()
        return cls(
            session_id=str(uuid.uuid4()),
            user_role=user_role,
            scenario_type=scenario_type,
            turns=[],
            state={},
            created_at=now,
            updated_at=now,
        )

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["turns"] = [turn.to_dict() for turn in self.turns]
        return payload
