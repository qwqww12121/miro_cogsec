# 前端修改指导文档：React 前端接入后端输出层

> 本文档只给前端修改建议。当前代码已同步 React + Tailwind 前端，但本次没有直接改 React 结果页展示逻辑。

## 1. 当前前端结构审查

当前前端是 React + Vite + Tailwind 项目，核心目录如下：

- `frontend/src/api/cogsec.js`
  - 负责调用 `/api/cogsec/analyze`。
- `frontend/src/api/scenarios.js`
  - 三个场景统一拼装请求体，分别传入 `fraud_im` / `public_opinion` / `event_propagation`。
- `frontend/src/pages/scenarios/*Page.jsx`
  - 三个场景的输入页。
- `frontend/src/components/results/*Result.jsx`
  - 当前三个结果面板。
  - 直接展示 `profile`、`metrics`、`counterfactual_report`、`scenario_extension.propagation`、`intervention_prescriptions` 等结构化字段。
- `frontend/src/pages/Home.jsx`
  - 首页场景选择与智能识别入口。
- `frontend/src/pages/BenchmarkPage.jsx`
  - 离线 benchmark 摘要页。

当前页面优点是三类场景入口清楚、机制展示较完整；主要问题是用户第一眼仍然看到结构化结果和工程指标，不是后端新增的成熟 AI 助手式最终回答。

## 2. 这次后端新增的可消费字段

后端现在会在原有 `analysis` payload 上新增兼容字段，不移除旧字段：

| 字段 | 用途 | 前端建议 |
|---|---|---|
| `assistant_message` | 面向用户/评审的自然语言最终回答 | 放在结果页首屏最上方，作为主答案 |
| `response_plan` | 后端用于生成回答的轻量规划 | 仅调试或二级详情使用，不建议首屏直接展示 |
| `graph_payload` | 规整后的图谱高亮数据 | 未来替代或补充 `risk_graph_bundle` 的可视化输入 |
| `suggested_followups` | 建议追问 | 放在回答卡片底部，做快捷按钮 |
| `latency_profile` | quick/full/branch latency 和 metric_source | 放在小型状态条，不要占据主叙事位置 |
| `conversation_state` | 多轮追问缓存状态 | 前端通常不用直接渲染，只需保存 session 即可 |

## 3. 首屏建议结构

建议把三个结果页的第一屏从“工程指标优先”改为“答案优先”：

```text
[自然语言回答区]
assistant_message
suggested_followups

[状态条]
scenario / risk / metric_source / latency

[机制详情]
证据链 | 图谱 | 传播路径 | 干预分支 | 原始工程数据
```

重点：不要让普通用户第一眼先看到 `FinalRisk`、`Fork`、`T0`、`E2E` 这些工程缩写。它们可以保留，但应降级到状态条或详情区。

## 4. 推荐组件拆分

建议新增或重构以下组件，但不要求一次完成：

| 组件 | 输入 | 作用 |
|---|---|---|
| `AssistantAnswerPanel.jsx` | `assistantMessage`, `suggestedFollowups`, `tone` | 展示自然回答和追问按钮 |
| `CogSecStatusStrip.jsx` | `scenarioMetadata`, `latencyProfile`, `responsePlan` | 展示场景、来源、耗时、是否 proxy |
| `EvidenceList.jsx` | `responsePlan.evidence_trace`, `graphPayload.evidence_links` | 展示 2-4 条关键证据 |
| `InterventionBranchesPanel.jsx` | `responsePlan.candidate_summaries`, `responsePlan.selected_branch` | 展示候选方案和 selected best branch |
| `GraphPayloadView.jsx` | `graphPayload` | 优先高亮节点/边，不直接吃超大 raw graph |
| `RawDebugPanel.jsx` | 原始 `analysis` | 折叠显示，供研究/调试使用 |

### 最小展示块建议

后续前端同学可以先不重构页面，只在三个 `*Result.jsx` 的指标卡片之前加入一个很小的展示块：

```jsx
function AssistantMessageBlock({ data }) {
  if (!data?.assistant_message) return null
  return (
    <Section title="系统结论">
      <div className="text-sm text-ink-900 leading-relaxed whitespace-pre-wrap">
        {data.assistant_message}
      </div>
      {data.suggested_followups?.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {data.suggested_followups.slice(0, 4).map((item) => (
            <button key={item} type="button" className="btn-ghost text-xs">
              {item}
            </button>
          ))}
        </div>
      )}
    </Section>
  )
}
```

接入位置：

- `frontend/src/components/results/FraudImResult.jsx`
- `frontend/src/components/results/PublicOpinionResult.jsx`
- `frontend/src/components/results/EventPropagationResult.jsx`

放在 `return <>` 后、四个 `StatTile` 指标之前即可。没有 `assistant_message` 时返回 `null`，不影响旧后端。

## 5. graph_payload 使用建议

后端返回的 `graph_payload` 是给前端未来使用的规整视图：

