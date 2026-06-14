# Miro-CogSec Benchmark Scenario Plan v0.1

本文档用于说明 benchmark v0.1 如何覆盖三个后端场景，并把数据构造、评分指标和 baseline 实验组织成一个统一但分场景的评测体系。

## 目标

v0.1 采用“三场景统一框架、场景化 gold answer、分层实验深度”的设计：

| 场景 | 评测重点 | v0.1 数据目标 | v0.1 定位 |
|---|---|---:|---|
| `fraud_im` | 用户是否被推向不可逆高损失操作 | 20 条 gold samples | 主评测集 |
| `public_opinion` | 公众讨论中叙事、情绪和不确定性如何发酵 | 5 条 seed gold samples | 传播认知扩展集 |
| `event_propagation` | 事件素材如何跨节点、跨平台扩散并发生失真 | 5 条 seed gold samples | 传播链路扩展集 |

三类场景都纳入 benchmark v0.1。区别不在于是否“正式”，而在于样本规模、标注成熟度和评分粒度不同：`fraud_im` 已具备较完整的人工 gold set；`public_opinion` 与 `event_propagation` 先建立小规模 seed gold annotations，用于验证传播类 schema、评分口径和后端扩展输出。

## 场景边界

### fraud_im

应用背景：电信诈骗、IM 诈骗、冒充客服、冒充公检法、刷单返利、虚假贷款、投资理财诈骗等。

评测问题：

- 系统是否识别出诈骗或高风险诱导？
- 用户被推向的不可逆操作是什么？
- 关键 fork point 是否早于转账、验证码泄露、屏幕共享、未知 App 下载或社会隔离？
- 系统是否给出明确的安全行动建议？

核心 gold 字段：

```text
is_fraud
fraud_type
risk_level
asset_targets
fork_points
intervention_window
counterfactual_expectation
expected_warning
expected_safe_action
evidence_spans
```

### public_opinion

应用背景：校园事件、公共政策争议、企业负面新闻、网传爆料、谣言和辟谣等公众讨论发酵场景。

评测问题：

- 主要叙事线程是否被正确识别？
- 情绪是否正在被放大？
- 信息不确定点、谣言点或事实缺口在哪里？
- 官方信息是否滞后，澄清是否需要介入？
- 系统建议的是降温、补充事实、澄清、延迟表态还是引导核验？

建议 gold 字段：

```text
scenario_type
event_summary
narrative_threads
emotion_signal
uncertainty_points
official_response_gap
propagation_risk_level
best_intervention_window
expected_intervention_action
expected_safe_public_action
evidence_spans
```

### event_propagation

应用背景：首发帖、截图流传、跨平台传播、关键节点放大、事件溯源、视频或图片引发连锁转发等。

评测问题：

- 首发或早期来源是否可识别？
- 哪些节点对传播起到放大作用？
- 信息在哪些步骤发生失真、断章取义或语境丢失？
- 传播链还有没有可阻断窗口？
- 系统建议的是移除关键节点、补充上下文、发布权威信息还是追溯源头？

建议 gold 字段：

```text
scenario_type
event_summary
origin_node
amplifier_nodes
propagation_path
distortion_points
coverage_risk
containment_window
expected_containment_action
evidence_spans
```

## 数据计划

### 当前状态

| 文件 | 状态 |
|---|---|
| `benchmark/data/cogsec_v0.1.jsonl` | 20 条 `fraud_im` gold samples，已人工确认 |
| `benchmark/data/raw_seed_v0.1.jsonl` | 20 条原始 seed，与 fraud gold 对齐 |
| `benchmark/data/public_opinion_v0.1.jsonl` | 5 条 `public_opinion` seed gold samples，`gold_reviewed` |
| `benchmark/data/event_propagation_v0.1.jsonl` | 5 条 `event_propagation` seed gold samples，`gold_reviewed` |
| `benchmark/outputs/aqs_v0.1.json` | `fraud_im` AQS 输出 |
| `benchmark/outputs/public_opinion_aqs_v0.1.json` | `public_opinion` AQS 输出 |
| `benchmark/outputs/event_propagation_aqs_v0.1.json` | `event_propagation` AQS 输出 |
| `benchmark/prompts/llm_baseline_fraud_im.md` | `fraud_im` LLM-only baseline prompt |
| `benchmark/prompts/llm_baseline_public_opinion.md` | `public_opinion` LLM-only baseline prompt |
| `benchmark/prompts/llm_baseline_event_propagation.md` | `event_propagation` LLM-only baseline prompt |
| `benchmark/data/llm_baseline_input_fraud_im_v0.1.jsonl` | `fraud_im` LLM-only answer-free input |
| `benchmark/data/llm_baseline_input_public_opinion_v0.1.jsonl` | `public_opinion` LLM-only answer-free input |
| `benchmark/data/llm_baseline_input_event_propagation_v0.1.jsonl` | `event_propagation` LLM-only answer-free input |
| `benchmark/outputs/llm_baseline/*.jsonl` | LLM-only baseline 输出建议路径，接入 API / LLM 后本地生成 |

