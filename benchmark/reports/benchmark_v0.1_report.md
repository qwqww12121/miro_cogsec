# Miro-CogSec Benchmark v0.1 Report

本文档汇总 Miro-CogSec benchmark v0.1 的三场景数据、标注质量、baseline 设计和当前完成状态。

## Overview

v0.1 覆盖三个后端场景：

| 场景 | 数据规模 | 当前状态 | 评测重点 |
|---|---:|---|---|
| `fraud_im` | 20 | `gold_reviewed` | 诈骗链路中的 fork point、资产风险、不可逆操作和干预窗口 |
| `public_opinion` | 5 | `gold_reviewed` | 舆情发酵中的叙事线程、情绪放大、不确定点和回应缺口 |
| `event_propagation` | 5 | `gold_reviewed` | 事件传播中的来源节点、放大节点、传播路径、失真点和阻断窗口 |

`fraud_im` 是当前主评测集，已完成人工 gold review。`public_opinion` 与 `event_propagation` 是传播类扩展 seed gold annotations，已经完成结构化标注、人工语义复核与 AQS 检查。

## Data Assets

| 文件 | 样本数 | 状态 |
|---|---:|---|
| `benchmark/data/cogsec_v0.1.jsonl` | 20 | fraud gold |
| `benchmark/data/public_opinion_v0.1.jsonl` | 5 | seed gold |
| `benchmark/data/event_propagation_v0.1.jsonl` | 5 | seed gold |
| `benchmark/data/llm_baseline_input_fraud_im_v0.1.jsonl` | 20 | answer-free LLM input |
| `benchmark/data/llm_baseline_input_public_opinion_v0.1.jsonl` | 5 | answer-free LLM input |
| `benchmark/data/llm_baseline_input_event_propagation_v0.1.jsonl` | 5 | answer-free LLM input |

### Source Distribution

| 场景 | 来源 |
|---|---|
| `fraud_im` | ChiFraud 17, TeleAntiFraud 2, NIST Phish Scale 1 |
| `public_opinion` | PHEME 3, CoAID 1, FakeNewsNet 1 |
| `event_propagation` | PHEME 2, CrisisLexT26 2, FakeNewsNet 1 |

开源/公开数据集主要提供事件、声明、粗标签或传播结构线索。CogSec 专用字段由 benchmark 人工规范化和标注，不是原数据集自带字段。

## Annotation Quality

### fraud_im

Command:

```powershell
py benchmark\cogsec_benchmark.py aqs
```

| Metric | Score |
|---|---:|
| ECR | 1.0 |
| FVS | 1.0 |
| WCS | 1.0 |
| TRS | 1.0 |
| RFS | 1.0 |
| AQI | 1.0 |

### public_opinion

Command:

```powershell
py benchmark\cogsec_benchmark.py scenario-aqs --input benchmark\data\public_opinion_v0.1.jsonl --scenario-type public_opinion --output benchmark\outputs\public_opinion_aqs_v0.1.json
```

| Metric | Score |
|---|---:|
| ECR | 1.0 |
| NCS | 1.0 |
| EAS | 1.0 |
| UGS | 1.0 |
| OGS | 1.0 |
| IAS | 1.0 |
| RFS | 1.0 |
| TRS | 1.0 |
| AQI | 1.0 |

`public_opinion` AQS 当前表示结构化 seed gold annotation 完整；语义复核已完成。

### event_propagation

Command:

```powershell
py benchmark\cogsec_benchmark.py scenario-aqs --input benchmark\data\event_propagation_v0.1.jsonl --scenario-type event_propagation --output benchmark\outputs\event_propagation_aqs_v0.1.json
```

| Metric | Score |
|---|---:|
| ECR | 1.0 |
| OVS | 1.0 |
| ANS | 1.0 |
| PCS | 1.0 |
| DCS | 1.0 |
| CWS | 1.0 |
| RFS | 1.0 |
| TRS | 1.0 |
| AQI | 1.0 |

`event_propagation` AQS 当前表示结构化 seed gold annotation 完整；语义复核已完成。低风险控制样本允许 `distortion_points=[]`。

## Baseline Design

v0.1 使用三层实验设计：

| 层级 | 名称 | 作用 | 当前状态 |
|---|---|---|---|
| Reference | Human Annotation / Expert Review | 人工 gold answer 和专家复核 | 三场景已完成 |
| Baseline | LLM-only Prompting | 不使用 CogSec 模块，直接让 LLM 输出结构化 prediction | prompt 和 answer-free input 已就绪 |
| Method | Miro-CogSec Full Pipeline | 运行后端完整主链与场景扩展输出 | fraud 有 3/20 smoke run；完整运行待补 |

### LLM-only Prompting

