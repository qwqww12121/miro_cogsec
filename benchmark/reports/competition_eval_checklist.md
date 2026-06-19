# Competition Benchmark Checklist

Use this checklist to decide whether the benchmark is ready for the information-security competition submission.

## Must Have

- [x] Three benchmark scenarios are defined: `fraud_im`, `public_opinion`, `event_propagation`.
- [x] `fraud_im` has 20 gold-reviewed samples.
- [x] `public_opinion` has 5 seed gold-reviewed samples.
- [x] `event_propagation` has 5 seed gold-reviewed samples.
- [x] AQS is available for gold annotation quality.
- [x] LLM-only baseline is available for all three scenarios.
- [x] Propagation runtime smoke passes for `public_opinion --limit 1`.
- [x] Propagation runtime smoke passes for `event_propagation --limit 1`.
- [x] Runtime adapter exists for propagation output scoring.
- [x] Benchmark design defines layered metrics: detection, reasoning, intervention, evidence, runtime.
- [x] Scenario scorer outputs `layer_scores` without replacing RES.
- [x] Scenario API runner records `system_variant` and `disabled_modules`.
- [ ] Full `fraud_im` runtime RES is available for 20/20 cases.
- [ ] Full `public_opinion` runtime adapter RES is available for 5/5 cases.
- [ ] Full `event_propagation` runtime adapter RES is available for 5/5 cases.

## Strongly Recommended

- [ ] Add an ablation result for at least one module, such as without propagation or without RAG.
- [ ] Add an error analysis table explaining where Miro-CogSec fails.
- [ ] Add a final LLM-only vs Miro-CogSec comparison table.
- [ ] Add a short limitation statement for the 5-sample seed propagation sets.
- [ ] Confirm all commands are reproducible from a clean branch.

## Competition Story

The final report should support this claim structure:

```text
Miro-CogSec is not just a chatbot.
It combines scenario routing, cognitive-risk reasoning, counterfactual branching,
and propagation simulation.
The benchmark compares this full pipeline against ordinary LLM-only output
on the same gold samples and the same scoring rules.
```

## Current Honest Status

Safe to say:

- The benchmark framework is in place.
- LLM-only baseline has been completed.
- Propagation runtime now runs for the two previously blocked scenarios.
- Runtime traces can now be adapted into benchmark prediction fields.

Not yet safe to say:

- Miro-CogSec fully outperforms LLM-only across all scenarios.
- Propagation semantics are fully aligned with the gold fields.
- Ablation proves which backend module contributes the largest gain.
