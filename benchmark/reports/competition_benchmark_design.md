# Miro-CogSec 比赛级 Benchmark 设计说明

## 1. 设计目标

本 benchmark 的目标不是简单证明“系统能跑”，而是为信息安全作品大赛提供一套可复现、可解释、可对比的评测体系。

核心问题是：

```text
相比普通 LLM 直接输出，Miro-CogSec 是否能在认知安全场景中更早发现风险、
更清楚解释风险机制，并给出更有效的安全干预？
```

因此，benchmark 需要同时回答三类问题：

| 问题 | 解释 |
|---|---|
| 完整性 | 是否覆盖诈骗、舆情、事件传播等不同认知安全场景？ |
| 公平性 | 是否用同一批 gold samples、同一套评分规则比较 LLM-only 和 Miro-CogSec？ |
| 解释性 | 如果系统表现好或不好，能否说明是 detection、reasoning、intervention、evidence 还是 runtime 出了问题？ |

## 2. 场景设置

当前 benchmark v0.1 覆盖三类场景：

| 场景 | 样本数 | 当前定位 | 评测重点 |
|---|---:|---|---|
| `fraud_im` | 20 | 主评测集 | 诈骗链路中的风险识别、关键分叉点、资产风险、不可逆操作和安全干预 |
| `public_opinion` | 5 | seed gold set | 舆情讨论中的叙事线程、情绪放大、不确定点、官方回应缺口和干预窗口 |
| `event_propagation` | 5 | seed gold set | 事件信息的来源节点、放大节点、传播路径、失真点和阻断窗口 |

说明：

- `fraud_im` 是当前最成熟的主评测集，用于展示 Miro-CogSec 在诈骗风险识别和干预上的能力。
- `public_opinion` 和 `event_propagation` 目前是小规模 seed set，主要用于验证传播类 schema、runtime 输出和评分口径。
- 三类场景都使用人工整理的 gold answer，而不是直接依赖原始公开数据集自带标签。

## 3. 对照组设计

比赛级 benchmark 不应只展示一个系统分数，而应设置清晰的对照组和消融组。

### 3.1 基础对照组

| 组别 | 名称 | 目的 | 当前状态 |
|---|---|---|---|
| A | DeepSeek LLM-only baseline | 测试普通 LLM 不使用 Miro-CogSec 模块时的直接答题能力 | 已完成三场景 baseline |
| B | Miro-CogSec full system | 测试完整系统能力，包括场景识别、RAG、反事实分支和传播仿真 | 待补正式全量 runtime 结果 |

这两组是最核心的比赛对比：

```text
同一批 gold samples
  -> DeepSeek LLM-only
  -> Miro-CogSec full system
  -> 使用同一套 scorer 比较
```

### 3.2 消融实验组

为了说明 Miro-CogSec 的具体模块是否真的带来贡献，建议加入以下 ablation：

| 组别 | 名称 | 目的 | 当前状态 |
|---|---|---|---|
| C | Miro-CogSec without propagation | 验证传播仿真模块对舆情和事件传播任务的贡献 | 待后端确认开关 |
| D | Miro-CogSec without RAG | 验证知识检索模块对风险解释和证据支持的贡献 | 待后端确认开关 |
| E | Miro-CogSec without counterfactual branch | 验证反事实分支推理对干预窗口和安全建议的贡献 | 待后端确认开关 |

原则：

- 不伪造 ablation 结果。
- 如果后端没有正式开关，报告中只写 planned ablation，不写假分数。
- 如果后端提供开关，每个 ablation 至少应在 seed set 或 smoke set 上跑一次。
- 报告中要明确区分 `completed baseline`、`completed full-system result`、`planned ablation` 和 `blocked by backend switch`。

### 3.3 建议的后端开关

为了支持正式 ablation，建议后端提供命令行参数或环境变量。

命令行形式：

```text
--disable-propagation
--disable-rag
--disable-counterfactual
```

环境变量形式：

```text
COGSEC_DISABLE_PROPAGATION=true
COGSEC_DISABLE_RAG=true
COGSEC_DISABLE_COUNTERFACTUAL=true
```

benchmark runner 需要记录本次运行配置：

```json
{
  "system_variant": "full",
  "disabled_modules": []
}
```

或：

```json
{
  "system_variant": "without_propagation",
  "disabled_modules": ["propagation"]
}
```

这样后续结果表才能清楚说明每个分数来自哪个系统版本。

## 4. 分层指标体系

比赛评委不一定只关心一个总分。单一 RES 分数可以总结表现，但不能解释系统为什么好或不好。因此 benchmark 应提供五层指标。

| Layer | 中文含义 | 评测问题 | 示例指标 |
|---|---|---|---|
| detection | 场景识别 | 系统有没有识别对任务类型和风险等级？ | scenario_match, risk calibration |
| reasoning | 风险推理 | 系统有没有找到正确风险机制、传播链路或叙事结构？ | fork accuracy, narrative score, propagation path score |
| intervention | 干预能力 | 系统有没有给出早期、可执行的干预建议？ | intervention window score, containment window score, safe action score |
| evidence | 证据可追溯 | 系统结论是否来自输入文本或 runtime trace？ | evidence attribution, evidence coverage |
| runtime | 稳定性与效率 | 系统能不能稳定运行，延迟和错误率是否可接受？ | success rate, latency, error count, propagation presence |

最终报告不应只写：

```text
Miro-CogSec RES = 0.xx
```

而应写成：

```text
Miro-CogSec 在 detection 和 runtime 上表现较强，
但在 propagation semantic reasoning 和 evidence attribution 上仍有不足。
```

## 5. 各场景的指标映射

### 5.1 fraud_im

