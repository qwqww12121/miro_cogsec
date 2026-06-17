# 当前实验结果与评分项说明


1. 当前已有实验结果
2. benchmark 评分项说明

## 1. 当前实验结果

### 1.1 DeepSeek LLM-only Baseline

LLM-only baseline 已完整跑完三类场景。该 baseline 不使用 Miro-CogSec 的 RAG、传播仿真、反事实分支，只根据 prompt 直接输出 benchmark 答卷字段。

| 场景 | 样本数 | Detection | Reasoning | Intervention | Evidence | Runtime | RES | 状态 |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `fraud_im` | 20 | 0.988 | 0.954 | 0.340 | 0.928 | N/A | 0.789 | completed |
| `public_opinion` | 5 | 0.800 | 0.400 | 0.173 | 0.701 | N/A | 0.399 | completed |
| `event_propagation` | 5 | 1.000 | 0.640 | 0.600 | 0.848 | N/A | 0.697 | completed |

### 1.2 Miro-CogSec Full System：fraud_im

`fraud_im` 已用 Miro-CogSec full system 跑完 20 条。

| 场景 | 样本数 | Runtime Success | Scenario Match | Latency p50 | Latency p95 | Max Latency | RES | 状态 |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `fraud_im` | 20 | 100.0 | 100.0 | 8048.306 ms | 28267.200 ms | 29177.688 ms | 0.407 | completed |

分层结果：

| 场景 | Detection | Reasoning | Intervention | Evidence | Runtime | RES |
|---|---:|---:|---:|---:|---:|---:|
| `fraud_im` | 0.750 | 0.500 | 0.217 | 0.000 | 1.000 | 0.407 |

细分评分项：

| 场景 | FPA | ATA | RCA | IWA | EAR | ASA | WSA |
|---|---:|---:|---:|---:|---:|---:|---:|
| `fraud_im` | 70.0 | 30.0 | 80.0 | 65.0 | 0.0 | 0.0 | 0.0 |

补充记录：

| 指标 | 数值 |
|---|---:|
| format_success_rate | 100.0 |
| complete_schema_rate | 0.0 |

### 1.3 Miro-CogSec Full System：public_opinion Smoke

`public_opinion` 目前只跑了 1 条 smoke，不是完整正式结果。

| 场景 | 已跑样本 | Runtime Success | Scenario Match | Propagation Present | Latency | RES | 状态 |
|---|---:|---:|---:|---:|---:|---:|---|
| `public_opinion` | 1/5 | 100.0 | 100.0 | 100.0 | 74530.148 ms | 0.198 | smoke |

分层结果：

| 场景 | Detection | Reasoning | Intervention | Evidence | Runtime | RES |
|---|---:|---:|---:|---:|---:|---:|
| `public_opinion` | 0.200 | 0.023 | 0.014 | 0.000 | 0.667 | 0.198 |

细分评分项：

| 场景 | NSS | EAS | UGS | OGS | RCA | IWA | IAS | SPS | EAR |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `public_opinion` | 1.6 | 45.0 | 0.0 | 0.0 | 100.0 | 21.0 | 0.0 | 0.0 | 0.0 |

补充记录：

| 指标 | 数值 |
|---|---:|
| case_count | 5 |
| scored_case_count | 1 |
| format_success_rate | 20.0 |
| complete_schema_rate | 20.0 |

### 1.4 Miro-CogSec：event_propagation Smoke

`event_propagation` 当前记录来自此前 1 条 smoke 和 adapter 试算，不是完整正式结果。

| 场景 | 已跑样本 | Detection | Reasoning | Intervention | Evidence | Runtime | RES | 状态 |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `event_propagation` | 1/5 | 0.200 | 0.017 | 0.100 | 0.000 | 0.667 | 0.293 | smoke |

## 2. 评分项说明

### 2.1 总体分层

| 分层 | 含义 | 主要看什么 |
|---|---|---|
| Detection | 检测能力 | 场景是否识别正确，风险等级是否判断正确 |
| Reasoning | 推理能力 | 是否找到正确的风险机制、分叉点、传播节点、叙事线或失真点 |
| Intervention | 干预能力 | 是否找到合适干预窗口，并给出可执行建议 |
| Evidence | 证据归因 | 输出结论是否能对应输入文本或 runtime trace 中的证据 |
| Runtime | 运行稳定性 | 是否跑通、延迟、传播结果是否存在、错误率 |
| RES | 总分 | 由各场景的细分指标加权得到 |

### 2.2 fraud_im 评分项

| 指标 | 英文名 | 含义 |
|---|---|---|
| FPA | Fork Point Accuracy | 关键分叉点是否判断正确 |
| ATA | Asset Target Accuracy | 受威胁资产是否识别正确，例如资金、凭证、身份、设备 |
| RCA | Risk Calibration Accuracy | 风险等级是否和 gold answer 对齐 |
| IWA | Intervention Window Accuracy | 干预窗口是否和 gold answer 对齐 |
| EAR | Evidence Attribution Rate | 证据片段是否覆盖 gold evidence，且来自输入文本 |
| ASA | Action Similarity Accuracy | 安全行动建议是否和 gold answer 相似 |
| WSA | Warning Similarity Accuracy | 风险提醒是否和 gold answer 相似 |
| RES | Runtime Evaluation Score | `fraud_im` 综合得分 |

### 2.3 public_opinion 评分项

| 指标 | 英文名 | 含义 |
|---|---|---|
| NSS | Narrative Similarity Score | 叙事线和风险叙事是否对齐 |
| EAS | Emotion Amplification Score | 情绪类型和情绪放大强度是否对齐 |
| UGS | Uncertainty Gap Score | 不确定点、事实缺口是否对齐 |
| OGS | Official Gap Score | 官方回应缺口是否判断正确 |
| RCA | Risk Calibration Accuracy | 传播风险等级是否对齐 |
| IWA | Intervention Window Accuracy | 最佳干预窗口是否对齐 |
| IAS | Intervention Action Similarity | 干预动作是否和 gold answer 相似 |
| SPS | Safe Public Action Similarity | 公众安全行动建议是否相似 |
| EAR | Evidence Attribution Rate | 证据片段是否对齐 |
| RES | Runtime Evaluation Score | `public_opinion` 综合得分 |

### 2.4 event_propagation 评分项

| 指标 | 英文名 | 含义 |
|---|---|---|
| OVS | Origin Validity Score | 源头节点或早期来源是否判断正确 |
| ANS | Amplifier Node Score | 放大节点是否识别正确 |
| PCS | Propagation Chain Score | 传播路径是否对齐 |
| DCS | Distortion Consistency Score | 信息失真点是否识别正确 |
| RCA | Risk Calibration Accuracy | 覆盖风险等级是否对齐 |
| CWS | Containment Window Score | 阻断窗口是否对齐 |
| CAS | Containment Action Similarity | 阻断或澄清动作是否相似 |
| EAR | Evidence Attribution Rate | 证据片段是否对齐 |
| RES | Runtime Evaluation Score | `event_propagation` 综合得分 |

## 3. 当前结果备注

当前 Miro-CogSec 的结果主要来自 runtime trace 到 benchmark `prediction` 字段的 adapter 转换。`fraud_im` 的 `complete_schema_rate = 0.0`，说明后端原生输出还没有直接填写完整标准答卷字段。因此现阶段分数更适合记录“当前输出对齐程度”，不能直接等同于系统最终能力上限。
