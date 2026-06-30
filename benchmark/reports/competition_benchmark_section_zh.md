# 第三章 Benchmark 测试与评估

## 3.1 测试环境与评估指标

### 3.1.1 测试环境

本项目围绕认知安全场景构建了 Miro-CogSec Benchmark，用于评估系统在欺诈识别、舆情风险研判和事件传播分析中的实际任务解决能力。所有实验均在本地 Windows 环境下完成，使用同一批 benchmark 样本、同一套评分程序和同一套输出 schema 对 Miro-CogSec 与普通 LLM-only baseline 进行对比。

测试环境如下：

| 项目 | 配置 |
|---|---|
| 操作系统 | Windows |
| Python 环境 | `miro-cogsec` Conda 环境 |
| Benchmark 分支 | `cjy-v2` |
| 后端版本 | 已合入 `origin/jzh` 最新后端输出与前端适配文档 |
| Benchmark 数据版本 | `cogsec_v0.1` |
| 主评测脚本 | `scripts/run_scenario_api_benchmark.py` |
| LLM-only 脚本 | `scripts/run_llm_baseline.py` |
| 闭源盲评脚本 | `scripts/run_closed_model_judge.py` |

其中，`cjy-v2` 分支已合入后端同学最新提交，包括自然语言输出层、响应规划层、语气控制模块以及前端适配文档。因此，本章中的 Miro-CogSec 结果反映的是当前最新版系统输出。

### 3.1.2 评估指标

为了避免只用单一总分评价系统，本 benchmark 采用分层指标体系，将系统能力拆分为五个维度：

| 指标层 | 中文含义 | 评估内容 | 权重 |
|---|---|---|---:|
| Problem Localization | 问题定位能力 | 是否识别正确风险类型、风险等级和关键问题 | 30% |
| Actionability | 干预可执行性 | 是否给出及时、具体、可执行的安全建议 | 30% |
| Evidence Grounding | 证据支撑能力 | 分析结论是否能够追溯到输入文本或运行痕迹 | 15% |
| Mechanism Insight | 机制解释能力 | 是否说明风险形成机制、传播路径或关键分叉点 | 15% |
| Output Reliability | 输出可靠性 | 输出格式是否完整、稳定、可被程序解析 | 10% |

综合得分记为 RES，计算方式如下：

```text
RES = 0.30 * Problem Localization
    + 0.30 * Actionability
    + 0.15 * Evidence Grounding
    + 0.15 * Mechanism Insight
    + 0.10 * Output Reliability
```

其中，自由文本类字段尽量采用语义相似度进行评价，分类字段采用轻量软匹配，避免只依赖机械关键词匹配。RES 作为综合分数，用于横向比较系统表现；分层指标用于解释系统强项和短板。

## 3.2 Benchmark 数据集设计

当前 benchmark v0.1 包含三类认知安全场景，共 30 条 gold-reviewed 样本。

| 场景 | 样本数量 | 数据定位 | 评估重点 |
|---|---:|---|---|
| `fraud_im` | 20 | 主评测集 | 即时通讯欺诈中的风险识别、关键分叉点、资产风险和安全干预 |
| `public_opinion` | 5 | seed gold set | 舆情传播中的叙事线、情绪放大、不确定点、官方回应缺口和干预窗口 |
| `event_propagation` | 5 | seed gold set | 事件传播中的源头节点、放大节点、传播路径、失真点和阻断策略 |

三类场景共同覆盖了认知安全系统的三个核心问题：

1. 个人风险：用户是否正在进入诈骗或诱导链路。
2. 群体风险：舆情是否存在情绪放大、误解扩散或回应缺口。
3. 传播风险：事件信息是否经过关键节点扩散、放大或失真。

其中，`fraud_im` 样本数量较多，用于主要量化对比；`public_opinion` 与 `event_propagation` 当前为 seed set，主要用于验证传播类任务的 schema、runtime 和评分路径。

## 3.3 对比实验设计

### 3.3.1 LLM-only Baseline

LLM-only baseline 表示不调用 Miro-CogSec 后端模块，仅让普通大模型在相同输入条件下完成同一份“考卷”。为了保证公平性，LLM-only 输入仅包含任务 ID、场景类型和原始输入文本，不提供 gold answer、评分规则或 Miro-CogSec 的中间模块输出。

