# CogSec-MIROFISH Mainline Refactor

## 1. 新的系统总架构说明

### 1.1 总体定位

本项目重构后的定位不再是“MIRO-FISH 主线 + CogSec 旁路检测”，而是：

- `MIRO-FISH` 作为主判别运行时
- `CogSec` 作为认知安全编排中枢
- `ZEP + CognitiveProfiler` 作为数字孪生初始化层
- `ThreatKnowledgeRAG` 作为攻击约束与风险图谱构建层
- `WorldState + Fork` 作为最终风险生成机制
- `CounterfactualReporter` 作为主链结果出口
- `T0FastResponder` 只做毫秒级护栏，不作为最终结论来源

### 1.2 主链分层

1. `Input Layer`
   接收 `Text / OCR / ASR / context`，先进入 `PrivacySanitizer`
2. `Persona Initialization Layer`
   `CognitiveProfileExtractor` 先生成 18 维画像，再映射为 `persona_state_vector`
3. `Threat Graph Construction Layer`
   `ThreatKnowledgeRAG.build_risk_graph_bundle()` 生成 Threat-Persona-Context 图谱
4. `MIRO-FISH Runtime Layer`
   `MiroFishRuntime.initialize_world_state()` 初始化 `WorldState`
5. `Fork-based Counterfactual Inference Layer`
   在高危不可逆节点触发 `Fork`
6. `Risk Scoring Layer`
   `RiskScorer.evaluate_counterfactual()` 只基于分支差值聚合最终风险
7. `Reporting & Intervention Layer`
   `CounterfactualReporter` 输出数字孪生、分支对照和干预处方

## 2. 主流程时序说明

### 2.1 Runtime Sequence

1. 输入文本进入 `PrivacySanitizer.sanitize_with_retry()`
2. 若脱敏后仍检出 PII，则自动重试一次；仍失败则中断
3. `T0FastResponder.scan()` 返回亚秒级护栏结果
4. `CognitiveProfileExtractor.extract()` 生成 18 维画像
5. `profile.to_persona_state_vector()` 生成运行时向量
6. `ThreatKnowledgeRAG.build_risk_graph_bundle()` 输出 `risk_graph_bundle`
7. `MiroFishRuntime.initialize_world_state()` 生成 `WorldStateSnapshot(step=0)`
8. `MiroFishRuntime.select_primary_fork()` 选择主 Fork 节点
9. 运行 `Branch A / Branch B` 多步反事实推演
10. `RiskScorer.evaluate_counterfactual()` 聚合最终风险
11. `CounterfactualReporter.generate_report()` 输出主链报告
12. 前端五屏消费同一份主链结果对象

### 2.2 System 1 / System 2 切换

- 默认进入 `System 2`
- 当 `time_pressure > 7` 且 `emotional_volatility > 7` 时强制切换 `System 1`
- 当 `verification_habit >= 6` 且 `decision_delay >= 6` 时允许回到 `System 2`

## 3. 核心模块职责表

| 模块 | 重构后职责 | 当前状态 |
| --- | --- | --- |
| `PrivacySanitizer` | 脱敏、最小必要、`session_only`、PII 泄漏重试 | 已实现 |
| `T0FastResponder` | 毫秒级护栏与红旗规则命中 | 已实现 |
| `CognitiveProfileExtractor` | 18 维画像抽取 | 已实现 |
| `PersonaStateVector` | 数字孪生运行时向量 | 新增 |
| `ThreatKnowledgeRAG` | 风险图谱构建、攻击策略链、Fork 节点候选 | 已重构 |
| `MiroFishRuntime` | `WorldState` 初始化、Fork 选择、Branch A/B 推演 | 新增 |
| `RiskScorer.evaluate_counterfactual` | 基于分支差值聚合最终风险 | 新增 |
| `CounterfactualReporter` | 输出数字孪生摘要、弱点链、攻击链、分支对照、干预处方 | 已重构 |
| `CogSecService` | 编排主链并向前端返回统一结果结构 | 已重构 |
| `CogSecWorkbench` | 五屏主链展示 | 已重构 |

## 4. 新数据结构定义

### 4.1 `persona_state_vector`

```json
{
  "authority_compliance": 8.6,
  "time_pressure_sensitivity": 8.1,
  "financial_stress": 7.4,
  "loss_aversion": 7.8,
  "fomo_susceptibility": 6.9,
  "verification_habit": 3.4,
  "help_seeking_tendency": 3.1,
  "analytic_control": 4.2,
  "emotional_volatility": 8.2,
  "digital_trust_boundary": 3.8,
  "asset_sensitivity": 6.4,
  "risk_recovery_awareness": 4.1,
  "confidence_level": 0.72,
  "system1_bias": 8.3,
  "system2_control": 3.9,
  "cognitive_mode": "SYSTEM_1",
  "switch_policy": {},
  "storage_policy": {
    "default": "session_only",
    "persistent_opt_in_required": true
  }
}
```

