"""File ingestor — parse uploaded files into ConversationTurn list.

Supported: .txt, .md, .markdown, .json, .csv
Max file size: 5 MB.  No pandas, no external libraries beyond stdlib.
"""

from __future__ import annotations

import csv
import io
import json as _json
from typing import Any, Dict, List

from .schema import ConversationTurn

MAX_FILE_BYTES = 5 * 1024 * 1024  # 5 MB
CHUNK_CHARS = 1200
VALID_EXTENSIONS = frozenset({"txt", "md", "markdown", "json", "csv"})


def ingest_file(filename: str, content: bytes) -> list[ConversationTurn]:
    """Parse *filename* from *content* bytes into one or more ConversationTurns."""
    if len(content) > MAX_FILE_BYTES:
        raise ValueError("file too large")

    ext = _extension(filename).lower()
    if ext not in VALID_EXTENSIONS:
        raise ValueError(f"unsupported file type: {ext}")

    text = _decode(content)

    if ext in ("txt", "md", "markdown"):
        return _parse_text(text, filename, ext)
    if ext == "json":
        return _parse_json(text, filename)
    return _parse_csv(text, filename)


# ---------------------------------------------------------------------------
# decoders
# ---------------------------------------------------------------------------


def _decode(content: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("file decode failed")


def _extension(filename: str) -> str:
    _, _, ext = filename.rpartition(".")
    return ext


# ---------------------------------------------------------------------------
# text / md / markdown
# ---------------------------------------------------------------------------


def _parse_text(text: str, filename: str, file_type: str) -> list[ConversationTurn]:
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    if not paragraphs and text.strip():
        # No blank lines — chunk by char count
        chunks = [text[i : i + CHUNK_CHARS] for i in range(0, len(text), CHUNK_CHARS)]
        paragraphs = chunks

    turns: list[ConversationTurn] = []
    for idx, para in enumerate(paragraphs):
        turns.append(
            ConversationTurn.create(
                role="file_excerpt",
                content=para,
                source=f"file:{filename}",
                metadata={
                    "filename": filename,
                    "file_type": file_type,
                    "chunk_index": idx + 1,
                },
            )
        )
    return turns


# ---------------------------------------------------------------------------
# json
# ---------------------------------------------------------------------------


def _parse_json(text: str, filename: str) -> list[ConversationTurn]:
    data = _json.loads(text)

    if isinstance(data, list):
        turns: list[ConversationTurn] = []
        for idx, item in enumerate(data):
            if isinstance(item, dict) and "content" in item:
                role = item.get("role", "file_excerpt")
                content = item["content"]
                turns.append(
                    ConversationTurn.create(
                        role=str(role),
                        content=str(content),
                        source=f"file:{filename}",
                        metadata={
                            "filename": filename,
                            "file_type": "json",
                            "row_index": idx,
                        },
                    )
                )
        if turns:
            return turns

    if isinstance(data, dict) and "messages" in data:
        messages = data["messages"]
        if isinstance(messages, list):
            turns = []
            for idx, msg in enumerate(messages):
                if isinstance(msg, dict) and "content" in msg:
                    role = msg.get("role", "file_excerpt")
                    turns.append(
                        ConversationTurn.create(
                            role=str(role),
                            content=str(msg["content"]),
                            source=f"file:{filename}",
                            metadata={
                                "filename": filename,
                                "file_type": "json",
                                "row_index": idx,
                            },
                        )
                    )
            if turns:
                return turns

    # fallback: pretty-print the whole JSON as one turn
    return [
        ConversationTurn.create(
            role="file_excerpt",
            content=_json.dumps(data, ensure_ascii=False, indent=2),
            source=f"file:{filename}",
            metadata={"filename": filename, "file_type": "json", "chunk_index": 1},
        )
    ]


# ---------------------------------------------------------------------------
# csv
# ---------------------------------------------------------------------------


def _parse_csv(text: str, filename: str) -> list[ConversationTurn]:
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None or "content" not in reader.fieldnames:
        raise ValueError("csv requires content column")

    turns: list[ConversationTurn] = []
    for idx, row in enumerate(reader):
        role = row.get("role", "file_excerpt") if "role" in (reader.fieldnames or []) else "file_excerpt"
        content = row.get("content", "")
        if not content:
            continue
        turns.append(
            ConversationTurn.create(
                role=str(role),
                content=content,
                source=f"file:{filename}",
                metadata={
                    "filename": filename,
                    "file_type": "csv",
                    "row_index": idx,
                },
            )
        )
    return turns
