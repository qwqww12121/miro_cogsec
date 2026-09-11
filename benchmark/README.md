# Miro-CogSec Benchmark v0.1

这个文件夹是 Miro-CogSec 的小样本 benchmark 管线。v0.1 先故意做小：20 条公开来源支撑的样本、一套稳定的 CogSec JSONL schema、第一层模型标注接口、第二层模型复核接口、Miro-CogSec 运行输出、评分脚本，以及给人工审核看的 Markdown 报告。

当前版本不是简单“诈骗/非诈骗”分类库，而是图谱支撑型小样本库。每条样本都应尽量包含：

```text
场景框架
  -> 证据包
  -> 攻击策略链
  -> 认知压力候选
  -> 资产目标
  -> Fork 节点
  -> A/B 反事实预期
  -> 不确定性说明
```

## 设计原则

这个 benchmark 不走手写特征工程路线。公开数据集负责提供真实或公开来源支撑的样本底座；强闭源模型负责把样本转换成 CogSec 图谱支撑答案；第二个模型组合或人工负责审查第一层转换是否可靠。最终冻结下来的 JSONL 才是 v0.1 benchmark。

## 目录结构

- `data/raw_seed_v0.1.jsonl`：清洗、去重、抽样后的公开来源种子样本。
- `data/cogsec_v0.1.jsonl`：第一层模型转换后的 20 条 CogSec 图谱支撑答案。
- `data/review_request_v0.1.jsonl`：给第二层模型审查用的标准输入。
- `data/review_stub_v0.1.jsonl`：空白二审结果模板。
- `prompts/stage1_cogsec_annotator.md`：第一层模型英文接口 prompt，可给 GPT-5.5 或同等级模型使用。
- `prompts/stage1_cogsec_annotator.zh-CN.md`：第一层接口的中文翻译，方便人工理解。
- `prompts/stage2_cogsec_reviewer.md`：第二层模型英文审查 prompt，可给 ClaudeCode + DeepSeek 等组合使用。
- `prompts/stage2_cogsec_reviewer.zh-CN.md`：第二层接口的中文翻译。
- `schemas/*.schema.json`：每个阶段的机器可读 JSON schema。
- `reports/human_review_v0.1.md`：人工审核报告，每条样本分三块：第一层抽取结果、第二层审查意见、人工审核留白。
- `outputs/`：本地运行 Miro-CogSec 后生成的预测结果和评分结果。
- `cogsec_benchmark.py`：统一入口脚本，负责校验、生成二审输入、生成报告、运行 runtime、评分。

## 流程

```text
公开数据集
  -> 清洗 / 去重 / 抽样
  -> 第一层模型：转换成 CogSec 图谱支撑 JSONL
  -> 格式校验
  -> 标注质量评分 (AQS)
  -> 第二层模型：审查 / 复核 / 给出修订建议
  -> 可选人工审核
  -> 固定为 benchmark v0.1
  -> 跑 Miro-CogSec
  -> 评测指标计算 (RES)
```

### 两层评分

- **AQS (Annotation Quality Score)** — 不依赖 runtime，独立评估标注本身的质量。
- **RES (Runtime Evaluation Score)** — 对比 Miro-CogSec 运行时输出与 benchmark 标准答案。

## 常用命令

校验原始样本和第一层标注：

```bash
python benchmark/cogsec_benchmark.py validate
```

标注质量评分（ECR / FVS / WCS / TRS / RFS → AQI），不依赖 runtime：

```bash
python benchmark/cogsec_benchmark.py aqs
```

把轻量第一层标注升级/覆盖为图谱支撑标注：

```bash
python benchmark/cogsec_benchmark.py enrich
```

重新生成第二层审查输入：

```bash
python benchmark/cogsec_benchmark.py make-review-input
```

重新生成人工审核 Markdown 报告：

```bash
python benchmark/cogsec_benchmark.py report
```

在 20 条样本上运行本地 Miro-CogSec：

```bash
python benchmark/cogsec_benchmark.py run
```

对运行输出做全维度评测（FPA / ATA / CPA / IWA / RCA / EAR → RES）：

```bash
python benchmark/cogsec_benchmark.py evaluate
```

（`score` 是 `evaluate` 的别名，保持向后兼容。）