### 4.2 `risk_graph_bundle`

```json
{
  "schema_version": "cogsec.mainline.v1",
  "threat_template_nodes": [],
  "evidence_items": [],
  "persuasion_principles": [],
  "persona_weakness_hits": [],
  "asset_targets": [],
  "environment_context": {},
  "fork_points": [],
  "nodes": [],
  "links": [],
  "categories": [],
  "consistency_score": 0.81,
  "hallucination_rollback": false
}
```

### 4.3 `world_state_snapshot`

```json
{
  "step": 2,
  "stage": "fork_execution",
  "action": "Primary Agent transfers funds to a fake safe account",
  "trust_score": 74.2,
  "cognitive_mode": "SYSTEM_1",
  "asset_exposure": 0.41,
  "intervention_window": 0.28,
  "posterior_risk": 0.79,
  "reversibility": 0.33,
  "evidence_hits": ["evidence:case_a"],
  "persona_hits": ["authority_compliance", "time_pressure_sensitivity"]
}
```

### 4.4 `branch_trace_step`

```json
{
  "branch": "A",
  "step": 3,
  "action": "Primary Agent transfers funds to a fake safe account",
  "action_type": "transfer_money",
  "fork_point_type": "transfer_money",
  "world_state": {},
  "posterior_updates": {},
  "evidence_refs": [],
  "persona_hit_chain": [],
  "irreversible": true,
  "audit_flag": false
}
```

### 4.5 `fork_comparison_result`

```json
{
  "fork_point_type": "transfer_money",
  "fork_node_id": "fork:transfer_money",
  "branch_a_state_trace": [],
  "branch_b_state_trace": [],
  "posterior_updates": [],
  "reversibility_curve": [],
  "persona_hit_chain": [],
  "evidence_graph_consistency": 0.84,
  "trajectory_gap": 0.31,
  "irreversibility_loss": 0.46,
  "low_discriminability": false,
  "anomaly_flags": [],
  "best_intervention_window": {
    "open_step": 2,
    "close_step": 3,
    "label": "verification intervention window"
  }
}
```

### 4.6 `intervention_prescription`

```json
{
  "title": "在 transfer_money 节点前强制二次核验",
  "priority": 1,
  "target_failure_node": "transfer_money",
  "trigger_step": 2,
  "window_open_step": 2,
  "window_close_step": 3,
  "rationale": "最佳干预窗口出现在不可逆操作前。",
  "recommended_actions": [
    "切换官方回拨",
    "暂停 10-30 分钟",
    "拒绝继续提供资金/验证码"
  ],
  "channel": "in_app",
  "expected_effect": "阻断进入高危路径",
  "fallback": "默认终止当前交互"
}
```

## 5. 接口改造建议

### 5.1 保持兼容的最小改造

- `POST /api/cogsec/analyze`
- `GET /api/cogsec/report/<report_id>`

保持接口路径不变，但返回结构改成主链优先：

```json
{
  "profile": {},
  "persona_state_vector": {},
  "risk_graph_bundle": {},
  "world_state_snapshot": {},
  "fork_comparison": {},
  "counterfactual_report": {},
  "intervention_prescriptions": [],
  "t0_fast_response": {},
  "sanitization": {},
  "metrics": {},
  "anomalies": []
}
```

### 5.2 建议新增的显式接口

- `POST /api/cogsec/mainline/analyze`
  直接返回主链运行时对象
- `GET /api/cogsec/diagram/master`
  返回静态总图 SVG 地址或元数据
- `POST /api/cogsec/evaluate`
  读取 benchmark JSON 后运行验收阈值检查

## 6. 前端页面改造建议

### 6.1 五屏主链展示

1. `DigitalTwinScreen`
   展示 `persona_state_vector`、System 1/2、隐私策略、T0 与脱敏辅助状态
2. `RiskGraphScreen`
   展示 `risk_graph_bundle` 的关系图、证据项、Fork 节点和静态总图
3. `CounterfactualEvolutionScreen`
   展示 `BranchTimeline`、每一步的 `WorldState`
4. `RiskCurveScreen`
   展示 `posterior_risk / reversibility` 双曲线和风险因子分解
5. `InterventionPrescriptionScreen`
   展示失败节点绑定的处方、最佳干预窗口、稳定/新增/Phase-II 边界

### 6.2 UI 叙事原则

- 不再以“风险分 + 文本解释”为中心
- 以“演化过程 + 分叉证据 + 失败节点 + 处方”作为主视觉
- `T0 / Privacy` 退为辅助护栏，不抢主链叙事

## 7. 静态总图设计说明

### 7.1 文件

- `frontend/public/cogsec-mirofish-mainline-diagram.svg`
- `frontend/src/components/cogsec/MasterStaticDiagram.vue`

