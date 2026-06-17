"""Session manager — wraps SessionStore + file parsing + CogSecService.

Orchestrates multi-turn session assembly then delegates to the existing
CogSecService.analyze_text() mainline for the actual analysis.

The canonical data model is now ConversationTurn / CogSecSession from
``app.modules.session``.  Legacy InputFragment / SessionData remain
for backward compatibility with /append and /upload routes.
"""

from __future__ import annotations

import os
import tempfile
from typing import Any, Dict, List, Optional

from ..config import Config
from ..modules.conversational_response import answer_followup_from_state
from ..modules.session import (
    ConversationTurn,
    build_incremental_analysis,
    build_session_text,
    ingest_file,
)
from ..modules.session_store import (
    InputFragment,
    SessionData,
    SessionStore,
    get_session_store,
)
from ..utils.file_parser import FileParser
from ..utils.logger import get_logger

logger = get_logger("mirofish.session")

# Allowed extensions for the legacy append_file path (PDF-aware)
_LEGACY_EXTENSIONS = Config.ALLOWED_EXTENSIONS
# Extensions supported by the new ingest_file pipeline
_SESSION_EXTENSIONS = frozenset({"txt", "md", "markdown", "json", "csv"})


# ---------------------------------------------------------------------------
# adapter: legacy InputFragment -> ConversationTurn
# ---------------------------------------------------------------------------


def fragment_to_turn(fragment: InputFragment, index: int = 1) -> ConversationTurn:
    """Convert a legacy InputFragment into a canonical ConversationTurn.

    If the fragment was created by ``append_turn()`` the original
    role / source / metadata / timestamp / turn_id are preserved.
    Otherwise a reasonable fallback is constructed from ``kind``.
    """
    # Prefer stored canonical fields when present
    role = fragment.role
    source = fragment.source
    meta: Dict[str, Any] = dict(fragment.metadata) if fragment.metadata else {}

    # Fallback for legacy fragments that lack the new fields
    if not meta and fragment.kind == "text" and role == "user" and source == "chat":
        meta["legacy_kind"] = fragment.kind
        if fragment.filename:
            meta["filename"] = fragment.filename
    if fragment.kind == "file" and fragment.filename:
        meta.setdefault("filename", fragment.filename)

    # Build turn preserving original IDs when available
    turn = ConversationTurn.create(
        role=role,
        content=fragment.content,
        source=source,
        metadata=meta or None,
    )
    if fragment.turn_id:
        turn.turn_id = fragment.turn_id
    if fragment.timestamp is not None:
        turn.timestamp = fragment.timestamp
    return turn


# ---------------------------------------------------------------------------
# SessionManager
# ---------------------------------------------------------------------------


