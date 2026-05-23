# SESSION INPUT LAYER — Round 3

## Why in-memory sessions

Round 3 introduces multi-turn input assembly without adding database / Redis /
Flask-Session dependencies.  Sessions live in a plain `dict` with 1-hour TTL
eviction (`session_store.py`).  This is a **development-phase** implementation.

## Architecture

```
/api/cogsec/session/*  (Flask routes)
        │
        v
SessionManager  (services/session_manager.py)
   ├── SessionStore               (modules/session_store.py)  — legacy fragment store
   ├── ConversationTurn            (modules/session/schema.py)  — canonical turn model
   ├── CogSecSession              (modules/session/schema.py)  — canonical session model
   ├── build_session_text()       (modules/session/analysis_adapter.py)
   ├── build_incremental_analysis() (modules/session/analysis_adapter.py)
   ├── ingest_file()              (modules/session/file_ingestor.py)
   └── CogSecService.analyze_text() (services/cogsec_service.py)  — existing mainline
```

## API reference

### Standard (new)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/cogsec/session/create` | Create a new session |
| `POST` | `/api/cogsec/session/<id>/turn` | Add a turn (JSON text or multipart file) |
| `GET`  | `/api/cogsec/session/<id>` | Get session details |
| `POST` | `/api/cogsec/session/<id>/analyze` | Merge all turns → CogSecService mainline |
| `DELETE` | `/api/cogsec/session/<id>` | Delete session |
| `GET`  | `/api/cogsec/session/list` | List active sessions |

### Compatibility (legacy)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/cogsec/session/<id>/append` | Append text fragment (alias) |
| `POST` | `/api/cogsec/session/<id>/upload` | Upload file fragment (alias, PDF-aware) |

## ConversationTurn JSON structure

```json
{
  "turn_id": "uuid",
  "role": "user|counterparty|system|file_excerpt",
  "content": "text content",
  "timestamp": 1234567890.0,
  "source": "chat|file:data.csv|file:chat.json",
  "metadata": {}
}
```

Valid roles: `user`, `counterparty`, `system`, `file_excerpt`.
Unknown roles are downgraded to `user` and the original value is stored in `metadata.original_role`.

## File parsing rules

Supported extensions: `.txt` `.md` `.markdown` `.json` `.csv`.
Max file size: 5 MB.

| Type | Rule |
|------|------|
| `txt`/`md`/`markdown` | Split on blank lines → one `file_excerpt` turn per paragraph |
| `json` (list of dicts with `content`) | One turn per item; `role` from item or `file_excerpt` |
| `json` (dict with `messages` list) | One turn per message; `role` from message or `file_excerpt` |
| `json` (other) | Whole JSON pretty-printed as one `file_excerpt` turn |
| `csv` | Requires `content` column; optional `role` column; one turn per row |

## Incremental analysis

`POST /api/cogsec/session/<id>/turn` returns an `incremental_analysis` block
after each turn:

```json
{
  "t0_signal": "low|medium|high",
  "persona_delta": { ... },
  "risk_delta": { "score_change": 0.0, "matched_keywords": [...] },
  "suggested_followup": "..."
}
```

This is **heuristic-only** (keyword matching).  No LLM call is made.

## Current limitations

- Sessions are in-memory → lost on process restart.
- No authentication or user isolation.
- `incremental_analysis` is keyword-based, not model-driven.
- The legacy `/append` and `/upload` routes store `InputFragment` objects;
  the standard `/turn` route stores `ConversationTurn` objects via the
  adapter function `fragment_to_turn()`.
- File parsing for PDF is only available through the legacy `/upload` route
  (which delegates to `FileParser.extract_text()`).

## Future roadmap

1. Replace `SessionStore` dict with Redis / SQLite when persistence is needed.
2. Replace heuristic `build_incremental_analysis()` with an LLM-powered delta
   when the propagation runtime is ready (Phase IV+).
3. Add session export / import for long-running investigations.