| 场景 | Prompt | Input |
|---|---|---|
| `fraud_im` | `benchmark/prompts/llm_baseline_fraud_im.md` | `benchmark/data/llm_baseline_input_fraud_im_v0.1.jsonl` |
| `public_opinion` | `benchmark/prompts/llm_baseline_public_opinion.md` | `benchmark/data/llm_baseline_input_public_opinion_v0.1.jsonl` |
| `event_propagation` | `benchmark/prompts/llm_baseline_event_propagation.md` | `benchmark/data/llm_baseline_input_event_propagation_v0.1.jsonl` |

LLM 输出建议放在：

```text
benchmark/outputs/llm_baseline/fraud_im_llm_baseline_v0.1.jsonl
benchmark/outputs/llm_baseline/public_opinion_llm_baseline_v0.1.jsonl
benchmark/outputs/llm_baseline/event_propagation_llm_baseline_v0.1.jsonl
```

格式验证命令：

```powershell
py benchmark\cogsec_benchmark.py validate-llm-baseline --scenario-type fraud_im --input benchmark\data\llm_baseline_input_fraud_im_v0.1.jsonl --output benchmark\outputs\llm_baseline\fraud_im_llm_baseline_v0.1.jsonl
py benchmark\cogsec_benchmark.py validate-llm-baseline --scenario-type public_opinion --input benchmark\data\llm_baseline_input_public_opinion_v0.1.jsonl --output benchmark\outputs\llm_baseline\public_opinion_llm_baseline_v0.1.jsonl
py benchmark\cogsec_benchmark.py validate-llm-baseline --scenario-type event_propagation --input benchmark\data\llm_baseline_input_event_propagation_v0.1.jsonl --output benchmark\outputs\llm_baseline\event_propagation_llm_baseline_v0.1.jsonl
```

## Runtime Baseline Status

`fraud_im` 当前不提交 API 输出文件。此前本地做过 3 / 20 cases 的 smoke run，只作为开发参考，不作为当前 benchmark artifact。

此前本地 smoke metrics，仅供参考：

| Metric | Value |
|---|---:|
| Runtime success rate | 15.0 |
| FPA | 100.0 |
| ATA | 66.67 |
| CPA | 50.0 |
| IWA | 100.0 |
| RCA | 100.0 |
| EAR | 0.0 |
| RES | 0.7 |

这些指标不能作为完整 runtime baseline 结论，因为只跑了 3 条样本，且输出文件已从当前提交中清理。完整运行建议命令：

```powershell
C:\Users\19579\.conda\envs\miro-cogsec\python.exe scripts\run_cogsec_api_benchmark.py
```

传播类 runtime baseline 尚未运行。由于后端传播类输出目前是 CogSec 主链加 `scenario_extension.propagation`，后续评分应优先读取场景化字段，不应强行套用 fraud fork 指标。

三场景 API smoke runner 已补充，但当前不把 API smoke 结果作为已完成实验结论。原因是本地尚未接入完整模型 API / propagation 所需 key，传播类扩展可能无法稳定产出 `scenario_extension.propagation`。

```powershell
C:\Users\19579\.conda\envs\miro-cogsec\python.exe scripts\run_scenario_api_benchmark.py --scenario all --limit 1 --disable-chroma --no-local-gemma
```

后续接入 API 后，再运行该命令并记录三类场景的 `runtime_success_rate`、`scenario_resolution_accuracy` 和传播类 `propagation_presence_rate`。在 API 未配置前，当前 benchmark 只声明数据层 gold set、AQS 和 baseline 输入已准备好。

## Review Status

| 场景 | Review status |
|---|---|
| `fraud_im` | 20 `gold_reviewed` |
| `public_opinion` | 5 `gold_reviewed` |
| `event_propagation` | 5 `gold_reviewed` |

传播类样本已在 2026-06-08 完成人工复核并升级为 `gold_reviewed`。复核中对 `event-propagation-v0.1-002` 的阻断窗口进行了小修：`containment_window.close_step` 从 4 调整为 3，使窗口在汇总账号放大前关闭。

## Current Deliverables

- 三场景 benchmark 规划：`benchmark/SCENARIO_PLAN.md`
- fraud 主评测报告：`benchmark/reports/fraud_im_benchmark_v0.1.md`
- 三场景总报告：`benchmark/reports/benchmark_v0.1_report.md`
- 三场景数据文件：`benchmark/data/*_v0.1.jsonl`
- 三场景 AQS 输出：`benchmark/outputs/*aqs_v0.1.json`
- 三场景 LLM baseline prompts：`benchmark/prompts/llm_baseline_*.md`
- 三场景 answer-free LLM input：`benchmark/data/llm_baseline_input_*_v0.1.jsonl`
- LLM baseline 输出建议路径：`benchmark/outputs/llm_baseline/*.jsonl`

## Next Steps

1. 收集三场景 LLM-only baseline 输出，并运行 `validate-llm-baseline`。
2. 跑完整 20 条 `fraud_im` Miro-CogSec API baseline。
3. 配置后端传播扩展所需 API key 后，运行 `public_opinion` / `event_propagation` 的完整 API smoke baseline。
4. 与后端同学确认传播类 API 输出字段，设计 `public_opinion` / `event_propagation` 的 RES 脚本。