该组实验用于回答：

```text
如果没有 Miro-CogSec 的系统模块，仅依赖普通 LLM，任务能完成到什么程度？
```

### 3.3.2 Miro-CogSec Full System

Miro-CogSec full system 表示调用当前完整后端系统，经过场景识别、风险分析、反事实/传播分析、响应规划和自然语言输出适配后生成结果，再由 benchmark adapter 转换为统一评分 schema。

该组实验用于回答：

```text
完整系统相比普通 LLM 是否能提供更稳定、更可追溯、更有干预价值的认知安全分析？
```

### 3.3.3 闭源模型盲评

除自动评分外，本项目还进行了 no-gold 闭源模型盲评。盲评时，评审模型只看到原始输入和两份匿名答案，不看到 gold answer，也不知道哪一份来自 Miro-CogSec，哪一份来自 LLM-only。

盲评用于补充观察自然语言答案质量，但不作为主指标。原因是盲评更接近开放式主观评价，容易受到语言流畅度、解释完整度和模型偏好的影响；自动 RES 则更适合做可复现、可量化的 benchmark 主指标。

## 3.4 自动评分结果

### 3.4.1 综合 RES 对比

在当前 v0.1 benchmark 上，Miro-CogSec 与 LLM-only 的自动评分结果如下：

| 场景 | 样本数 | LLM-only RES | Miro-CogSec RES | 提升 |
|---|---:|---:|---:|---:|
| `fraud_im` | 20 | 0.714 | 0.749 | +0.035 |
| `public_opinion` | 5 | 0.376 | 0.554 | +0.178 |
| `event_propagation` | 5 | 0.589 | 0.709 | +0.120 |

结果表明，在自动语义评分体系下，Miro-CogSec 在三类场景中均高于 LLM-only。尤其是在 `public_opinion` 和 `event_propagation` 两类传播任务中，系统相比普通 LLM-only 表现出更明显优势。

### 3.4.2 分层指标对比

进一步拆分五层指标，可以观察不同系统能力的差异。

| 场景 | 系统 | 问题定位 | 干预可执行性 | 证据支撑 | 机制解释 | 输出可靠性 | RES |
|---|---|---:|---:|---:|---:|---:|---:|
| `fraud_im` | LLM-only | 0.892 | 0.330 | 0.790 | 0.863 | 1.000 | 0.714 |
| `fraud_im` | Miro-CogSec | 0.873 | 0.412 | 0.869 | 0.887 | 1.000 | 0.749 |
| `public_opinion` | LLM-only | 0.277 | 0.159 | 0.843 | 0.128 | 1.000 | 0.376 |
| `public_opinion` | Miro-CogSec | 0.556 | 0.440 | 0.738 | 0.298 | 1.000 | 0.554 |
| `event_propagation` | LLM-only | 0.354 | 0.607 | 0.927 | 0.413 | 1.000 | 0.589 |
| `event_propagation` | Miro-CogSec | 0.710 | 0.661 | 0.803 | 0.513 | 1.000 | 0.709 |

从分层指标看，Miro-CogSec 的优势主要体现在：

- 在 `fraud_im` 中，Miro-CogSec 的干预可执行性、证据支撑和机制解释均高于 LLM-only。
- 在 `public_opinion` 中，Miro-CogSec 在问题定位、干预可执行性和机制解释上提升明显，说明系统对舆情任务的结构化分析比普通 LLM 更稳定。
- 在 `event_propagation` 中，Miro-CogSec 的问题定位和机制解释优于 LLM-only，说明传播仿真和传播结构分析对事件传播任务有实际帮助。

同时也可以看到，LLM-only 在部分证据支撑指标上得分较高。这主要是因为普通 LLM 直接围绕输入文本作答，语言表达往往更贴近原文；而 Miro-CogSec 经过系统模块转换后，部分自然语言表达仍存在模板化问题，影响开放式评价效果。

## 3.5 闭源模型盲评结果

为进一步检查系统输出在开放式评价中的可读性和实用性，本项目使用闭源模型进行了 no-gold 盲评。评审模型只依据原始输入和匿名答案，从问题定位、干预可执行性、证据支撑、机制解释和输出可靠性五个维度进行评价。

