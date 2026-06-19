# Backend Response Contract

## 1. Purpose

This document explains the backend response fields added for user-facing answers, graph display, follow-up reuse, and latency/provenance reporting.

The key rule is compatibility: existing API fields remain available. New fields are additive and should not break old frontend, benchmark, or debugging consumers.

## 2. Main API Shape

The main analysis endpoint still returns:

```json
{
  "success": true,
  "data": {
    "...existing fields": "...",
    "assistant_message": "...",
    "response_plan": {},
    "graph_payload": {},
    "suggested_followups": [],
    "latency_profile": {},
    "conversation_state": {},
    "tone": "friendly"
  }
}
```

The existing fields such as `benchmark_prediction`, `cogsec_analysis`, `adapter_diagnostics`, `risk_graph_bundle`, `scenario_extension`, `metrics`, and `role_report` are still present.

## 3. Field Ownership

| Field | Owner Layer | Intended Consumer |
|---|---|---|
| `assistant_message` | response adapter | user, frontend, demo, judge-facing display |
| `response_plan` | response planner | backend, frontend details panel, debugging |
| `graph_payload` | response planner | frontend graph view |
| `suggested_followups` | response adapter | frontend chat / quick actions |
| `latency_profile` | response planner | backend diagnostics, frontend status strip |
| `conversation_state` | response planner / session | session follow-up reuse |
| `benchmark_prediction` | benchmark adapter | benchmark scoring / schema-compatible evaluation |
| `cogsec_analysis` | benchmark adapter | structured mechanism output |
| `adapter_diagnostics` | benchmark adapter | developer diagnostics |
| `risk_graph_bundle` | mainline / RAG graph | graph internals and fallback visualization |
| `scenario_extension` | scenario runtime | propagation and intervention search internals |

## 4. `assistant_message`

`assistant_message` is the primary user-facing final answer.

It should:

- be readable without knowing backend internals;
- put the conclusion first;
- include 2-4 key evidence points;
- give concrete actions;
- avoid raw JSON;
- avoid benchmark, adapter, diagnostics, and schema names;
- avoid claiming proxy results are full OASIS results.

Example:

```text
结论：这是一个较高传播风险事件，关键在于早期来源、放大节点和失真点是否被及时纠偏。
关键依据：
- 起点：突发事件的首发帖或早期来源。
- 放大节点：新闻账号扩大初始信息覆盖面；个人账号转发并推动二次传播。
- 失真点：未经证实的身份信息被补充并传播。
建议动作：
- 标注未确认身份信息，要求转发账号更新更正，并将权威更正与原传播链绑定展示。
为什么这样做：
- 传播风险主要来自早期信息被高影响力节点二次包装后继续扩散。
```

Frontend should show this field first.

## 5. `tone`

The backend supports these tones:

| Tone | Target User | Style |
|---|---|---|
| `friendly` | ordinary user | natural, concise, low-jargon |
| `serious` | operator / admin / risk-control user | direct, action-oriented |
| `expert` | teacher / reviewer / research demo | includes mechanism and branch comparison |
| `judge_friendly` | A/B judge or demo comparison | short, answer-like, no engineering field names |

Request example:

```json
{
  "scenario": "首发帖被多个新闻账号转发，随后出现未经证实身份信息...",
  "scenario_type": "event_propagation",
  "tone": "judge_friendly"
}
```

If omitted, `tone` defaults to `friendly`.

## 6. `response_plan`

`response_plan` is a compact intermediate representation used to render `assistant_message`.

Typical fields:

```json
{
  "scenario": "public_opinion",
  "scenario_label": "舆论事件",
  "tone": "friendly",
  "primary_risk": "high",
  "conclusion": "...",
  "evidence": ["...", "..."],
  "recommendations": ["...", "..."],
  "mechanism": ["...", "..."],
  "selected_branch": {},
  "selected_branch_summary": "...",
  "candidate_summaries": [],
  "metric_source": "proxy",
  "sections": ["结论", "为什么", "建议你这样做"]
}
```

Use cases:

- frontend evidence panel;
- intervention branch panel;
- backend debugging;
- response snapshot tests.

Do not use `response_plan` as the main user answer. It is still a structured planning object.

## 7. `graph_payload`

`graph_payload` is a compact graph-facing view.

Typical fields:

```json
{
  "graph_mode": "public_opinion",
  "highlight_nodes": [],
  "highlight_edges": [],
  "active_branch": "branch_004",
  "display_step": "selected_intervention",
  "node_annotations": {},
  "edge_annotations": {},
  "evidence_links": [],
  "nodes": [],
  "edges": []
}
```

