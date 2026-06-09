# Miro-CogSec Benchmark v0.1

本目录用于维护 Miro-CogSec 的小规模 benchmark。v0.1 覆盖三个后端场景：

| 场景 | 样本数 | 当前定位 |
|---|---:|---|
| `fraud_im` | 20 | 主评测集 |
| `public_opinion` | 5 | seed benchmark，用于验证舆情场景 schema、baseline 和后端输出对齐 |
| `event_propagation` | 5 | seed benchmark，用于验证事件传播场景 schema、baseline 和后端输出对齐 |

`public_opinion` 和 `event_propagation` 当前不是最终大规模评测集，主要用于先把字段、评分和实验流程跑通。

## 当前结论

### 数据层

三类 gold 数据和 AQS 已经准备好：

- `fraud_im`：20 条 `gold_reviewed`，AQS = 1.0
- `public_opinion`：5 条 `gold_reviewed`，AQS = 1.0
- `event_propagation`：5 条 `gold_reviewed`，AQS = 1.0

### LLM-only baseline

已使用 DeepSeek 通过 OpenAI-compatible API 跑完三类 LLM-only baseline。该 baseline 不使用 Miro-CogSec 后端模块、RAG、传播仿真或 runtime 输出，只测试普通 LLM 直接生成结构化 prediction 的能力。

| 场景 | 样本数 | 格式通过率 | schema 完整率 | RES |
|---|---:|---:|---:|---:|
| `fraud_im` | 20 | 100.0 | 100.0 | 0.789 |
| `public_opinion` | 5 | 100.0 | 100.0 | 0.399 |
| `event_propagation` | 5 | 100.0 | 100.0 | 0.701 |

主要观察：

| 场景 | 表现较好 | 表现较弱 |
|---|---|---|
| `fraud_im` | FPA=100.0，RCA=97.5，EAR=92.8，ATA=90.8 | IWA=65.0 |
| `public_opinion` | RCA=80.0，EAS=80.0，EAR=70.1 | IWA=4.2，UGS=21.2，NSS=23.5，OGS=35.5 |
| `event_propagation` | RCA=100.0，CWS=100.0，OVS=89.9，EAR=84.8，ANS=81.7 | CAS=20.0，PCS=28.7 |

baseline 输出文件位于：

```text
benchmark/outputs/llm_baseline/
```

这些文件是本地生成物，默认不作为稳定 benchmark 数据提交；稳定结论以本 README 和报告中的汇总分数为准。

## 当前问题

### 1. 传播类 runtime 暂时不能算正式 RES

DeepSeek API 已接通，两个传播类场景也能正确路由：

- `public_opinion`：`scenario_match=100.0`
- `event_propagation`：`scenario_match=100.0`

但 `public_opinion` 和 `event_propagation` 的 runtime 输出目前仍偏诈骗主链字段，例如：

```text
predicted_fork_type
risk_bin
trajectory_gap
evidence_text
```

它们还没有稳定输出 benchmark 需要的场景化字段，例如：

```text
public_opinion:
narrative_threads
emotion_signal
uncertainty_points
official_response_gap

event_propagation:
origin_node
amplifier_nodes
propagation_path
distortion_points
containment_window
```

因此，传播类 runtime 还需要后端输出字段对齐，或者 benchmark 侧 adapter 从后端原始输出中抽取这些字段。

### 2. OASIS 传播扩展在本地 Windows 上失败

当前本地 smoke test 中，传播扩展 `scenario_extension.propagation` 没有稳定产出，报错为：

```text
[WinError 32] 另一个程序正在使用此文件，进程无法访问 branch_a.db
```

这看起来是 OASIS 临时 SQLite 数据库文件锁问题。该问题属于后端传播仿真集成问题，不是 benchmark 数据或 DeepSeek key 的问题。

### 3. ablation 需要后端提供正式开关

传播类场景最重要的消融实验是：

```text
Miro-CogSec without propagation
vs
Miro-CogSec with propagation
```

但当前后端还没有正式、稳定的 benchmark 开关，例如：

```text
enable_propagation=false
enable_propagation=true
```

现在本地出现的 `propagation=False` 是 OASIS 报错导致的结果，不能作为正式 ablation。后续建议后端至少提供 `enable_propagation=false/true`，之后再考虑：

```text
enable_cognitive_profile=false/true
enable_fork_ab=false/true
```

## 建议实验顺序

1. **AQS**：先证明 gold 标注完整、可追溯。
2. **LLM-only baseline**：已完成，用 DeepSeek 直接输出 prediction，对比 gold answer。
3. **Miro-CogSec fraud runtime**：优先跑完整 `fraud_im` runtime baseline。
4. **传播类字段对齐**：等后端稳定输出 `scenario_extension.propagation` 或场景化字段后，再写 adapter。
5. **传播类 runtime RES**：字段对齐后，再跑 `public_opinion` 和 `event_propagation` 的正式 runtime 评分。
6. **Ablation**：等后端提供开关后，比较 with/without propagation。

详细字段对齐计划见：

```text
benchmark/reports/runtime_alignment_todo.md
```

## 关键文件

