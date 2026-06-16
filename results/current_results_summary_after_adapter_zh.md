# Miro-CogSec Adapter 后结果汇总

## 运行配置

- 命令：`conda run -n ai_basic python scripts/run_scenario_api_benchmark.py --scenario all --disable-chroma --no-local-gemma`
- 说明：本次用于验证 benchmark adapter、`cogsec_analysis`、以及 public/event 的 counterfactual intervention search 输出合同。
- 注意：本次未声称 full OASIS per-candidate branches；OASIS adapter 可 import，但没有 API key 时会回退到 lightweight propagation，并将 counterfactual branch 指标标注为 `metric_source=proxy`。

## Answer Score After Adapter

| 场景 | 样本数 | Runtime Success | Complete Schema | RES | 关键变化 |
|---|---:|---:|---:|---:|---|
| `fraud_im` | 20 | 100.0 | 100.0 | 0.699 | 从旧 runtime adapter 的 schema 缺失改为完整 benchmark prediction |
| `public_opinion` | 5 | 100.0 | 100.0 | 0.414 | 跑满 5 条，补齐 evidence、窗口、动作和传播干预搜索字段 |
| `event_propagation` | 5 | 100.0 | 100.0 | 0.597 | 跑满 5 条，补齐 origin/amplifier/path/distortion/containment 字段 |

## 细分指标

| 场景 | 细分指标 |
|---|---|
| `fraud_im` | FPA 70.0, ATA 84.2, RCA 70.0, IWA 85.0, EAR 87.0, ASA 25.9, WSA 17.2 |
| `public_opinion` | NSS 26.8, EAS 38.0, UGS 16.7, OGS 38.4, RCA 70.0, IWA 47.4, IAS 37.4, SPS 47.9, EAR 73.8 |
| `event_propagation` | OVS 41.9, ANS 65.5, PCS 57.1, DCS 38.5, RCA 70.0, CWS 90.0, CAS 41.5, EAR 75.8 |

## Before / After 对比

| 场景 | Before | After | 主要解释 |
|---|---:|---:|---|
| `fraud_im` | RES 0.407, complete_schema_rate 0.0, EAR 0.0 | RES 0.699, complete_schema_rate 100.0, EAR 87.0 | 低分主因是旧 adapter 没输出完整答卷字段，也没有从原文抽 evidence spans |
| `public_opinion` | 1 条 smoke RES 0.198, complete_schema_rate 20.0 | 5 条正式 RES 0.414, complete_schema_rate 100.0 | 已从 smoke 跑到完整 5 条，并新增传播多分支 search |
| `event_propagation` | 1 条 smoke RES 0.293 | 5 条正式 RES 0.597, complete_schema_rate 100.0 | 传播链、放大节点、失真点、阻断窗口字段已补齐 |

## Mechanistic / Traceability Summary

| 场景 | Risk Graph | Counterfactual | Propagation Search | Branches | Metric Source |
|---|---:|---:|---:|---:|---|
| `fraud_im` | 100.0 | 100.0 | N/A | N/A | runtime/RAG/counterfactual report |
| `public_opinion` | 100.0 | 100.0 | 100.0 | 4.0 | proxy |
| `event_propagation` | 100.0 | 100.0 | 100.0 | 4.0 | proxy |

## 仍需注意

1. `public_opinion` 的 NSS/UGS/OGS 仍偏低，说明叙事线、不确定点、官方回应缺口需要更贴近 gold 语言。
2. `fraud_im` 的 ASA/WSA 仍偏低，说明安全动作和 warning 文案还可以继续做模板化归一。
3. `event_propagation` 的 OVS/DCS 仍有提升空间，主要是 origin type 和 distortion description 的枚举/表述还没有完全对齐 gold。
4. 当前 counterfactual intervention search 已经实现 baseline + 4 branches + branch comparison + selected best branch，但本次指标是 proxy，不是 full OASIS per-candidate runtime。

## 输出文件

- `results/answer_score_summary_after_adapter.json`
- `results/mechanistic_score_summary.json`
- `benchmark/outputs/api_fraud_im_after_adapter_v0.1.jsonl`
- `benchmark/outputs/api_public_opinion_after_adapter_v0.1.jsonl`
- `benchmark/outputs/api_event_propagation_after_adapter_v0.1.jsonl`
- `benchmark/outputs/api_fraud_im_mechanistic_after_adapter_v0.1.json`
- `benchmark/outputs/api_public_opinion_mechanistic_after_adapter_v0.1.json`
- `benchmark/outputs/api_event_propagation_mechanistic_after_adapter_v0.1.json`
