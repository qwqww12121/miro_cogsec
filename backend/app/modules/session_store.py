"""In-memory session store for multi-turn CogSec input assembly.

No database, no Redis — a plain dict with basic TTL eviction.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Fragment types
# ---------------------------------------------------------------------------


@dataclass
class InputFragment:
    """A single input unit within a session — text or file content."""

    fragment_id: str
    kind: str  # "text" | "file"
    content: str
    filename: Optional[str] = None
    byte_size: Optional[int] = None
    added_at: float = field(default_factory=time.time)
    role: str = "user"
    source: str = "chat"
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: Optional[float] = None
    turn_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "fragment_id": self.fragment_id,
            "kind": self.kind,
            "content_preview": self.content[:120] + ("..." if len(self.content) > 120 else ""),
            "content_length": len(self.content),
            "added_at": self.added_at,
            "role": self.role,
            "source": self.source,
        }
        if self.filename is not None:
            payload["filename"] = self.filename
        if self.byte_size is not None:
            payload["byte_size"] = self.byte_size
        if self.metadata:
            payload["metadata"] = self.metadata
        return payload


# ---------------------------------------------------------------------------
# Session dataclass
# ---------------------------------------------------------------------------


@dataclass
class SessionData:
    """Holds all fragments for a single analysis session."""

    session_id: str
    scenario_type: Optional[str] = None
    user_role: str = "individual"
    fragments: List[InputFragment] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_access: float = field(default_factory=time.time)

    def touch(self) -> None:
        self.last_access = time.time()

    def to_dict(self, include_content: bool = False) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "session_id": self.session_id,
            "scenario_type": self.scenario_type,
            "user_role": self.user_role,
            "fragment_count": len(self.fragments),
            "fragments": [f.to_dict() for f in self.fragments],
            "created_at": self.created_at,
            "last_access": self.last_access,
        }
        if include_content:
            payload["merged_text"] = self.merge()
        return payload

    def merge(self) -> str:
        """Concatenate all fragments into a single analysis-ready text."""
        parts: List[str] = []
        for i, fragment in enumerate(self.fragments, start=1):
            if fragment.kind == "text":
                parts.append(f"[Turn {i}]\n{fragment.content}")
            elif fragment.kind == "file":
                label = fragment.filename or f"file_{fragment.fragment_id}"
                parts.append(f"[File {i}: {label}]\n{fragment.content}")
            else:
                parts.append(f"[Fragment {i}]\n{fragment.content}")
        return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# In-memory store
# ---------------------------------------------------------------------------

# TTL in seconds — sessions untouched for this long are eligible for eviction
DEFAULT_SESSION_TTL_SEC = 3600  # 1 hour
MAX_FRAGMENTS_PER_SESSION = 50
MAX_FRAGMENT_CONTENT_CHARS = 100_000  # per fragment


class SessionStore:
    """Thread-safe in-memory store for CogSec sessions."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sessions: Dict[str, SessionData] = {}

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def create(
        self,
        scenario_type: Optional[str] = None,
        user_role: str = "individual",
    ) -> SessionData:
        session_id = _new_session_id()
        session = SessionData(
            session_id=session_id,
            scenario_type=scenario_type,
            user_role=user_role,
        )
        with self._lock:
            self._sessions[session_id] = session
        return session

    def get(self, session_id: str) -> Optional[SessionData]:
        self._evict_expired()
        with self._lock:
            session = self._sessions.get(session_id)
        if session is not None:
            session.touch()
        return session

    def append_text(self, session_id: str, content: str) -> InputFragment:
        session = self._require_session(session_id)
        fragment = InputFragment(
            fragment_id=_new_fragment_id(),
            kind="text",
            content=content[:MAX_FRAGMENT_CONTENT_CHARS],
        )
        self._add_fragment(session, fragment)
        return fragment

    def append_turn(self, session_id: str, turn: Any) -> InputFragment:
        """Append a full ConversationTurn, preserving role/source/metadata."""
        session = self._require_session(session_id)
        fragment = InputFragment(
            fragment_id=_new_fragment_id(),
            kind="text" if turn.source == "chat" else "file",
            content=turn.content[:MAX_FRAGMENT_CONTENT_CHARS],
            role=getattr(turn, "role", "user"),
            source=getattr(turn, "source", "chat"),
            metadata=dict(getattr(turn, "metadata", {}) or {}),
            timestamp=getattr(turn, "timestamp", None),
            turn_id=getattr(turn, "turn_id", None),
        )
        self._add_fragment(session, fragment)
        return fragment

    def append_file(
        self,
        session_id: str,
        content: str,
        filename: Optional[str] = None,
        byte_size: Optional[int] = None,
    ) -> InputFragment:
        session = self._require_session(session_id)
        fragment = InputFragment(
            fragment_id=_new_fragment_id(),
            kind="file",
            content=content[:MAX_FRAGMENT_CONTENT_CHARS],
            filename=filename,
            byte_size=byte_size,
        )
        self._add_fragment(session, fragment)
        return fragment

    def delete(self, session_id: str) -> bool:
        self._evict_expired()
        with self._lock:
            return self._sessions.pop(session_id, None) is not None

    def list_sessions(self) -> List[SessionData]:
        self._evict_expired()
        with self._lock:
            return list(self._sessions.values())

    # ------------------------------------------------------------------
    # internal
    # ------------------------------------------------------------------

    def _require_session(self, session_id: str) -> SessionData:
        session = self.get(session_id)
        if session is None:
            raise KeyError(f"Session not found: {session_id}")
        return session

    def _add_fragment(self, session: SessionData, fragment: InputFragment) -> None:
        with self._lock:
            if len(session.fragments) >= MAX_FRAGMENTS_PER_SESSION:
                raise ValueError(
                    f"Session {session.session_id} has reached the maximum of "
                    f"{MAX_FRAGMENTS_PER_SESSION} fragments"
                )
            session.fragments.append(fragment)
            session.touch()

    def _evict_expired(self) -> None:
        now = time.time()
        with self._lock:
            expired = [
                sid
                for sid, s in self._sessions.items()
                if now - s.last_access > DEFAULT_SESSION_TTL_SEC
            ]
            for sid in expired:
                del self._sessions[sid]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _new_session_id() -> str:
    return f"sess_{uuid.uuid4().hex[:16]}"


def _new_fragment_id() -> str:
    return f"frag_{uuid.uuid4().hex[:12]}"


# ---------------------------------------------------------------------------
# module-level singleton
# ---------------------------------------------------------------------------

_default_store: Optional[SessionStore] = None
_store_lock = threading.Lock()


def get_session_store() -> SessionStore:
    global _default_store
    if _default_store is None:
        with _store_lock:
            if _default_store is None:
                _default_store = SessionStore()
    return _default_store