运行不依赖 Miro-CogSec runtime 的完整本地流程（validate + aqs + review-input + report）：

```bash
python benchmark/cogsec_benchmark.py all-local
```

加上 runtime 运行和评测：

```bash
python benchmark/cogsec_benchmark.py all-local --with-runtime
```

## 评测指标

### AQS: Annotation Quality Score（标注质量，不依赖 runtime）

| 指标 | 全称 | 含义 | 目标 |
|------|------|------|------|
| ECR | Evidence Coverage Rate | evidence_pack 中 span 命中原文、ID 格式正确的比例 | > 0.95 |
| FVS | Fork Validity Score | fork_points.type 属于 benchmark schema，且 runtime_alignment 明确标出 direct / nearest / unsupported | 1.00 |
| WCS | Window Consistency Score | 干预窗口关闭在不可逆节点之前的案例比例 | 1.00 |
| TRS | Traceability Score | evidence_refs 指向有效 evidence_pack ID 的比例 | 1.00 |
| RFS | Rich Field Score | 所有 rich fields 已填写且结构完整的比例 | 1.00 |
| AQI | Annotation Quality Index | ECR×0.25 + FVS×0.25 + WCS×0.15 + TRS×0.20 + RFS×0.15 | > 0.90 |

### RES: Runtime Evaluation Score（运行时评测）

| 指标 | 全称 | 含义 | 目标 |
|------|------|------|------|
| FPA | Fork Point Accuracy | runtime 预测的 Fork 二元类别是否与 benchmark 标准答案一致 | > 0.70 |
| ATA | Asset Target Accuracy | 预测的资产目标类型与标准答案的重叠率 | > 0.60 |
| CPA | Counterfactual Path Accuracy | 预测的 trajectory_gap 与标准答案差值 ≤ 0.20 的比例 | > 0.60 |
| IWA | Intervention Window Accuracy | 预测的干预时机是否在标准答案窗口内 | > 0.65 |
| RCA | Risk Calibration Accuracy | 预测的 risk bin 与标准答案一致的比率 | > 0.65 |
| EAR | Evidence Attribution Rate | 预测输出的关键词与标准答案 evidence_keywords 的重叠率 | > 0.65 |
| RES | Runtime Evaluation Score | FPA×0.20 + ATA×0.18 + CPA×0.18 + IWA×0.14 + RCA×0.15 + EAR×0.15 | > 0.65 |

## 评分文件

- `outputs/aqs_v0.1.json`：标注质量评分输出（`aqs` 命令）
- `outputs/run_v0.1.jsonl`：运行时预测输出（`run` 命令）
- `outputs/metrics_v0.1.json`：运行时评测输出（`evaluate` 命令）

## 两个模型接口

第一层标注接口：

- 输入：`data/raw_seed_v0.1.jsonl`
- 英文 prompt：`prompts/stage1_cogsec_annotator.md`
- 中文翻译：`prompts/stage1_cogsec_annotator.zh-CN.md`
- 输出：`data/cogsec_v0.1.jsonl`
- 约定：输入一行，输出一行 CogSec JSON。

第二层审查接口：

- 输入：`data/review_request_v0.1.jsonl`
- 英文 prompt：`prompts/stage2_cogsec_reviewer.md`
- 中文翻译：`prompts/stage2_cogsec_reviewer.zh-CN.md`
- 输出：`data/review_v0.1.jsonl`
- 约定：一条第一层标注对应一条审查 JSON。

## 来源说明

v0.1 的样本来自公开数据或公开分类体系，并针对 GitHub 放置做了规范化处理。样本保留数据集名称、标签、许可证说明和 URL，同时移除了直接联系方式，避免长篇复制原始记录。

主要公开来源：

- ChiFraud: https://github.com/xuemingxxx/ChiFraud
- TeleAntiFraud: https://github.com/JimmyMa99/TeleAntiFraud
- NIST Phish Scale User Guide: https://www.nist.gov/publications/nist-phish-scale-user-guide

注意：CogSec 标签不是原始数据集自带标签，而是第一层模型转换出的 benchmark 标准答案。因此必须保留模型元数据、prompt 版本和二审记录，保证后续可追溯、可复核。
