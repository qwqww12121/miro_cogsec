# LOCAL INTEGRATION NOTES — CogSec Backend

> Last verified: 2026-05-23 on Python 3.12.9 / conda `test2`

## 1. Current integration environment

| Item | Value |
|---|---|
| Python | 3.12.9 (conda env `test2`) |
| ChromaDB | 1.5.9 |
| LLM | qwen-plus @ dashscope (`LLM_API_KEY` required) |
| Flask | Development server on `127.0.0.1:5001` |
| Frontend | `127.0.0.1:3000` (not covered here) |

## 2. Chroma configuration — critical

The project uses `load_dotenv(override=True)` in `backend/app/config.py`.  This
means **the `.env` file at the project root always wins** over shell environment
variables.

```
# backend/app/config.py (simplified)
project_root_env = os.path.join(..., '../../.env')
load_dotenv(project_root_env, override=True)   # <-- .env overrides shell
```

If `CHROMA_PATH` in `.env` points to a stale, readonly, or version-mismatched
Chroma directory, **CogSecService will fail at init** with errors like:

- `attempt to write a readonly database`
- `unable to open database file`
- `'RustBindingsAPI' object has no attribute 'bindings'`

### Required setup

1. Ensure `CHROMA_PATH` in `.env` points to a fresh, writable directory.

   ```env
   CHROMA_PATH=D:\mirofish_runtime\chroma_test_312
   CHROMADB_PATH=D:\mirofish_runtime\chroma_test_312
   ```

2. The directory must exist and be writable by the current user.

3. **After changing `CHROMA_PATH`, restart the Python process** — Chroma's
   `PersistentClient` holds internal state that does not survive path switches.

4. Do not commit personal absolute paths to `.env`.  Each developer should
   copy `.env.example` and configure their own local paths.

### Smoke test

```bash
conda activate test2
cd backend
python -c "from app.config import Config; print(Config.CHROMA_PATH)"
# Must print: D:\mirofish_runtime\chroma_test_312
```

## 3. Verified service-level tests

All three canonical scenarios pass end-to-end through `CogSecService.analyze_text()`:

| Scenario | Command check | Result |
|---|---|---|
| `fraud_im` | `bool(d.get('role_report')) and bool(d.get('scenario_metadata'))` | PASS |
| `public_opinion` | `bool((d.get('scenario_extension') or {}).get('propagation')) and bool(d.get('role_report'))` | PASS |
| `event_propagation` | `bool((d.get('scenario_extension') or {}).get('propagation')) and bool(d.get('role_report'))` | PASS |

## 4. Verified API-level tests

Run with `app.test_client()` — no external HTTP server needed:

| Method | Path | Check | Result |
|---|---|---|---|
| `POST` | `/api/cogsec/analyze` (fraud_im) | `profile`, `fork_comparison`, `scenario_metadata`, `role_report` present; `role_report` has no `error` | PASS |
| `POST` | `/api/cogsec/analyze` (public_opinion) | `scenario_extension.propagation` exists; `role_report.markdown` contains `\|` (Markdown table) | PASS |
| `POST` | `/api/cogsec/analyze` (event_propagation) | `scenario_extension.propagation` exists; `role_report.markdown` contains "时间线" | PASS |
| `POST` | `/api/cogsec/session/create` | Returns `session_id` | PASS |
| `POST` | `/api/cogsec/session/<id>/turn` | Returns `turns_added` + `incremental_analysis` | PASS |
| `POST` | `/api/cogsec/session/<id>/analyze` | Returns `session_summary`, `scenario_extension.propagation`, `role_report` | PASS |

## 5. Frontend data fields — reading order

The `POST /api/cogsec/analyze` and `POST /api/cogsec/session/<id>/analyze`
responses share the same top-level `data` structure.  Frontend consumers
should read these fields:

### Always present

| Field | Type | Description |
|---|---|---|
| `data.scenario_metadata` | dict | Canonical scenario, risk dimensions, report sections, `resolved_from`, `user_role` |
| `data.role_report` | dict | Role-specific rendered report: `{role, title, markdown, sections, structured}`. **Must not contain `error` key** in normal operation |
| `data.counterfactual_report` | dict | Fork A/B comparison, recommendations, trigger points, risk breakdown |
| `data.fork_comparison` | dict | Branch trace diffs, reversibility curve, best intervention window |
| `data.metrics` | dict | `t0_latency_ms`, `end_to_end_ms`, `risk_breakdown` (final_risk, trajectory_gap, etc.), `benchmarks` |
| `data.profile` | dict | 18-dim cognitive profile + `overall_vulnerability_score` |

### Conditionally present

| Field | Type | Description |
|---|---|---|
| `data.scenario_extension` | dict or null | `null` for `fraud_im`; contains `propagation` for `public_opinion`/`event_propagation` |
| `data.scenario_extension.propagation` | dict | ForkedPropagationResult: `{fork_point, branch_a, branch_b, comparison}` |
| `data.session_summary` | dict | Only in session-analyze responses: `{session_id, turn_count, scenario_type, user_role}` |

### Propagation sub-fields (when present)

```
data.scenario_extension.propagation
  .fork_point         {intervention_tick, strategy_type}
  .branch_a           PropagationTrace {agents, actions, coverage_curve, emotion_curve, key_nodes, final_metrics}
  .branch_b           PropagationTrace (intervention branch)
  .comparison         {coverage_delta, action_delta, peak_risk_delta, intervention_effective, strategy_type}
```

### Role report sub-fields

```
data.role_report
  .role               "individual" | "official" | "media" | "target_group"
  .title              e.g. "个人风险判断 — 基于 CogSec 分析"
  .markdown           Ready-to-render Markdown string (6 000-3 000 chars)
  .sections           [{heading, content}, ...]
  .structured         Role-specific structured data (varies by role)
```

## 6. Current limitations

| Limitation | Impact | Mitigation |
|---|---|---|
| Propagation is a lightweight tick-based heuristic, not real OASIS | Coverage/emotion curves are formula-based, not LLM-driven | Switch to `OasisPropagationAdapter` when OASIS in-process API is stable |
| Sessions are in-memory (`dict` + 1-hour TTL) | Lost on process restart | Replace `SessionStore` with Redis/SQLite when persistence is needed |
| `public_opinion` / `event_propagation` still reuse the old fraud CogSec base (CognitiveProfileExtractor, ThreatKnowledgeRAG) | Persona profiling and RAG retrieval are fraud-oriented | Scenario-specific profilers and RAG backends planned for Phase II+ |
| `CHROMA_PATH` misconfiguration crashes `CogSecService.__init__()` | All `/api/cogsec/*` endpoints fail | Follow Section 2 setup; the error message will mention `chromadb` or `sqlite` |

## 7. Quick-start checklist for new developers

1. `conda create -n cogsec python=3.12 && conda activate cogsec`
2. `pip install chromadb flask flask-cors python-dotenv openai`
3. `cp .env.example .env` and edit:
   - `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL_NAME`
   - `CHROMA_PATH` → a fresh writable directory
4. `cd backend && python -c "from app.config import Config; print(Config.CHROMA_PATH)"`
5. `python -c "from app.services.cogsec_service import CogSecService; s=CogSecService(); print('OK')"`
6. `python run.py` to start Flask on `127.0.0.1:5001`