Frontend guidance:

- Use `graph_payload` for future graph highlighting.
- Use `highlight_nodes` and `active_branch` to focus the view.
- Use `evidence_links` to connect evidence cards to graph items.
- Fall back to `risk_graph_bundle` if `graph_payload.nodes` is empty.

Do not expose `graph_payload` as text to ordinary users.

## 8. `suggested_followups`

`suggested_followups` is a short list of user-friendly follow-up prompts.

Example:

```json
[
  "为什么这么判断？",
  "证据是什么？",
  "还有别的方案吗？",
  "为什么选这个方案？"
]
```

Frontend can render these as quick action buttons.

If the user clicks one after a session analysis, call:

```text
POST /api/cogsec/session/<session_id>/turn
```

If the backend returns `data.conversational_response`, show that answer directly.

## 9. `latency_profile`

`latency_profile` explains runtime and metric provenance.

Typical fields:

```json
{
  "quick_response_latency_ms": 12.5,
  "full_response_latency_ms": 850.0,
  "branch_execution_latency_ms": 4.3,
  "branch_count": 4,
  "metric_source": "proxy",
  "fallback_reason": "Counterfactual branches currently use local propagation proxy metrics."
}
```

Important contract:

- `metric_source = "proxy"` means lightweight proxy metrics.
- `metric_source = "oasis_runtime"` should only be used for actual OASIS runtime metrics.
- `metric_source = "heuristic"` means rule or heuristic estimate.
- `metric_source = "llm_hypothesis"` means hypothetical LLM-only mechanism.

Never relabel proxy results as OASIS results.

## 10. `conversation_state`

`conversation_state` is used for session follow-up reuse.

Typical fields:

```json
{
  "conversation_id": "sess_xxx",
  "turn_id": "turn_xxx",
  "scenario": "public_opinion",
  "tone": "friendly",
  "last_benchmark_prediction": {},
  "last_cogsec_analysis": {},
  "last_risk_graph_bundle": {},
  "last_evidence_trace": [],
  "last_selected_best_branch": {},
  "last_propagation_intervention_search": {},
  "cached_fields": [],
  "has_cached_analysis": true
}
```

The session manager stores a compact copy after full analysis.

Follow-ups that can reuse state:

| User Follow-Up | Expected Behavior |
|---|---|
| “为什么？” | explain reason from cached evidence and mechanism |
| “证据是什么？” | return 2-4 cached evidence points |
| “还有别的方案吗？” | compare cached intervention candidates |
| “为什么选这个方案？” | explain cached selected branch |

These should not rerun the full pipeline unless no cached state exists.

## 11. Fields That Should Not Be Directly Displayed As Main Answer

Do not use these as the primary user-facing answer:

- `benchmark_prediction`
- `cogsec_analysis`
- `adapter_diagnostics`
- `scenario_extension`
- raw `risk_graph_bundle`
- raw `counterfactual_branches`
- raw `branch_a_log` / `branch_b_log`

They are valuable, but they are structured/internal. Directly showing them makes the system look like an engineering log.

## 12. Backend Integration Notes

Recommended flow in `CogSecService`:

1. Run existing mainline analysis.
2. Build `benchmark_prediction`, `cogsec_analysis`, and `adapter_diagnostics`.
3. Build role report if needed.
4. Build conversational response fields.
5. Return all fields in one compatible payload.

The response layer should be pure adapter logic:

- read existing structured fields;
- select the most useful evidence and actions;
- render tone-specific text;
- preserve metric provenance;
- avoid inventing simulation results.

## 13. API Compatibility Rules

Backend maintainers should preserve these rules:

1. Add fields rather than removing old fields.
2. Keep benchmark fields schema-compatible.
3. Keep `metric_source` explicit.
4. Keep `assistant_message` free of raw JSON and internal adapter names.
5. Keep session follow-up answers marked as cached-state reuse.
6. Do not modify judge or benchmark logic just to consume `assistant_message`.
7. Do not make frontend depend on raw internal objects when compact fields are available.

## 14. Quick Handoff Checklist

Before changing this layer, check:

- Does the change affect `benchmark_prediction` schema?
- Does it change `cogsec_analysis` semantics?
- Does it hide or mislabel `metric_source`?
- Does it make `assistant_message` longer but less useful?
- Does it force frontend changes?
- Does it rerun the full pipeline for simple follow-ups?

If yes, treat the change as higher risk and document the reason.