### 7.2 四区布局

1. 左侧
   `Text / OCR / ASR -> PrivacySanitizer -> 18D Persona -> persona_state_vector -> System 1/2`
2. 中央
   `Primary Agent / Adversary Agent / Context Agent / Audit Agent / Evidence / Weakness / Asset / Threat Template / WorldState / Fork`
3. 右侧
   `Branch A` 红色高危演化，`Branch B` 绿色安全演化
4. 下方
   `Posterior Risk Curve / Reversibility Curve / Key Hit Chain / Intervention Prescription`

### 7.3 必须表达的四个信息

- 风险不是一句话判出来，而是在“人-攻击-环境”关系里长出来
- 同一攻击面对不同数字孪生会形成不同轨迹
- 关键是“哪一步从可逆转为不可逆”
- 系统不是事后解释，而是在 Fork 后预测后果并插入干预

## 8. README 中“创新点”与“系统流程”重写稿

### 8.1 创新点

`CogSec-MIROFISH` 不是更复杂的大模型检测器，而是一个基于 `MIRO-FISH` 多智能体反事实推演的人因认知安全预测系统。

它的核心创新不在于把文本送进大模型后输出一个风险标签，而在于：

- 先把用户当前状态建模为可运行的 `persona_state_vector`
- 再把攻击、人、环境、证据构造成 `risk_graph_bundle`
- 然后把这些对象送入 `MIRO-FISH` 主判别运行时形成 `WorldState`
- 在关键不可逆节点触发 `Fork`
- 通过 `Branch A / Branch B` 的轨迹差值推导最终风险
- 最后把干预建议绑定到失败节点，而不是绑定到一个泛化标签

因此，系统输出的是“如果继续配合将如何演化，如果转入核验将如何收敛”的后果预测，而不是“文本看起来是否可疑”的静态判断。

### 8.2 系统流程

1. 输入文本、OCR 或 ASR 内容先进入 `PrivacySanitizer`
2. `T0FastResponder` 提供毫秒级红旗护栏
3. `CognitiveProfileExtractor` 输出 18 维画像并映射为 `persona_state_vector`
4. `ThreatKnowledgeRAG` 构建 `risk_graph_bundle`
5. `MIRO-FISH Runtime` 用 `persona_state_vector + risk_graph_bundle + input` 初始化 `WorldState`
6. 在转账、共享屏幕、验证码泄露、下载未知 APP、脱离亲友沟通、伪官方核验等节点触发 `Fork`
7. 系统推进 `Branch A / Branch B` 多步演化
8. `RiskScorer` 以分支差值聚合最终风险
9. `CounterfactualReporter` 输出数字孪生摘要、认知弱点链、攻击链、分支对照、不可逆节点和个性化处方

## 9. 答辩用 1 分钟创新点讲稿

我们这套系统的关键，不是把诈骗文本送进大模型后做一个分类，而是把 `MIRO-FISH` 的演化能力重新放回主判别链。

在我们的主链里，系统先根据用户当前输入和上下文构建 18 维认知画像，再压缩成一个可运行的 `persona_state_vector`，把用户建成数字孪生。然后系统会把攻击话术、环境压力、证据项和资产目标构造成 `risk_graph_bundle`，送入 `MIRO-FISH Runtime` 初始化 `WorldState`。

真正的判别发生在 Fork 之后。比如一旦出现转账、验证码、屏幕共享这类关键节点，系统会同时推进一条高危配合路径和一条安全核验路径。最终风险不是来自单段文本，而是来自两条分支在 `posterior_risk`、`asset_exposure` 和 `reversibility` 上的轨迹差值。

所以我们做的不是“检测是否可疑”，而是“预测如果继续配合会造成什么后果、在哪个窗口还能被拦下来”。这也是它区别于传统大模型检测器的核心创新。

## 10. 可执行的重构任务清单

### P0

1. 让 `CogSecService` 主链完全基于 `WorldState + ForkComparison`
2. 完成五屏前端主链展示
3. 将 README 首页改成“主链预测系统”叙事
4. 把异常矩阵加入自动化测试
5. 固化静态总图 SVG 资产

### P1

1. 将 `ZEP` 的实体和边直接注入 `risk_graph_bundle`
2. 支持从模拟 timeline 中抽取真实行为事件作为 EvidenceItem
3. 在 `RiskScorer` 中加入更多 `fork_point_type` 专属权重
4. 为 `CounterfactualReporter` 增加更细的失败节点模板

### P2

1. 多 Fork 并行搜索与更长时间跨度推演
2. Context Agent / Audit Agent 进入实时多智能体循环
3. 评测脚本接入真实 benchmark 数据集，输出 `FSA / CPA / EAR / FPR`
4. 生成更强的海报与论文图版式