```json
{
  "graph_mode": "public_opinion|event_propagation|fraud_im",
  "highlight_nodes": [],
  "highlight_edges": [],
  "active_branch": "baseline|branch_001|...",
  "display_step": "summary|evidence|mechanism|candidates|selected_intervention",
  "node_annotations": {},
  "edge_annotations": {},
  "evidence_links": [],
  "nodes": [],
  "edges": []
}
```

前端建议：

1. 优先用 `highlight_nodes` 控制图谱节点高亮。
2. 用 `active_branch` 切换候选干预分支展示。
3. 用 `evidence_links` 在图谱旁展示证据卡片。
4. 如果 `nodes/edges` 为空，再 fallback 到旧的 `risk_graph_bundle`。
5. 不要把完整 `cogsec_analysis` 或 `benchmark_prediction` 直接作为用户答案渲染。

## 6. tone 控制建议

后端支持四种 tone：

| tone | 前端入口建议 | 展示风格 |
|---|---|---|
| `friendly` | 默认普通用户 | 温和、清楚、行动建议优先 |
| `serious` | 管理员/处置人员 | 风险判断、关键依据、处置建议 |
| `expert` | 老师/评审/研究展示 | 机制链路、分支比较、指标来源 |
| `judge_friendly` | A/B judge 或 demo 对比 | 短、自然、少术语、结论先行 |

前端可以在请求体里加：

```json
{ "tone": "friendly" }
```

不传时后端默认 `friendly`。

## 7. 多轮追问接入建议

当前后端支持 session state 复用：完整分析后，用户再问这些问题时可以不重跑 pipeline：

- “为什么？”
- “证据是什么？”
- “还有别的方案吗？”
- “为什么选这个方案？”

前端建议：

1. 用户提交原始事件内容后调用 `/api/cogsec/session/<session_id>/analyze`。
2. 后续追问走 `/api/cogsec/session/<session_id>/turn`。
3. 如果返回里有 `data.conversational_response`，优先展示它。
4. 如果没有，说明不是缓存可回答追问，再提示用户是否重新完整分析。

## 8. P0-P3 修改优先级

### P0：只接主答案

- 在三个 React 结果页首屏顶部展示 `data.assistant_message`。
- 有 `suggested_followups` 时展示为按钮。
- 保留现有 StatTile、曲线、传播仿真表格和干预建议，不改图谱、不改分支。

### P1：接 latency 和 metric source

- 展示 `data.latency_profile.metric_source`。
- 如果是 `proxy`，文案用“轻量近似指标”，不要写“完整 OASIS”。
- 展示 quick/full latency，但不让它压过主答案。

### P2：接 graph_payload 高亮

- 未来的图谱组件支持 `graph_payload.nodes/edges`。
- 支持 `highlight_nodes` 视觉高亮。
- 旧 `risk_graph_bundle` 作为 fallback。

### P3：多轮追问体验

- 在回答卡底部显示 `suggested_followups`。
- 点击后走 `/session/<id>/turn`。
- 用 `conversational_response.assistant_message` 追加到聊天区。

## 9. 当前 TODO 清单

| 优先级 | TODO | 文件 |
|---|---|---|
| P0 | 新增 `AssistantMessageBlock.jsx` 或在三个结果页内联最小展示块 | `frontend/src/components/results/*Result.jsx` |
| P0 | 请求体默认带 `tone: 'friendly'`，评测/展示时可切到 `judge_friendly` 或 `expert` | `frontend/src/api/scenarios.js` |
| P1 | 在结果页小状态区展示 `latency_profile.metric_source` 和 fallback reason | `frontend/src/components/results/*Result.jsx` |
| P1 | proxy/lightweight 指标文案改成“轻量近似”，避免展示成完整 OASIS runtime | `frontend/src/components/results/*Result.jsx` |
| P2 | 用 `graph_payload.highlight_nodes/highlight_edges` 驱动图谱高亮 | 后续图谱组件 |
| P3 | suggested followups 接 session 追问接口 | 新聊天/追问组件 |

## 10. 验收标准

前端改完后建议检查：

1. 首屏能直接读到结论，不需要理解工程字段。
2. `friendly` 输出不像实验报告。
3. `expert` 能看到 selected branch 和 metric_source。
4. `judge_friendly` 不显示 benchmark / adapter / diagnostics 字样。
5. proxy 指标不会被展示成 OASIS runtime。
6. 旧的结构化结果、曲线和传播仿真页面仍可打开。
7. 后端没有 `assistant_message` 时，前端能 fallback 到旧结果页。

## 11. 不建议做的事

- 不要把 `benchmark_prediction` 原样作为主答案。
- 不要把 `cogsec_analysis` 原样渲染成大段 JSON。
- 不要把 `proxy` 文案写成 `oasis_runtime`。
- 不要为了好看删掉 `metric_source`。
- 不要把所有机制字段堆到首屏。
- 不要在前端硬编码 judge 文案；应该消费后端 `tone` 输出。
