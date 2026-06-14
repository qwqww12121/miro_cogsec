# Runtime Alignment TODO

本文档记录 API 接入后，如何把后端输出对齐到 benchmark gold answer。

## 核心结论

当前 benchmark 已经有三类 gold answer 和评分函数。后续缺的不是重新设计指标，而是补一个 adapter：

```text
backend raw output
  -> normalized prediction JSON
  -> score against gold answer
```

评分入口已经存在：

```powershell
py benchmark\cogsec_benchmark.py score-scenario-predictions --scenario-type public_opinion --truth benchmark\data\public_opinion_v0.1.jsonl --predictions <prediction.jsonl> --output <metrics.json>
py benchmark\cogsec_benchmark.py score-scenario-predictions --scenario-type event_propagation --truth benchmark\data\event_propagation_v0.1.jsonl --predictions <prediction.jsonl> --output <metrics.json>
```

## 第一步：保存后端原始输出

API / key 接好后，先每个场景只跑 1 条，不急着全量实验：

```powershell
C:\Users\19579\.conda\envs\miro-cogsec\python.exe scripts\run_scenario_api_benchmark.py --scenario public_opinion --limit 1 --disable-chroma --no-local-gemma
C:\Users\19579\.conda\envs\miro-cogsec\python.exe scripts\run_scenario_api_benchmark.py --scenario event_propagation --limit 1 --disable-chroma --no-local-gemma
```

重点查看每条输出中的：

- `scenario_metadata`
- `scenario_extension`
- `scenario_extension.propagation`
- `role_report`
- `prediction`
- `metrics`

## 第二步：做字段对齐表

### public_opinion

| gold 字段 | 后端可能来源 | 对齐状态 |
|---|---|---|
| `narrative_threads` | `role_report.markdown` / `role_report.structured` | 待确认 |
| `emotion_signal` | `scenario_extension.propagation.branch_*.emotion_curve` / report | 待确认 |
| `uncertainty_points` | `role_report.markdown` / structured sections | 待确认 |
| `official_response_gap` | role report / scenario-specific text | 待确认 |
| `propagation_risk_level` | propagation final metrics / risk breakdown | 待确认 |
| `best_intervention_window` | propagation `fork_point` / comparison | 待确认 |
| `expected_intervention_action` | intervention prescriptions / role report | 待确认 |
| `expected_safe_public_action` | role report recommendations | 待确认 |
| `evidence_spans` | report text / input keyword overlap | 待确认 |

### event_propagation

| gold 字段 | 后端可能来源 | 对齐状态 |
|---|---|---|
| `origin_node` | propagation event / fork point / report timeline | 待确认 |
| `amplifier_nodes` | propagation key nodes / report | 待确认 |
| `propagation_path` | propagation branch traces / report timeline | 待确认 |
| `distortion_points` | role report / scenario-specific analysis | 待确认 |
| `coverage_risk` | propagation final coverage / risk metrics | 待确认 |
| `containment_window` | propagation `fork_point.intervention_tick` | 待确认 |
| `expected_containment_action` | intervention prescriptions / role report | 待确认 |
| `evidence_spans` | report text / input keyword overlap | 待确认 |

## 第三步：写 adapter

adapter 的输出格式必须是 JSONL，每行至少包含：

```json
{
  "id": "public-opinion-v0.1-001",
  "prediction": {
    "narrative_threads": [],
    "emotion_signal": {},
    "uncertainty_points": [],
    "official_response_gap": {},
    "propagation_risk_level": "medium",
    "best_intervention_window": {},
    "expected_intervention_action": "",
    "expected_safe_public_action": "",
    "evidence_spans": []
  }
}
```

event_propagation 对应：

```json
{
  "id": "event-propagation-v0.1-001",
  "prediction": {
    "origin_node": {},
    "amplifier_nodes": [],
    "propagation_path": [],
    "distortion_points": [],
    "coverage_risk": "medium",
    "containment_window": {},
    "expected_containment_action": "",
    "evidence_spans": []
  }
}
```

## 当前判断

API 未接入前，不需要强行写最终 adapter。现在最合理的工作是：

1. 保留 gold schema 和评分函数。
2. 等后端能跑后，保存每个场景 1 条真实输出。
3. 根据真实输出填写字段对齐表。
4. 再写 adapter，把后端输出转成 prediction JSONL。
