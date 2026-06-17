# Project Scope And Scenarios

## 1. One-Sentence Positioning

Miro-CogSec is a cognitive-security analysis and intervention-support backend: it turns a user-provided incident, conversation, or传播场景 into structured risk understanding, evidence traces, propagation/intervention analysis, and a user-facing response.

It is not only a fraud detector. Fraud detection is one supported scenario, but the broader goal is to explain cognitive-security risk and recommend safer intervention actions.

## 2. What Problem This Project Solves

The backend is designed to answer four practical questions:

1. What is happening in the input?
2. Why is it risky from a cognitive-security perspective?
3. What evidence or mechanism supports that judgment?
4. What should the user, operator, or public communicator do next?

The system should therefore produce both:

- machine-readable structured fields for graphs, traces, benchmark adapters, and future frontend views;
- human-readable final answers for ordinary users, reviewers, or operators.

## 3. Main Scenario Types

The project currently has three main scenario families.

| Scenario | Core Question | Typical Output |
|---|---|---|
| `fraud_im` | Is this instant-message / dialogue interaction risky or fraudulent? | risk judgment, key evidence, asset targets, fork points, safe action |
| `public_opinion` | How is a public discussion forming and where can misunderstanding escalate? | event summary, narrative threads, emotion signal, uncertainty points, official response gap, public communication action |
| `event_propagation` | How does information move through sources, amplifiers, and distortion points? | origin node, amplifier nodes, propagation path, distortion points, containment window, correction action |

These are scenario types. They describe the domain of the input.

## 4. `fraud_im`

`fraud_im` covers suspicious instant messaging, social engineering, account risk, credential requests, money-transfer pressure, and other dialogue-based risk.

The backend should focus on:

- whether the interaction is risky;
- what kind of fraud or social-engineering pattern it resembles;
- which assets are targeted, such as credentials, identity, funds, devices, or accounts;
- which fork points make the interaction dangerous;
- what the user should do immediately.

Good final answer behavior:

- conclusion first;
- concrete warning;
- 2-4 evidence points;
- direct safe action.

Avoid:

- only outputting a label;
- over-explaining graph internals to ordinary users;
- treating every suspicious phrase as confirmed fraud without evidence.

## 5. `public_opinion`

`public_opinion` covers public discussion, narrative formation,情绪放大, uncertainty, and official-response gaps.

The backend should focus on:

- what the public event is about;
- which narrative threads are forming;
- whether anger, panic, anxiety, or confusion is being amplified;
- what is still uncertain;
- whether official information is missing, delayed, incomplete, or not tied back to the original传播链;
- how to communicate safely.

Good final answer behavior:

- do not rush to moral judgment;
- separate confirmed information from uncertain information;
- explain why a communication window matters;
- recommend concrete clarification or public communication actions.

Avoid:

- turning public-opinion analysis into fraud analysis;
- treating “传播热度” itself as proof of truth or falsehood;
- hiding uncertainty.

## 6. `event_propagation`

`event_propagation` covers the movement of information through origin nodes, amplifier nodes, repost chains, media accounts, community groups, and correction nodes.

The backend should focus on:

- where the information starts;
- who or what amplifies it;
- how the message changes;
- where distortion, context loss, or identity/time/place errors appear;
- when and where containment or correction should happen.

Good final answer behavior:

- identify source and amplifier roles;
- explain the main propagation path;
- name distortion points;
- recommend early correction, labeling, source verification, or high-node update actions.

Avoid:

- dumping raw simulation traces;
- saying proxy branch metrics are full OASIS runtime metrics;
- over-claiming exact propagation outcomes when only lightweight proxy metrics are available.

## 7. Intervention Strategy Positioning

`intervention_strategy` should be treated as an analysis focus or response mode, not as a separate scenario type by default.

Reason:

- `public_opinion` and `event_propagation` are input domains.
- intervention strategy is a decision layer over those domains.
- the same public-opinion event can be answered in normal summary mode or intervention-strategy mode.

Recommended API concept:

```json
{
  "scenario_type": "public_opinion",
  "analysis_focus": "intervention_strategy",
  "tone": "expert"
}
```

If the project later adds a formal `analysis_focus` field, the backend should route like this:

| Field | Meaning |
|---|---|
| `scenario_type` | What kind of case this is |
| `analysis_focus` | What the user wants emphasized |
| `tone` | How the answer should be written |

Current implementation can still expose intervention information through `response_plan.selected_branch`, `response_plan.candidate_summaries`, `graph_payload.active_branch`, and `latency_profile.metric_source`.

## 8. Relationship Between RAG, LLM, Rules, Runtime, And Response Layer

The backend should not be described as “RAG makes the final judgment” or “LLM makes the final judgment”.

More accurate responsibility split:

| Component | Responsibility |
|---|---|
| RAG / case library | retrieves similar cases, risk templates, evidence material |
| LLM / extractor | helps turn raw input into structured profile fields when available |
| rule / adapter logic | normalizes outputs into scenario-specific schemas |
| runtime / simulation | produces branch traces, fork comparison, or propagation proxy metrics |
| response layer | converts structured results into readable user-facing answers |

The final answer is produced by the CogSec pipeline as a whole.

## 9. Scenario Routing Principle

If the caller explicitly passes `scenario_type`, the backend should respect it unless the value is unsupported.

Reason:

- in benchmark, demos, and backend integration, the scenario is often known;
- overriding explicit `public_opinion` or `event_propagation` inputs can accidentally collapse the project back into fraud detection;
- auto-detection is useful only when the caller does not know the scenario.

Recommended behavior:

1. If `scenario_type` is supported, use it as the primary route.
2. If it is missing, use detection.
3. If it is legacy or ambiguous, resolve to a canonical scenario.
4. If detection disagrees with an explicit supported scenario, record the disagreement in diagnostics rather than silently switching the task.

## 10. Current Non-Goals

The current backend handoff should not include:

- benchmark scoring redesign;
- gold answer changes;
- judge script changes;
- frontend page refactor;
- pretending proxy metrics are OASIS runtime metrics;
- project-wide MiroFish / OASIS / CASIS refactor;
- making `fraud_im` the only optimization target.

## 11. Handoff Summary For Backend Maintainers

When receiving this project, treat the backend as a layered system:

1. Scenario input enters `CogSecService`.
2. Mainline modules create profile, graph, risk, branch, propagation, and benchmark-compatible fields.
3. `benchmark_adapter` creates structured task outputs.
4. `conversational_response` creates the human-facing answer.
5. Session state can cache the last full analysis for simple follow-up questions.

The safest improvement path is to strengthen layer 4 and the API contract before changing core runtime logic.