| Layer | 指标来源 | 说明 |
|---|---|---|
| detection | risk calibration, fraud/fork presence | 是否识别出诈骗或高风险链路 |
| reasoning | fork point, asset target, counterfactual path | 是否识别关键分叉点、资产类型和高风险路径 |
| intervention | intervention window, safe action, warning | 是否在不可逆操作前给出安全建议 |
| evidence | evidence span attribution | 结论是否能追溯到输入文本 |
| runtime | runtime success, latency, error count | 后端完整链路是否稳定 |

### 5.2 public_opinion

| Layer | 指标来源 | 说明 |
|---|---|---|
| detection | scenario match, propagation risk calibration | 是否识别为舆情场景，风险等级是否合理 |
| reasoning | narrative threads, emotion signal, uncertainty points, official response gap | 是否识别叙事、情绪、不确定点和回应缺口 |
| intervention | best intervention window, expected intervention action | 是否给出合适的澄清、降温或信息补充策略 |
| evidence | evidence spans, runtime trace evidence | 是否能说明判断依据来自哪里 |
| runtime | propagation presence, success rate, latency | OASIS propagation 是否跑通 |

### 5.3 event_propagation

| Layer | 指标来源 | 说明 |
|---|---|---|
| detection | scenario match, coverage risk calibration | 是否识别为事件传播场景，覆盖风险是否合理 |
| reasoning | origin node, amplifier nodes, propagation path, distortion points | 是否识别来源、放大节点、传播路径和失真点 |
| intervention | containment window, expected containment action | 是否能在失真扩大前给出阻断策略 |
| evidence | evidence spans, runtime trace evidence | 是否能追溯到输入或传播轨迹 |
| runtime | propagation presence, success rate, latency | 传播仿真是否稳定运行 |

## 6. RES 的定位

RES 保留，但它应被定位为 summary score，而不是唯一结论。

推荐报告写法：

```text
RES is a summary score.
Layered metrics explain why the score is high or low.
```

也就是说：

- RES 用来做最终横向比较。
- 分层指标用来解释系统能力结构。
- 如果 RES 低，但 runtime 和 detection 高，说明系统能跑、能识别场景，但语义字段仍未对齐。
- 如果 RES 高，但 evidence 低，说明系统可能“答对了”，但解释性和可追溯性不足。

## 7. 统一结果表格式

最终比赛报告建议使用如下表格：

| Scenario | System | Detection | Reasoning | Intervention | Evidence | Runtime | RES | Status |
|---|---|---:|---:|---:|---:|---:|---:|---|
| `fraud_im` | DeepSeek LLM-only | TBD | TBD | TBD | TBD | N/A | 0.789 | completed baseline |
| `fraud_im` | Miro-CogSec full | TBD | TBD | TBD | TBD | TBD | TBD | pending full runtime |
| `fraud_im` | Miro-CogSec w/o RAG | TBD | TBD | TBD | TBD | TBD | TBD | pending backend switch |
| `public_opinion` | DeepSeek LLM-only | TBD | TBD | TBD | TBD | N/A | 0.399 | completed baseline |
| `public_opinion` | Miro-CogSec full | TBD | TBD | TBD | TBD | TBD | TBD | pending full runtime |
| `public_opinion` | Miro-CogSec w/o propagation | TBD | TBD | TBD | TBD | TBD | TBD | pending backend switch |
| `event_propagation` | DeepSeek LLM-only | TBD | TBD | TBD | TBD | N/A | 0.701 | completed baseline |
| `event_propagation` | Miro-CogSec full | TBD | TBD | TBD | TBD | TBD | TBD | pending full runtime |
| `event_propagation` | Miro-CogSec w/o propagation | TBD | TBD | TBD | TBD | TBD | TBD | pending backend switch |

说明：

- `TBD` 表示指标还没有正式计算。
- `N/A` 表示该系统类型不适用，例如 LLM-only 没有 runtime success rate。
- `pending backend switch` 表示消融实验设计已确定，但需要后端提供正式开关。

## 8. 当前状态

当前可以安全说明：

- 三场景 benchmark 已建立。
- DeepSeek LLM-only baseline 已完成。
- `public_opinion` 和 `event_propagation` 的 propagation runtime smoke 已通过。
- Windows SQLite `branch_a.db` 文件锁问题在 smoke test 中未复现。
- benchmark 侧已经有 runtime adapter，可以把传播 runtime trace 转成可评分 prediction 字段。

当前还不能夸大说明：

- 不能说 Miro-CogSec 已经全面超过 LLM-only。
- 不能说传播类语义字段已经完全对齐。
- 不能说 ablation 已经证明某个模块有效，除非后端开关和实验结果补齐。

## 9. 下一步

建议按以下顺序推进：

1. 先确认这份 benchmark 设计文档是否得到团队认可。
2. 在 scorer 中增加 `layer_scores` 输出，不替换现有 RES。
3. 在 runner 输出中记录 `system_variant` 和 `disabled_modules`。
4. 与后端确认是否支持 propagation / RAG / counterfactual 的禁用开关。
5. 再跑 Miro-CogSec full system 的正式结果。
6. 如果开关可用，再跑 ablation；如果不可用，只在报告中标注 planned ablation。

## 10. 评审展示口径

比赛展示时建议这样讲：

```text
我们不是只做了一个 demo，也不是只让模型生成一段分析。
我们构建了一个三场景 benchmark，用同一批 gold answer 比较普通 LLM 和 Miro-CogSec。
评测不仅看总分 RES，还拆成 detection、reasoning、intervention、evidence、runtime 五层。
这样可以说明系统到底强在哪里、弱在哪里，以及每个安全模块是否真的有贡献。
```