### 待补文件

| 文件 | 数量 | 说明 |
|---|---:|---|
| `benchmark/reports/fraud_im_benchmark_v0.1.md` | 1 | fraud 主评测集报告 |
| `benchmark/reports/benchmark_v0.1_report.md` | 1 | 三场景总报告 |

## 评分设计

评分分两层：

```text
AQS: Annotation Quality Score，评 gold 标注质量，不依赖后端 runtime
RES: Runtime Evaluation Score，评后端输出与 gold answer 的匹配程度
```

### fraud_im

已有 AQS 指标：

| 指标 | 含义 |
|---|---|
| ECR | evidence span 是否可追溯到输入文本 |
| FVS | fork 类型与 runtime alignment 是否有效 |
| WCS | 干预窗口是否早于不可逆节点 |
| TRS | evidence_refs 是否指向有效证据 |
| RFS | rich fields 是否完整 |

已有 RES 指标：

| 指标 | 含义 |
|---|---|
| FPA | fork point accuracy |
| ATA | asset target accuracy |
| CPA | counterfactual path accuracy |
| IWA | intervention window accuracy |
| RCA | risk calibration accuracy |
| EAR | evidence attribution rate |

### public_opinion

建议 AQS：

| 指标 | 含义 |
|---|---|
| ECR | 叙事、情绪、不确定点是否有证据支撑 |
| NCS | Narrative Consistency Score，叙事线程是否清楚且不互相矛盾 |
| EAS | Emotion Amplification Score，情绪放大标注是否合理 |
| UGS | Uncertainty Gap Score，不确定点和事实缺口是否明确 |
| IAS | Intervention Action Score，干预建议是否具体且早于扩散失控 |

建议 RES：

| 指标 | 含义 |
|---|---|
| NTA | narrative thread accuracy |
| EAA | emotion amplification accuracy |
| UPA | uncertainty point accuracy |
| ORA | official response gap accuracy |
| ISA | intervention strategy accuracy |

### event_propagation

建议 AQS：

| 指标 | 含义 |
|---|---|
| ECR | 来源、节点、路径、失真点是否有证据支撑 |
| OVS | Origin Validity Score，首发/早期来源标注是否合理 |
| ANS | Amplifier Node Score，放大节点标注是否合理 |
| PCS | Propagation Chain Score，传播路径是否连贯 |
| DCS | Distortion Consistency Score，失真点是否早于风险升级 |
| CWS | Containment Window Score，阻断窗口是否早于传播失控 |

建议 RES：

| 指标 | 含义 |
|---|---|
| ONA | origin node accuracy |
| ANA | amplifier node accuracy |
| PPA | propagation path accuracy |
| DPA | distortion point accuracy |
| CWA | containment window accuracy |

## Baseline 实验

三场景使用一致的实验结构，但 prompt 和评分字段按场景调整。

| 层级 | 名称 | 作用 |
|---|---|---|
| Reference | Human Annotation / Expert Review | 人工 gold answer 与专家复核，作为评测参考答案 |
| Baseline | LLM-only Prompting | 直接提示大模型完成场景分析，不使用 CogSec 模块 |
| Method | Miro-CogSec Full Pipeline | 跑完整后端主链与场景扩展输出 |

### LLM-only Prompting

每个场景准备一个 baseline prompt：

| 场景 | Prompt 文件 |
|---|---|
| `fraud_im` | `benchmark/prompts/llm_baseline_fraud_im.md` |
| `public_opinion` | `benchmark/prompts/llm_baseline_public_opinion.md` |
| `event_propagation` | `benchmark/prompts/llm_baseline_event_propagation.md` |

对应 answer-free 输入文件：

