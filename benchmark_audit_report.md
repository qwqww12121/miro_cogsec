# Benchmark Audit Report: Answer RES and OASIS Grounding

Date: 2026-06-16

## Executive Conclusion

当前 `benchmark/cogsec_benchmark.py` 里的 Answer RES 适合评估“模型是否按 benchmark prediction schema 输出了接近 gold answer 的字段”，但它不是一个 simulation-grounded evaluation。它几乎完全围绕字段完整性、字段值匹配、自然语言相似度和证据 span 对齐展开，没有显式使用 OASIS runtime、传播分支、counterfactual branch 或干预效果指标。

因此，DeepSeek LLM-only 直接按 schema 作答时天然适配 Answer RES；Miro-CogSec/OASIS 即使真实跑出了传播分支和干预差异，只要最终 adapter 输出的自然语言字段与 gold answer 表述不够接近，Answer RES 也不会额外奖励其机制型能力。

## Scoring Logic Inventory

### Shared Helpers

| Helper | Logic | Implication |
|---|---|---|
| `_sequence_similarity` | 先规范化为字符串；一方包含另一方则 1.0；否则使用 `SequenceMatcher.ratio()` | 偏向自然语言表述相似，不理解仿真机制 |
| `_text_collection_similarity` | 对 gold 文本集合中每一项，找 prediction 文本集合的最高字符串相似度后平均 | gold 的措辞会强影响得分 |
| `_risk_score_match` | low/medium/high bin 相同得 1.0，相邻得 0.5，否则 0 | 是离散风险桶匹配，不看传播轨迹 |
| `_evidence_span_score` | gold evidence span 与 prediction span 做文本相似，并检查 prediction span 是否出现在原文 | 是证据文本 grounding，不是 runtime grounding |
| `_numeric_window_score` | 数值窗口重叠得 1.0，边界相差 1 得 0.5 | 只看窗口字段，不看仿真分支中的最佳时机 |
| `_stage_window_score` | open_stage / close_stage / label 的字符串相似度平均 | 仍是字段文本对齐 |

### fraud_im

| Metric | Weight | Scoring Type | Uses Gold Natural Language | Uses Runtime/OASIS |
|---|---:|---|---|---|
| FPA | 0.20 | fork 是否属于 `no_fork_needed` 二分类 | No | No |
| ATA | 0.16 | asset target type 集合覆盖 | No | No |
| RCA | 0.16 | risk bin 匹配 | No | No |
| IWA | 0.14 | intervention start/end turn 数值窗口 | No | No |
| EAR | 0.18 | evidence span 文本相似 + 原文包含 | Yes | No |
| ASA | 0.10 | expected safe action 字符串相似 | Yes | No |
| WSA | 0.06 | expected warning 字符串相似 | Yes | No |

Fraud 的 FPA 不是完整 fork type 精确匹配，而是把 `no_fork_needed` 和所有“需要干预”的 fork 进行二分类。它对模型是否产生了完整机制链、反事实路径、传播或 OASIS 分支没有直接奖励。

### public_opinion

| Metric | Weight | Scoring Type | Uses Gold Natural Language | Uses Runtime/OASIS |
|---|---:|---|---|---|
| NSS | 0.16 | narrative claim/risk 文本集合相似 | Yes | No |
| EAS | 0.12 | dominant emotion 和 amplification level 精确匹配 | Partly | No |
| UGS | 0.14 | uncertainty description 文本集合相似 | Yes | No |
| OGS | 0.12 | official response status 精确匹配 + description 相似 | Yes | No |
| RCA | 0.12 | propagation risk bin 匹配 | No | No |
| IWA | 0.10 | intervention window stage/label 文本相似 | Yes | No |
| IAS | 0.10 | intervention action 字符串相似 | Yes | No |
| SPS | 0.06 | safe public action 字符串相似 | Yes | No |
| EAR | 0.08 | evidence span 文本相似 + 原文包含 | Yes | No |

Public opinion 是当前最能暴露问题的场景：真实 OASIS smoke 已经有 `engine=oasis`、Branch A/B `oasis_driven=true`、coverage 从 0.917 降到 0.500，coverage reduction 为 0.417，但 Answer RES 只读最终 prediction 字段，不读这些 runtime 指标。

### event_propagation

