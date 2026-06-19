# Project Limitations And Improvement Notes

## 1. Purpose

This document records issues exposed during recent backend development and project handoff.

It is written for future maintainers who may continue improving Miro-CogSec. The goal is not to rewrite the project immediately, but to make the current limitations visible so that later changes can be targeted instead of accidental.

## 2. Current Project Tension

The project has grown beyond its early fraud-detection origin.

Current intended positioning:

> Miro-CogSec should be a cognitive-security analysis and intervention-support system.

However, parts of the code, data, prompts, examples, and evaluation still make it easy for the project to collapse back into a narrower fraud or phishing detector.

This creates several recurring problems:

- `fraud_im` receives more mature treatment than `public_opinion` and `event_propagation`.
- some outputs still sound like risk labels or engineering reports rather than user-facing analysis;
- intervention strategy exists as a capability, but its product/API positioning is not fully stable;
- propagation and intervention results often rely on lightweight proxy metrics rather than full simulation;
- performance and latency are not yet strong enough for smooth interactive use.

## 3. Problem: Project Scope Is Still Too Narrow In Practice

### Symptom

Even though the code now supports:

- `fraud_im`
- `public_opinion`
- `event_propagation`
- intervention strategy over propagation scenarios

the project still often behaves, reads, or gets evaluated like a fraud-risk system.

### Why This Matters

If the project is judged mainly as a fraud detector, then its strongest research claim becomes smaller:

- less about cognitive-security mechanism;
- less about public communication and propagation intervention;
- more like another risk-classification pipeline.

That makes the project easier to compare unfavorably with a strong LLM-only baseline, because LLM-only can already produce fluent fraud warnings and public-opinion summaries.

### Suggested Improvements

- Keep `fraud_im` as one scenario, but do not let it dominate demos, docs, or evaluation.
- Add more first-class examples for `public_opinion` and `event_propagation`.
- Treat `intervention_strategy` as an analysis focus, not just a byproduct of propagation search.
- Make scenario routing respect explicit `scenario_type` more strongly.
- Add scenario-specific smoke examples that are not fraud-like at all.

## 4. Problem: Scenario Boundary Is Not Obvious Enough

### Symptom

Some concepts are easy to mix up:

- scenario type;
- output tone;
- analysis focus;
- benchmark task;
- frontend display mode.

For example, `intervention_strategy` is not really the same kind of thing as `public_opinion`. It is better understood as a decision layer over public-opinion or event-propagation analysis.

### Suggested Improvements

Introduce a clearer API distinction:

```json
{
  "scenario_type": "public_opinion",
  "analysis_focus": "intervention_strategy",
  "tone": "expert"
}
```

Recommended meanings:

| Field | Meaning |
|---|---|
| `scenario_type` | What domain the input belongs to |
| `analysis_focus` | What the user wants emphasized |
| `tone` | How the backend should write the answer |

This would make the backend easier to extend without inventing new scenario names for every output style.

## 5. Problem: Final Answers Were Historically Too Engineering-Like

### Symptom

Earlier outputs exposed useful internal structures, but they often looked like:

- field dumps;
- template reports;
- risk graph logs;
- branch metric summaries;
- benchmark-compatible schema objects.

This is a problem for ordinary users and for blind LLM judges. A strong LLM-only answer often wins because it is direct, natural, and actionable, even when Miro-CogSec has more internal structure.

### Recent Mitigation

A backend response layer was added:

- `assistant_message`
- `response_plan`
- `graph_payload`
- `suggested_followups`
- `latency_profile`
- `conversation_state`

This layer improves readability without changing benchmark, judge, gold answers, frontend code, or core runtime semantics.

### Remaining Improvements

- Make `friendly` and `judge_friendly` outputs even less technical.
- Keep branch IDs and metric terms mostly out of ordinary-user answers.
- Convert remaining English runtime phrases into natural Chinese.
- Reduce duplicated recommendations when selected branch action overlaps with scenario action.
- Add response snapshot tests for all tones and scenarios.

## 6. Problem: RAG / LLM / Runtime Responsibility Is Easy To Misstate

### Symptom

During discussion, a key question appeared:

> RAG 还是 LLM 做判断？

The answer should not be simplified to either one.

### Correct Responsibility Split

| Layer | Responsibility |
|---|---|
| RAG / case library | retrieves similar cases, threat templates, evidence material |
| LLM / extractor | helps extract cognitive profile and structure raw input when available |
| rules / adapters | normalize scenario-specific fields |
| runtime / simulation | produces fork, branch, propagation, and intervention traces |
| response layer | renders a readable final answer |

The final judgment is a pipeline result, not a single-module decision.

### Suggested Improvements

- Document this split in the README and backend handoff docs.
- Add provenance fields to more outputs.
- In `assistant_message`, avoid implying that one module alone made the judgment.
- In debugging views, show which fields came from RAG, runtime, heuristics, proxy, or LLM.

## 7. Problem: Performance Is Not Yet Interactive Enough

### Symptom

Some benchmark/API runs have multi-second or much longer latency. Full backend runs include:

- profile extraction;
- RAG / graph construction;
- mainline runtime;
- propagation extension;
- intervention branch search;
- role report rendering;
- response rendering.

Even when each part is reasonable alone, the full chain can feel slow.

### Recent Mitigation

The lightweight intervention branches were changed from serial execution to parallel proxy execution, and `latency_profile` now exposes:

- quick response latency;
- full response latency;
- branch execution latency;
- branch count;
- metric source;
- fallback reason.

### Remaining Improvements

- Add a true fast path for user-facing quick response.
- Cache expensive RAG or graph results across turns.
- Cache scenario detection and profile extraction for session follow-ups.
- Avoid rerunning full propagation when the user only asks “why?” or “证据是什么？”.
- Add timeouts per stage, not only end-to-end timeout.
- Record per-stage latency, not just full latency.
- Defer heavy branch comparison until after an initial answer is returned.