| 文件 | 说明 |
|---|---|
| `benchmark/data/cogsec_v0.1.jsonl` | `fraud_im` 20 条 gold samples |
| `benchmark/data/public_opinion_v0.1.jsonl` | `public_opinion` 5 条 seed gold samples |
| `benchmark/data/event_propagation_v0.1.jsonl` | `event_propagation` 5 条 seed gold samples |
| `benchmark/data/llm_baseline_input_fraud_im_v0.1.jsonl` | `fraud_im` LLM-only answer-free input |
| `benchmark/data/llm_baseline_input_public_opinion_v0.1.jsonl` | `public_opinion` LLM-only answer-free input |
| `benchmark/data/llm_baseline_input_event_propagation_v0.1.jsonl` | `event_propagation` LLM-only answer-free input |
| `benchmark/prompts/llm_baseline_fraud_im.md` | `fraud_im` LLM-only prompt |
| `benchmark/prompts/llm_baseline_public_opinion.md` | `public_opinion` LLM-only prompt |
| `benchmark/prompts/llm_baseline_event_propagation.md` | `event_propagation` LLM-only prompt |
| `benchmark/reports/benchmark_v0.1_report.md` | 三场景 benchmark 汇总报告 |
| `benchmark/reports/fraud_im_benchmark_v0.1.md` | `fraud_im` 主评测报告 |
| `benchmark/reports/runtime_alignment_todo.md` | 后端输出字段对齐计划 |
| `benchmark/cogsec_benchmark.py` | 校验、AQS、baseline 评分、runtime 评分入口 |
| `scripts/run_llm_baseline.py` | LLM-only baseline runner |
| `scripts/run_scenario_api_benchmark.py` | 三场景后端 API smoke runner |

## 常用命令

### 数据校验

```powershell
py benchmark\cogsec_benchmark.py validate
```

### fraud_im AQS

```powershell
py benchmark\cogsec_benchmark.py aqs
```

### 传播类 AQS

```powershell
py benchmark\cogsec_benchmark.py scenario-aqs --input benchmark\data\public_opinion_v0.1.jsonl --scenario-type public_opinion --output benchmark\outputs\public_opinion_aqs_v0.1.json
py benchmark\cogsec_benchmark.py scenario-aqs --input benchmark\data\event_propagation_v0.1.jsonl --scenario-type event_propagation --output benchmark\outputs\event_propagation_aqs_v0.1.json
```

### 跑 LLM-only baseline

需要先配置 OpenAI-compatible 环境变量，例如 DeepSeek：

```powershell
$env:LLM_API_KEY="你的 key"
$env:LLM_BASE_URL="https://api.deepseek.com"
$env:LLM_MODEL_NAME="deepseek-chat"
```

运行 baseline：

```powershell
C:\Users\19579\.conda\envs\miro-cogsec\python.exe scripts\run_llm_baseline.py --scenario fraud_im --retries 5 --retry-sleep 3
C:\Users\19579\.conda\envs\miro-cogsec\python.exe scripts\run_llm_baseline.py --scenario public_opinion --retries 5 --retry-sleep 3
C:\Users\19579\.conda\envs\miro-cogsec\python.exe scripts\run_llm_baseline.py --scenario event_propagation --retries 5 --retry-sleep 3
```

### 验证 LLM-only baseline 输出

```powershell
py benchmark\cogsec_benchmark.py validate-llm-baseline --scenario-type fraud_im --input benchmark\data\llm_baseline_input_fraud_im_v0.1.jsonl --output benchmark\outputs\llm_baseline\fraud_im_llm_baseline_v0.1.jsonl
py benchmark\cogsec_benchmark.py validate-llm-baseline --scenario-type public_opinion --input benchmark\data\llm_baseline_input_public_opinion_v0.1.jsonl --output benchmark\outputs\llm_baseline\public_opinion_llm_baseline_v0.1.jsonl
py benchmark\cogsec_benchmark.py validate-llm-baseline --scenario-type event_propagation --input benchmark\data\llm_baseline_input_event_propagation_v0.1.jsonl --output benchmark\outputs\llm_baseline\event_propagation_llm_baseline_v0.1.jsonl
```

### 评分 LLM-only baseline

```powershell
py benchmark\cogsec_benchmark.py score-llm-baseline --scenario-type fraud_im --annotated benchmark\data\cogsec_v0.1.jsonl --predictions benchmark\outputs\llm_baseline\fraud_im_llm_baseline_v0.1.jsonl --output benchmark\outputs\llm_baseline\fraud_im_llm_baseline_metrics_v0.1.json
py benchmark\cogsec_benchmark.py score-llm-baseline --scenario-type public_opinion --annotated benchmark\data\public_opinion_v0.1.jsonl --predictions benchmark\outputs\llm_baseline\public_opinion_llm_baseline_v0.1.jsonl --output benchmark\outputs\llm_baseline\public_opinion_llm_baseline_metrics_v0.1.json
py benchmark\cogsec_benchmark.py score-llm-baseline --scenario-type event_propagation --annotated benchmark\data\event_propagation_v0.1.jsonl --predictions benchmark\outputs\llm_baseline\event_propagation_llm_baseline_v0.1.jsonl --output benchmark\outputs\llm_baseline\event_propagation_llm_baseline_metrics_v0.1.json
```

### 三场景后端 smoke test

```powershell
C:\Users\19579\.conda\envs\miro-cogsec\python.exe scripts\run_scenario_api_benchmark.py --scenario public_opinion --limit 1 --disable-chroma --no-local-gemma
C:\Users\19579\.conda\envs\miro-cogsec\python.exe scripts\run_scenario_api_benchmark.py --scenario event_propagation --limit 1 --disable-chroma --no-local-gemma
```

当前该 smoke test 可以验证场景路由，但传播类正式 runtime 评分仍受 OASIS 和字段对齐问题阻塞。

## 数据来源

v0.1 样本来自公开数据集或公开分类体系，并经过规范化处理，不直接复制长篇原始记录。

| 场景 | 来源 |
|---|---|
| `fraud_im` | ChiFraud 17，TeleAntiFraud 2，NIST Phish Scale 1 |
| `public_opinion` | PHEME 3，CoAID 1，FakeNewsNet 1 |
| `event_propagation` | PHEME 2，CrisisLexT26 2，FakeNewsNet 1 |

CogSec 专用标签不是原始数据集自带字段，而是 benchmark 人工规范化和复核后的 gold answer。
