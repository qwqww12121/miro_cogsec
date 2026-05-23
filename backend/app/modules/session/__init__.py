"""Session module — canonical multi-turn input models, file ingest, and adapters."""

from .schema import CogSecSession, ConversationTurn, normalize_turn_role
from .analysis_adapter import (
    build_incremental_analysis,
    build_raw_inputs_from_turns,
    build_session_text,
)
from .file_ingestor import ingest_file

__all__ = [
    "build_incremental_analysis",
    "build_raw_inputs_from_turns",
    "build_session_text",
    "CogSecSession",
    "ConversationTurn",
    "ingest_file",
    "normalize_turn_role",
]