## 8. Problem: Proxy Metrics Can Be Misread As Full OASIS Results

### Symptom

Propagation intervention search currently uses lightweight local proxy metrics for candidate branches. This is useful, but easy to overstate.

### Current Good Practice

The backend marks:

- `runtime_engine = "lightweight_counterfactual_proxy"`
- `metric_source = "proxy"`
- `has_oasis_counterfactual_branches = false`

### Risk

If frontend, docs, demos, or reports describe these proxy numbers as full OASIS runtime, the project claim becomes misleading.

### Suggested Improvements

- Keep `metric_source` visible in expert views.
- In friendly views, avoid detailed metric claims from proxy branches.
- Add explicit fallback wording when full OASIS is unavailable.
- Add tests that fail if proxy is relabeled as `oasis_runtime`.

## 9. Problem: Benchmark And Closed-Model Judge Can Measure The Wrong Layer

### Symptom

Existing closed-model judge input generation reads `benchmark_prediction`, not necessarily the new `assistant_message`.

That means a response-layer improvement may not show up in judge results unless the judge input is intentionally constructed to compare final answers.

### Why This Matters

If the judge sees structured schema objects while LLM-only is represented as fluent prose, the comparison is not measuring only model quality. It is also measuring presentation format.

### Suggested Improvements

- Keep benchmark scoring unchanged unless explicitly doing evaluation work.
- If comparing final answer quality, build a separate judge input that compares `assistant_message`.
- Keep that separate from schema scoring.
- Report clearly which layer is being evaluated:
  - structured benchmark prediction;
  - mechanism analysis;
  - final user-facing answer;
  - latency;
  - frontend usability.

## 10. Problem: Data Coverage Is Still Thin For Non-Fraud Scenarios

### Symptom

`public_opinion` and `event_propagation` have fewer and less varied examples than a real deployment would need.

This can make the system brittle:

- similar phrasing works;
- unusual public events may not;
- cross-domain cases may be routed poorly;
- intervention candidates can become repetitive.

### Suggested Improvements

- Add more public-opinion cases with different emotional structures.
- Add event-propagation cases with different origins and amplifier types.
- Include benign or low-risk public discussions.
- Include cases where official correction already exists.
- Include cases where intervention should be minimal to avoid overblocking.
- Avoid using only examples that contain obvious keywords like “未经证实” or “官方”.

## 11. Problem: Intervention Candidate Quality Needs Better Semantics

### Symptom

The current candidate generator can produce useful but somewhat generic interventions:

- official response;
- community note;
- downranking;
- friction prompt;
- source verification;
- content labeling;
- node targeting;
- debunking.

These are reasonable categories, but they may not always match the specific event.

### Suggested Improvements

- Make candidate generation more scenario-aware.
- Add constraints for overblocking and public trust damage.
- Separate “information correction” from “visibility suppression”.
- Add a policy that favors least-invasive intervention when risk is moderate.
- Improve explanation of why one branch is selected over another.

## 12. Problem: Frontend Does Not Yet Match The New Backend Contract

### Symptom

The frontend still primarily shows an engineering workbench:

- profile;
- graph;
- fork timeline;
- risk curves;
- intervention prescriptions.

These are useful for research demos, but not ideal as the first screen for a user or judge.

### Suggested Improvements

See:

- `docs/frontend_improvement_guide_zh.md`
- `docs/backend_response_contract.md`

Priority:

1. Show `assistant_message` first.
2. Add `suggested_followups`.
3. Add `latency_profile.metric_source`.
4. Use `graph_payload` for graph highlighting.
5. Keep raw objects in collapsed debug panels.

## 13. Problem: Tests Cover Schema Better Than Product Experience

### Symptom

Existing tests are good at checking adapters and runtime pieces, but less complete for:

- natural answer quality;
- tone differences;
- no raw engineering fields in `judge_friendly`;
- session follow-up behavior;
- latency/provenance correctness.

### Suggested Improvements

- Add snapshot-style tests for `assistant_message`.
- Test each tone for each scenario.
- Test that `judge_friendly` does not mention benchmark/adapter/diagnostics.
- Test that follow-up answers do not rerun full analysis.
- Test metric source preservation.
- Test fallback behavior when propagation search is missing.

## 14. High-Value TODO List

If someone wants to improve the project without doing a major refactor, start here:

1. Add `analysis_focus` to API requests and route intervention strategy through it.
2. Improve scenario routing so explicit `scenario_type` is respected.
3. Add more non-fraud examples and smoke tests.
4. Improve `assistant_message` naturalness for `public_opinion` and `event_propagation`.
5. Add per-stage latency tracking.
6. Cache session-level expensive results.
7. Keep proxy/OASIS provenance visible and tested.
8. Create a separate final-answer judge input only if evaluation work is explicitly requested.
9. Update frontend to show `assistant_message` first.
10. Add response snapshot tests.

## 15. What Not To Do Casually

Avoid these changes unless there is a clear evaluation plan:

- do not modify gold answers just to improve scores;
- do not change judge scripts as part of ordinary backend work;
- do not hide `metric_source`;
- do not claim proxy metrics are OASIS;
- do not optimize only `fraud_im`;
- do not make every output longer in the hope that it looks more advanced;
- do not rewrite the whole mainline before stabilizing the response contract.

## 16. Bottom Line

The project has a good direction, but its strongest future is not “another fraud classifier”.

The stronger claim is:

> Given a cognitive-security scenario, Miro-CogSec can identify the risk mechanism, connect it to evidence and propagation structure, compare intervention options, and return a usable response while preserving provenance.

Most future work should support that broader claim.
