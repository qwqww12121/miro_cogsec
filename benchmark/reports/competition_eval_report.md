# Miro-CogSec Competition Evaluation Report

## 1. Evaluation Goal

This benchmark is designed to support the information-security competition submission. Its purpose is not only to show that Miro-CogSec can run, but to evaluate whether the system provides measurable security value beyond ordinary LLM prompting.

The core question is:

```text
Can Miro-CogSec detect cognitive-security risk earlier, explain the risky branch more clearly, and recommend safer interventions than an LLM-only baseline?
```

The benchmark therefore evaluates four capabilities:

| Capability | What It Tests | Why It Matters |
|---|---|---|
| Scenario recognition | Whether the system routes a case to `fraud_im`, `public_opinion`, or `event_propagation` | Wrong scenario routing makes later analysis unreliable |
| Risk reasoning | Whether risk level, key fork, propagation risk, and uncertainty are identified | Security systems must catch the right failure mode |
| Intervention quality | Whether the system finds an early, actionable intervention window | A useful defense must act before irreversible loss or uncontrolled spread |
| Evidence grounding | Whether conclusions are traceable to input text or runtime traces | Competition evaluation needs explainability, not only final labels |

## 2. Benchmark Structure

v0.1 contains three scenarios:

| Scenario | Size | Current Role | Main Evaluation Target |
|---|---:|---|---|
| `fraud_im` | 20 | Main gold set | Fraud fork point, asset risk, irreversible action, safe intervention |
| `public_opinion` | 5 | Seed gold set | Narrative threads, emotion amplification, uncertainty, official response gap |
| `event_propagation` | 5 | Seed gold set | Origin node, amplifier nodes, propagation path, distortion points, containment window |

All three scenarios have `gold_reviewed` annotations. The propagation scenarios are smaller seed sets, so they are mainly used to validate schema, runtime alignment, and scoring feasibility before scaling.

## 3. Experimental Design

The competition experiment should compare at least two systems on the same gold samples:

```text
Gold samples
  -> LLM-only baseline
  -> score with the same benchmark metrics

Gold samples
  -> Miro-CogSec full pipeline
  -> runtime adapter when needed
  -> score with the same benchmark metrics
```

Recommended experiment layers:

| Layer | System | Purpose |
|---|---|---|
| Reference | Human-reviewed gold answer | Defines the expected answer and evidence |
| Baseline | LLM-only prompting | Measures what a plain model can do without CogSec modules |
| Full system | Miro-CogSec runtime | Measures the project system under the same task |
| Ablation, planned | Miro-CogSec without propagation/RAG/counterfactual branch | Shows which modules contribute value |

## 4. Metrics

The benchmark uses two metric families:

| Metric Family | Meaning | Runtime Dependency |
|---|---|---|
| AQS | Annotation Quality Score: whether the gold labels are complete, grounded, and internally consistent | No |
| RES | Runtime Evaluation Score: whether a model/runtime prediction matches the gold answer | Yes |

For competition reporting, RES should be broken down instead of reported as a single opaque number.

| Dimension | Example Metrics | Interpretation |
|---|---|---|
| Detection | scenario match, risk calibration | Did the system identify the right task and risk level? |
| Reasoning | fork/path/narrative/node accuracy | Did the system explain the correct mechanism? |
| Intervention | intervention-window or containment-window score | Did the system act early enough? |
| Evidence | evidence attribution rate | Did the system ground claims in visible evidence? |
| Stability | runtime success rate, latency, error count | Can the system run reliably in the competition demo environment? |

## 5. Current Results

### 5.1 LLM-only Baseline

DeepSeek LLM-only baseline has already been run. This baseline does not use Miro-CogSec backend modules, RAG, counterfactual simulation, or OASIS propagation.

| Scenario | Samples | RES |
|---|---:|---:|
| `fraud_im` | 20 | 0.789 |
| `public_opinion` | 5 | 0.399 |
| `event_propagation` | 5 | 0.701 |

Interpretation:

- `fraud_im`: LLM-only is strong on obvious fraud risk and evidence terms, but weaker on precise intervention windows.
- `public_opinion`: LLM-only struggles with narrative structure, uncertainty gaps, and intervention timing.
- `event_propagation`: LLM-only can often describe event spread, but does not validate runtime containment behavior.

### 5.2 Miro-CogSec Runtime Smoke

After the latest backend update, the two previously blocked propagation scenarios were rechecked locally on Windows.

| Scenario | Limit | Runtime Success | Scenario Match | Propagation Present | SQLite Lock |
|---|---:|---:|---:|---:|---|
| `public_opinion` | 1 | 100.0 | 100.0 | 100.0 | Not reproduced |
| `event_propagation` | 1 | 100.0 | 100.0 | 100.0 | Not reproduced |

Interpretation:

- The previous Windows SQLite issue around `branch_a.db` was not reproduced in the smoke tests.
- `scenario_extension.propagation` is now present for both propagation scenarios.
- This proves runtime feasibility, but not full semantic quality.

### 5.3 Runtime Adapter Scoring

The backend propagation output is runtime-trace oriented: agents, actions, coverage curves, emotion curves, branch A/B comparison, and key nodes. The benchmark gold answer is semantic-task oriented: narrative threads, uncertainty, official response gap, origin node, amplifier nodes, distortion points, and containment window.

A benchmark-side adapter was added to normalize runtime traces into prediction fields so the existing scorer can produce partial RES without changing backend logic.

Current adapter smoke scores, based on 1/5 samples:

