# Backend Response Improvement Audit

## Scope

This audit is limited to backend response generation. It does not propose changes to benchmark scoring, gold answers, judge scripts, benchmark data distribution, frontend structure, or the MiroFace / OASIS / CASIS / MiroFish core chain.

## 1. Final API Response Assembly

The final response returned by the CogSec API is assembled in:

- `backend/app/services/cogsec_service.py`
  - `CogSecService.analyze_text()` runs the main backend chain and returns a `CogSecAnalysisResult`.
  - `CogSecAnalysisResult.to_dict()` serializes the dataclass directly with `asdict`.
- `backend/app/api/cogsec.py`
  - `POST /api/cogsec/analyze` returns `{"success": true, "data": result.to_dict()}`.
  - `GET /api/cogsec/report/<report_id>` builds scenario text from a report and returns the same shape.
  - `POST /api/cogsec/session/<session_id>/analyze` calls `SessionManager.analyze()` and returns its payload.

Current user-facing output is therefore mostly the raw engineering payload. There is no dedicated final answer layer that rewrites structured analysis into a natural assistant response.

## 2. benchmark_prediction / cogsec_analysis / adapter_diagnostics

These fields are generated in:

- `backend/app/modules/benchmark_adapter.py`
  - `build_benchmark_payload(...)`
  - `_build_fraud_prediction(...)`
  - `_build_public_opinion_prediction(...)`
  - `_build_event_propagation_prediction(...)`
  - `_build_cogsec_analysis(...)`
  - `_diagnostics(...)`

They are attached near the end of `CogSecService.analyze_text()`:

- `analysis_result.benchmark_prediction`
- `analysis_result.cogsec_analysis`
- `analysis_result.adapter_diagnostics`

These fields are useful for benchmark-compatible structured evaluation, but they are not written as normal ChatGPT-style user answers.

## 3. Scenario Final Text Sources

The current scenario-specific content comes from `benchmark_adapter.py`:

- `fraud_im`
  - risk label, fraud type, assets, fork points, warning, safe action, evidence spans.
- `public_opinion`
  - event summary, narrative threads, emotion signal, uncertainty points, official response gap, best intervention window, expected public action.
- `event_propagation`
  - origin node, amplifier nodes, propagation path, distortion points, containment window, expected containment action.

These are structured fields. The backend currently does not have a separate formatter that turns them into concise, natural, judge-facing prose.

## 4. Existing judge_friendly / user_facing / tone Logic

No existing `judge_friendly`, `tone`, or `assistant_message` response layer was found.

The closest related feature is:

- `backend/app/modules/reporters/...`
- `render_role_report(...)`
- `analysis_result.role_report`

This is a role-oriented report renderer, not a conversational response adapter. It can coexist with the new response layer, but should not be reused as the final judge-facing answer because it still exposes report-like structure.

## 5. Multi-Turn Conversation State

Current multi-turn support is in:

- `backend/app/services/session_manager.py`
- `backend/app/modules/session_store.py`
- `backend/app/modules/session/analysis_adapter.py`

The session layer stores fragments / turns and can build incremental analysis from the latest input. It does not cache the last full `benchmark_prediction`, `cogsec_analysis`, `risk_graph_bundle`, `evidence_trace`, selected branch, or intervention search.

Therefore follow-up questions such as "为什么？", "证据是什么？", "还有别的方案吗？" cannot currently reuse the last full analysis result in a dedicated way.

## 6. Intervention Branch Execution

Intervention branch search is implemented in:

- `backend/app/modules/propagation/intervention_search.py`
- `run_oasis_counterfactual_intervention_search(...)`

Current behavior:

- Generates up to four intervention candidates.
- Runs a baseline propagation simulation.
- Runs each candidate branch through the lightweight local propagation simulator.
- Selects the best branch by coverage, polarization, misinformation, key-node activity, and cost.

Before this change, candidate branches were executed serially in a `for` loop. The branch metrics are explicitly marked as proxy metrics, not full OASIS runtime metrics.

## 7. OASIS / proxy / lightweight Fallback and metric_source

The propagation extension is attached in `CogSecService.analyze_text()` under:

- `scenario_extension["propagation"]`
- `scenario_extension["propagation_intervention_search"]`

The counterfactual intervention search marks provenance in `intervention_search.py`:

- `runtime_engine = "lightweight_counterfactual_proxy"`
- `metric_source = "proxy"`
- `has_oasis_counterfactual_branches = False`
- `has_oasis_baseline_propagation = ...`

This is a good boundary: proxy branch metrics are already labelled and should not be presented as full OASIS results.

## 8. Minimal Backend Change Points

The safest minimal change points are:

- Add a backend response layer that reads existing structured outputs and creates:
  - `assistant_message`
  - `response_plan`
  - `graph_payload`
  - `suggested_followups`
  - `latency_profile`
  - `conversation_state`
- Attach those fields at the end of `CogSecService.analyze_text()` after benchmark adapter and role report generation.
- Add optional `tone` input to API endpoints, defaulting to `friendly`.
- Cache a compact last-analysis state in the session store after full session analysis.
- Answer simple follow-ups from cached state without rerunning the main pipeline.
- Parallelize lightweight proxy candidate branches while preserving metric provenance.

These changes add compatible fields and do not alter benchmark schemas or core simulation semantics.

## 9. Areas To Avoid

Do not modify:

- `benchmark` scoring logic.
- gold answer files.
- closed-model judge scripts.
- benchmark data distribution.
- frontend pages or component structure in this task.
- MiroFace / OASIS / CASIS / MiroFish core chain semantics.
- proxy branch provenance or metric source labels.

Any future frontend changes should consume the new backend fields, but this task should only document those recommendations.