盲评结果如下：

| 场景 | 样本数 | Miro-CogSec 胜 | LLM-only 胜 | 平局 |
|---|---:|---:|---:|---:|
| `fraud_im` | 20 | 2 | 16 | 2 |
| `public_opinion` | 5 | 0 | 4 | 1 |
| `event_propagation` | 5 | 1 | 4 | 0 |
| 总计 | 30 | 3 | 24 | 3 |

盲评结果显示，Miro-CogSec 在自然语言输出质量上仍存在明显短板。评审反馈中反复出现的问题是：系统在部分 `fraud_im` 样本中会套用“征信受损”“账户冻结”“安全账户”等模板化诈骗话术，导致答案与输入场景不完全匹配。例如，实名手机卡交易、信用卡代还、赌博广告、办证广告等场景，实际风险机制不同，但系统输出有时仍偏向“安全账户”类诈骗剧本。

因此，闭源盲评暴露的问题不是 benchmark 流程错误，而是系统表达层和场景细分层仍需优化。自动评分说明 Miro-CogSec 在结构化任务字段上具备优势；盲评说明系统在面向评审和用户的自然语言表达上仍需进一步提升。

## 3.6 结果分析

### 3.6.1 系统优势

Miro-CogSec 相比 LLM-only 的优势主要体现在三个方面。

第一，系统能够保持稳定的结构化输出。三类场景中，Miro-CogSec 的输出可靠性均为 1.000，说明 benchmark 所需字段能够被稳定生成和解析。

第二，系统在传播类任务中具有更明显优势。`public_opinion` 的 RES 从 0.376 提升到 0.554，`event_propagation` 的 RES 从 0.589 提升到 0.709，说明传播分析模块和 runtime adapter 对群体性认知安全任务有帮助。

第三，系统在干预可执行性上整体优于 LLM-only。尤其在 `fraud_im` 和 `public_opinion` 中，Miro-CogSec 更倾向于给出明确的干预窗口和安全建议，而不是只做泛泛解释。

### 3.6.2 当前不足

当前不足主要集中在自然语言表达层和场景细分层。

第一，部分输出存在模板化问题。尤其在欺诈类场景中，系统有时将不同类型诈骗统一套入“安全账户”剧本，导致机制解释与输入不匹配。

第二，传播类 seed set 样本数量仍较少。`public_opinion` 与 `event_propagation` 目前各 5 条样本，更适合作为早期验证集；后续若用于正式比赛展示，应继续扩充样本规模。

第三，ablation 实验尚未形成完整闭环。当前 benchmark 已设计 `without propagation`、`without RAG`、`without counterfactual branch` 等消融组，但仍需要后端提供正式开关，才能得到可复现的模块贡献数据。

## 3.7 可靠性与可复现性说明

本 benchmark 具有以下可复现设计：

| 项目 | 说明 |
|---|---|
| 固定数据集 | 三类场景样本均保存在 `benchmark/data/` 下 |
| 固定输出格式 | LLM-only 与 Miro-CogSec 均对齐统一 schema |
| 固定评分脚本 | 自动评分由 `benchmark/cogsec_benchmark.py` 完成 |
| 固定实验产物 | 实验输出保存在 `benchmark/outputs/` 下 |
| 固定报告路径 | 设计文档与结果报告保存在 `benchmark/reports/` 下 |

因此，评审或团队成员可以基于相同数据和脚本复现实验结果，并检查每条样本的输出、得分和错误原因。

## 3.8 小结

本章构建并验证了一套面向认知安全任务的 benchmark 评估体系。该体系覆盖欺诈识别、舆情风险研判和事件传播分析三类任务，采用统一 schema、统一评分规则和统一样本集比较 Miro-CogSec 与 LLM-only。

实验结果表明，在自动语义 RES 评分下，Miro-CogSec 在三类任务中均高于 LLM-only，说明系统模块在结构化风险识别、传播分析和干预建议方面具有一定有效性。同时，闭源模型盲评显示，系统当前自然语言表达仍存在模板化和场景错配问题。后续优化方向应集中在场景细分、响应模板选择和证据驱动的自然语言生成上，以提升系统在开放式人工评价中的表现。