| 场景 | Input 文件 |
|---|---|
| `fraud_im` | `benchmark/data/llm_baseline_input_fraud_im_v0.1.jsonl` |
| `public_opinion` | `benchmark/data/llm_baseline_input_public_opinion_v0.1.jsonl` |
| `event_propagation` | `benchmark/data/llm_baseline_input_event_propagation_v0.1.jsonl` |

生成命令：

```powershell
py benchmark\cogsec_benchmark.py make-baseline-input --input benchmark\data\cogsec_v0.1.jsonl --scenario-type fraud_im --output benchmark\data\llm_baseline_input_fraud_im_v0.1.jsonl
py benchmark\cogsec_benchmark.py make-baseline-input --input benchmark\data\public_opinion_v0.1.jsonl --scenario-type public_opinion --output benchmark\data\llm_baseline_input_public_opinion_v0.1.jsonl
py benchmark\cogsec_benchmark.py make-baseline-input --input benchmark\data\event_propagation_v0.1.jsonl --scenario-type event_propagation --output benchmark\data\llm_baseline_input_event_propagation_v0.1.jsonl
```

LLM 输出完成后，先运行格式验证：

```powershell
py benchmark\cogsec_benchmark.py validate-llm-baseline --scenario-type fraud_im --input benchmark\data\llm_baseline_input_fraud_im_v0.1.jsonl --output benchmark\outputs\llm_baseline\fraud_im_llm_baseline_v0.1.jsonl
py benchmark\cogsec_benchmark.py validate-llm-baseline --scenario-type public_opinion --input benchmark\data\llm_baseline_input_public_opinion_v0.1.jsonl --output benchmark\outputs\llm_baseline\public_opinion_llm_baseline_v0.1.jsonl
py benchmark\cogsec_benchmark.py validate-llm-baseline --scenario-type event_propagation --input benchmark\data\llm_baseline_input_event_propagation_v0.1.jsonl --output benchmark\outputs\llm_baseline\event_propagation_llm_baseline_v0.1.jsonl
```

### Human / Expert Reference

人工标注不作为一个普通模型 baseline，而是作为 gold reference：

- 确认输入文本已脱敏、来源可追溯；
- 确认标注字段有证据支撑；
- 确认 intervention / containment window 早于高损失或失控节点；
- 对不确定推断写入 uncertainty 或 review notes。

### Miro-CogSec Full Pipeline

当前后端以 `CogSecService.analyze_text()` 为统一入口。三场景均可通过 `scenario_type` 进入对应 canonical 场景：

```text
fraud_im
public_opinion
event_propagation
```

`public_opinion` 和 `event_propagation` 会额外尝试运行 propagation extension，并在结果中写入 `scenario_extension.propagation`。benchmark 评分应优先读取场景化输出；当后端字段尚未完全对齐时，报告中应标注为 alignment gap，而不是把传播类任务强行折算成诈骗 fork。

## v0.1 工作顺序

1. 冻结 `fraud_im` 20 条 gold samples，并保留 AQS=1.0 的质量记录。
2. 跑完整 `fraud_im` API baseline，生成 Miro-CogSec Full Pipeline 结果。
3. 编写 `fraud_im_benchmark_v0.1.md`，说明样本来源、标注原则、AQS、runtime 初步结果和 alignment gap。
4. 复核 `public_opinion_v0.1.jsonl` 5 条 seed gold 的来源、字段和标注口径。
5. 复核 `event_propagation_v0.1.jsonl` 5 条 seed gold 的来源、字段和标注口径。
6. 使用三场景 LLM baseline prompts 收集 LLM-only 输出。
7. 为传播类 seed gold 先实现 AQS 检查；RES 可先以报告化评估为主，后续再脚本化。
8. 汇总到 `benchmark_v0.1_report.md`。

## v0.1 完成标准

| 项目 | 完成标准 |
|---|---|
| fraud data | 20 条 gold，validate 通过，AQS 达到 1.0 |
| fraud runtime | 完整 API baseline 可复跑，有 metrics 输出 |
| public opinion data | 5 条 seed gold annotations，字段完整，已人工复核 |
| event propagation data | 5 条 seed gold annotations，字段完整，已人工复核 |
| scoring | fraud AQS/RES 可脚本化，传播类 AQS 已脚本化，传播类 RES 后续补齐 |
| baseline | LLM-only、Human/Expert reference、Miro-CogSec pipeline 三层实验设计可复用 |
| report | 有三场景总报告，明确当前结果和后续扩展空间 |