class SessionManager:
    """Orchestrates multi-turn sessions and delegates analysis to CogSecService."""

    def __init__(self, store: Optional[SessionStore] = None):
        self._store = store or get_session_store()

    # ------------------------------------------------------------------
    # session CRUD (backward-compatible)
    # ------------------------------------------------------------------

    def create(
        self,
        scenario_type: Optional[str] = None,
        user_role: str = "individual",
    ) -> SessionData:
        return self._store.create(
            scenario_type=scenario_type,
            user_role=user_role,
        )

    def get(self, session_id: str) -> SessionData:
        return self._require_session(session_id)

    def delete(self, session_id: str) -> bool:
        return self._store.delete(session_id)

    def list_sessions(self) -> List[SessionData]:
        return self._store.list_sessions()

    # ------------------------------------------------------------------
    # append text (compatibility — kept for /append route)
    # ------------------------------------------------------------------

    def append_text(self, session_id: str, content: str) -> InputFragment:
        self._require_session(session_id)
        return self._store.append_text(session_id, content)

    # ------------------------------------------------------------------
    # append file (compatibility — kept for /upload route)
    # ------------------------------------------------------------------

    def append_file(
        self,
        session_id: str,
        file_data: bytes,
        original_filename: str,
    ) -> InputFragment:
        self._require_session(session_id)

        suffix = _safe_suffix(original_filename)
        if suffix not in _LEGACY_EXTENSIONS:
            raise ValueError(
                f"不支持的文件格式: .{suffix}，允许: {sorted(_LEGACY_EXTENSIONS)}"
            )

        tmp_path: Optional[str] = None
        try:
            fd, tmp_path = tempfile.mkstemp(suffix=f".{suffix}")
            os.close(fd)
            with open(tmp_path, "wb") as fh:
                fh.write(file_data)

            content = FileParser.extract_text(tmp_path)
        finally:
            if tmp_path is not None and os.path.exists(tmp_path):
                os.unlink(tmp_path)

        return self._store.append_file(
            session_id=session_id,
            content=content,
            filename=original_filename,
            byte_size=len(file_data),
        )

    # ------------------------------------------------------------------
    # add_turn — standard turn endpoint (text + file via ingest_file)
    # ------------------------------------------------------------------

    def add_turn(
        self,
        session_id: str,
        role: str,
        content: str,
        source: str = "chat",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ConversationTurn:
        """Create and append a single ConversationTurn to the session."""
        self._require_session(session_id)
        turn = ConversationTurn.create(
            role=role,
            content=content,
            source=source,
            metadata=metadata,
        )
        self._store.append_turn(session_id, turn)
        return turn

    def add_turns_from_file(
        self,
        session_id: str,
        file_data: bytes,
        original_filename: str,
    ) -> list[ConversationTurn]:
        """Parse *file_data* via ingest_file and append all resulting turns."""
        self._require_session(session_id)
        turns = ingest_file(original_filename, file_data)
        for turn in turns:
            self._store.append_turn(session_id, turn)
        return turns

    # ------------------------------------------------------------------
    # get_turns — canonical view
    # ------------------------------------------------------------------

    def get_turns(self, session_id: str) -> list[ConversationTurn]:
        """Return all fragments as canonical ConversationTurns."""
        session = self._require_session(session_id)
        return [
            fragment_to_turn(f, idx)
            for idx, f in enumerate(session.fragments, start=1)
        ]

    # ------------------------------------------------------------------
    # analyze — merge all fragments, delegate to CogSecService
    # ------------------------------------------------------------------

    def analyze(self, session_id: str, tone: str = "friendly") -> Dict[str, Any]:
        """Merge all session fragments via build_session_text() and run CogSec mainline.

        Returns the same CogSecAnalysisResult.to_dict() payload as
        POST /api/cogsec/analyze, plus top-level ``session`` and
        ``session_summary`` fields.
        """
        from .cogsec_service import CogSecService

        session = self._require_session(session_id)
        turns = self.get_turns(session_id)
        if not turns:
            raise ValueError(f"Session {session_id} has no input turns")

        session_text = build_session_text(turns)
        service = CogSecService()
        result = service.analyze_text(
            scenario_text=session_text,
            scenario_type=session.scenario_type,
            user_role=session.user_role,
            tone=tone,
            conversation_id=session.session_id,
            turn_id=getattr(turns[-1], 'turn_id', None),
        )
        payload = result.to_dict()
        if payload.get("conversation_state"):
            session.state["last_analysis"] = payload["conversation_state"]
        payload["session"] = session.to_dict()
        payload["session_summary"] = {
            "session_id": session.session_id,
            "turn_count": len(turns),
            "scenario_type": session.scenario_type,
            "user_role": session.user_role,
            "tone": tone,
            "state_reused": False,
        }
        return payload

    def answer_followup(self, session_id: str, content: str, tone: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Answer a simple follow-up from the last cached full analysis, if available."""
        session = self._require_session(session_id)
        last_analysis = session.state.get("last_analysis") if isinstance(session.state, dict) else None
        if not isinstance(last_analysis, dict):
            return None
        return answer_followup_from_state(
            state=last_analysis,
            user_message=content,
            tone=tone or last_analysis.get("tone"),
        )

    # ------------------------------------------------------------------
    # internal
    # ------------------------------------------------------------------

    def _require_session(self, session_id: str) -> SessionData:
        session = self._store.get(session_id)
        if session is None:
            raise KeyError(f"Session not found: {session_id}")
        return session


def _safe_suffix(filename: str) -> str:
    _, _, ext = filename.rpartition(".")
    return ext.lower()