| Scenario | Scored Samples | Complete Schema Rate | RES | Main Strength | Main Gap |
|---|---:|---:|---:|---|---|
| `public_opinion` | 1/5 | 20.0 | 0.270 | Risk calibration and official-response signal | Narrative, uncertainty, evidence semantics |
| `event_propagation` | 1/5 | 20.0 | 0.293 | Risk calibration and containment window | Origin semantics, distortion semantics, evidence attribution |

Important: the complete schema rate is 20.0 because only one of five samples was run, not because the adapter output is missing required fields for that sample.

### 5.4 System Comparison by Layer

RES is a summary score. The competition report should also compare systems by five layers: detection, reasoning, intervention, evidence, and runtime.

| Scenario | System | Detection | Reasoning | Intervention | Evidence | Runtime | RES | Status |
|---|---|---:|---:|---:|---:|---:|---:|---|
| `fraud_im` | DeepSeek LLM-only | TBD | TBD | TBD | TBD | N/A | 0.789 | completed baseline |
| `fraud_im` | Miro-CogSec full | TBD | TBD | TBD | TBD | TBD | TBD | pending full runtime |
| `public_opinion` | DeepSeek LLM-only | TBD | TBD | TBD | TBD | N/A | 0.399 | completed baseline |
| `public_opinion` | Miro-CogSec full | TBD | TBD | TBD | TBD | TBD | TBD | pending 5/5 runtime |
| `event_propagation` | DeepSeek LLM-only | TBD | TBD | TBD | TBD | N/A | 0.701 | completed baseline |
| `event_propagation` | Miro-CogSec full | TBD | TBD | TBD | TBD | TBD | TBD | pending 5/5 runtime |

### 5.5 Ablation Comparison by Layer

The ablation design is part of the benchmark, but official ablation numbers must wait for real backend switches. Do not report fake ablation scores.

| Scenario | System Variant | Detection | Reasoning | Intervention | Evidence | Runtime | RES | Status |
|---|---|---:|---:|---:|---:|---:|---:|---|
| `fraud_im` | Miro-CogSec w/o RAG | TBD | TBD | TBD | TBD | TBD | TBD | pending backend switch |
| `fraud_im` | Miro-CogSec w/o counterfactual | TBD | TBD | TBD | TBD | TBD | TBD | pending backend switch |
| `public_opinion` | Miro-CogSec w/o propagation | TBD | TBD | TBD | TBD | TBD | TBD | pending backend switch |
| `public_opinion` | Miro-CogSec w/o RAG | TBD | TBD | TBD | TBD | TBD | TBD | pending backend switch |
| `event_propagation` | Miro-CogSec w/o propagation | TBD | TBD | TBD | TBD | TBD | TBD | pending backend switch |
| `event_propagation` | Miro-CogSec w/o counterfactual | TBD | TBD | TBD | TBD | TBD | TBD | pending backend switch |

## 6. Current Assessment

The benchmark is now useful for three levels of competition evidence:

1. Data quality: three scenarios have gold-reviewed data and AQS checks.
2. Baseline comparison: LLM-only results are available for all three scenarios.
3. Runtime feasibility: Miro-CogSec propagation runtime now runs on the previously blocked scenarios.

The remaining weakness is semantic alignment:

```text
Backend runtime trace != benchmark semantic prediction
```

The adapter solves the engineering connection, but the current backend output still does not directly produce the full semantic fields expected by `public_opinion` and `event_propagation` gold answers. This is why adapter RES is currently low.

## 7. Competition-Ready Claims

Safe claims:

- Miro-CogSec benchmark covers fraud, public opinion, and event propagation scenarios.
- Gold annotations are structured and human reviewed.
- LLM-only baseline exists for direct comparison.
- Propagation runtime now executes for both propagation scenarios and the previous Windows SQLite lock was not reproduced in smoke tests.
- A benchmark adapter now allows runtime propagation traces to be scored against semantic gold fields.

Claims that still need more evidence:

- Miro-CogSec outperforms LLM-only on all scenarios.
- Propagation intervention improves containment in most cases.
- Runtime semantic output fully matches gold narrative/distortion fields.

## 8. Next Work Before Submission

Priority order:

1. Run Miro-CogSec full runtime for all 20 `fraud_im` cases and compute official runtime RES.
2. Run `public_opinion` and `event_propagation` for all 5 seed cases each, then compute adapter RES.
3. Add a small ablation table if backend switches are available:
   - full system
   - without propagation
   - without RAG
   - without counterfactual branch
4. Improve backend semantic output or adapter rules for:
   - `public_opinion.narrative_threads`
   - `public_opinion.uncertainty_points`
   - `event_propagation.origin_node`
   - `event_propagation.distortion_points`
   - evidence attribution from runtime trace to gold evidence spans
5. Prepare final competition tables:
   - LLM-only vs Miro-CogSec RES
   - smoke/runtime stability
   - error analysis by scenario
   - limitation statement

## 9. Recommended Final Result Table

Use this table once full runtime results are available:

| Scenario | LLM-only RES | Miro-CogSec RES | Delta | Runtime Success | Key Finding |
|---|---:|---:|---:|---:|---|
| `fraud_im` | 0.789 | TBD | TBD | TBD | TBD |
| `public_opinion` | 0.399 | TBD | TBD | TBD | TBD |
| `event_propagation` | 0.701 | TBD | TBD | TBD | TBD |

This table is the core competition story: the same gold tasks, the same scorer, and a transparent comparison between ordinary LLM output and the Miro-CogSec system.