| Metric | Weight | Scoring Type | Uses Gold Natural Language | Uses Runtime/OASIS |
|---|---:|---|---|---|
| OVS | 0.14 | origin node type 精确匹配 + description 相似 | Yes | No |
| ANS | 0.14 | amplifier node type/description 文本集合相似 | Yes | No |
| PCS | 0.16 | propagation path node/action/risk_state 文本集合相似 | Yes | No |
| DCS | 0.12 | distortion description 文本集合相似 | Yes | No |
| RCA | 0.12 | coverage risk bin 匹配 | No | No |
| CWS | 0.12 | containment open/close step 数值窗口 | No | No |
| CAS | 0.10 | containment action 字符串相似 | Yes | No |
| EAR | 0.10 | evidence span 文本相似 + 原文包含 | Yes | No |

Event propagation 虽然有传播路径字段，但评分仍然是“预测文本与 gold 文本相似”，不是“仿真分支是否真的改变传播覆盖率、极化程度、误传扩散或关键节点活跃度”。

## What Answer RES Does Not Use

当前 `compute_prediction_scores` 只从每条输出里读取：

- `benchmark_prediction`，如果不存在则读取 `prediction`
- gold `answer`
- gold/input `text`

它没有读取：

- `scenario_extension.propagation.runtime.engine`
- `scenario_extension.propagation.branch_a`
- `scenario_extension.propagation.branch_b`
- `scenario_extension.propagation.comparison.coverage_reduction`
- `scenario_extension.propagation.comparison.intervention_effectiveness`
- `scenario_extension.propagation.branch_*.final_metrics.oasis_driven`
- `scenario_extension.propagation_intervention_search.counterfactual_branches`
- `scenario_extension.propagation_intervention_search.selected_best_branch`
- `cogsec_analysis.risk_graph`
- `cogsec_analysis.counterfactual_analysis`
- `cogsec_analysis.propagation_analysis`
- `cogsec_analysis.provenance`

这解释了为什么 lightweight 和 DeepSeek/OASIS 在同一条 public_opinion smoke 上 Answer RES 都是 0.777：Answer RES 对真实 OASIS grounding 不敏感。

## Current Result Interpretation

已观察到的关键结果：

| Run | Scenario | Runtime | OASIS Grounding | Answer RES | Mechanism Signal |
|---|---|---|---:|---:|---|
| Lightweight adapter | public_opinion smoke | lightweight/proxy | 0 | 0.777 | 有 proxy counterfactual search |
| DeepSeek + OASIS | public_opinion smoke | oasis | 100 | 0.777 | Branch A coverage 0.917, Branch B coverage 0.500 |

这不是说 DeepSeek/OASIS 没有带来机制效果，而是说明 Answer RES 没有把该效果计入分数。它只评估最后回答字段是否和 gold answer 表述接近。

## Speed Audit

DeepSeek/OASIS public smoke 慢的主要原因不是单点 bug，而是 full OASIS 调用结构本身较重：

- quick mode 仍然使用约 12 个 agents 和 5 个 ticks。
- 当前 A/B 两条 OASIS branch 是顺序执行，不是并行执行。
- 每个 tick 会为多个 agent 触发 `LLMAction()`。
- 粗略调用规模是 12 agents x 5 ticks x 2 branches，大约 120 次外部模型决策。
- OASIS 环境启动、日志输出、post/action trace 记录也会增加额外开销。

因此 public_opinion DeepSeek/OASIS smoke 的 126 秒级延迟是符合当前执行结构的。若把每个 candidate 都直接 full OASIS 跑一遍，benchmark 会进一步变慢。

## Recommendation

不建议直接废掉 Answer RES。更稳妥的做法是把它定位为 answer-schema alignment score，同时新增或单独报告 simulation-grounded 指标，用于证明 Miro-CogSec/OASIS 的机制型能力。

推荐的报告结构：

| Layer | Purpose |
|---|---|
| Answer RES | 字段对齐、gold answer 对齐、证据 span 对齐 |
| Mechanistic Traceability | risk graph、counterfactual analysis、provenance、evidence trace 是否完整 |
| Simulation-Grounded Evaluation | runtime engine、OASIS branch grounding、coverage reduction、intervention effectiveness、counterfactual branch comparison、selected best branch 是否由仿真支撑 |

推荐实验策略：

1. 全量 benchmark 默认使用 lightweight/proxy counterfactual search，保证速度。
2. 对代表性样本抽样运行 full OASIS，作为 simulation-grounded validation。
3. 在报告中并列表达：LLM-only 更适配 schema answering；Miro-CogSec/OASIS 的优势应体现在机制结构、传播分支和干预效果上。

## Bottom Line

当前低分不能直接说明 Miro-CogSec/OASIS 没有机制优势；它主要说明 Answer RES 评价的是“回答字段像不像 gold answer”。如果作品目标是认知安全中的传播干预与闭环控制，最终展示不应只押注 Answer RES，而应同时展示 OASIS branch 差异、counterfactual intervention search 和 selected branch 的机制证据链。
