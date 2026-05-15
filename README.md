<div align="center">

<img src="./static/image/MiroFish_logo_compressed.jpeg" alt="MiroFish Logo" width="75%"/>

简洁通用的群体智能引擎，预测万物
</br>
<em>A Simple and Universal Swarm Intelligence Engine, Predicting Anything</em>

[English](./README-EN.md) | [中文文档](./README.md)

</div>

## 项目定位

**CogSec** (Cognitive Defense X)，一个基于 **MIRO-FISH 多智能体反事实推演**的人因认知安全预测平台。

与传统文本检测不同，本系统的最终风险判断不来自单段 `scenario_text`，而是来自完整的认知安全主链：

- **用户数字孪生初始化** — 18 维认知画像 → `persona_state_vector`
- **Threat-Persona-Context 风险图谱** — 攻击策略链 × 人因弱点 × 环境约束
- **WorldState 主判别运行时** — MIRO-FISH 驱动的状态演化引擎
- **双分支反事实推演** — 在关键不可逆节点 Fork，同时推进高危/安全两条路径
- **基于分支差值的后果预测与干预处方** — 最终风险来自轨迹差值，而非文本分类

主链角色划分：

- `MIRO-FISH` — 主判别运行时
- `CogSec` — 认知安全编排中枢
- `T0FastResponder` — 毫秒级护栏，不负责最终结论
- `CounterfactualReporter` — 主链结果出口

## 项目主线

### 1. 新主链总览

当前系统的主流程为：

`Input -> PrivacySanitizer -> PersonaStateVector -> RiskGraphBundle -> WorldState -> Fork A/B -> Counterfactual Risk -> Intervention`

与传统文本检测不同，本系统的最终风险不直接来自 `scenario_text`，而是来自：

- `persona_state_vector`
- `risk_graph_bundle`
- `WorldState` 演化
- `Branch A / Branch B` 双分支轨迹差值
- `reversibility / intervention_window / evidence_consistency`

### 2. Input Layer

输入层接收：

- `Text`
- `OCR`
- `ASR`
- 用户上下文与问卷信号

在进入任何画像或推演前，统一先经过：

- `backend/app/modules/privacy_sanitizer.py`
- `backend/app/modules/t0_fast_responder.py`

其中：

- `PrivacySanitizer` 负责本地脱敏、最小必要、`session_only` 默认策略
- `T0FastResponder` 负责 `< 500ms` 的红旗护栏与早期拦截

### 3. Persona Initialization Layer

这条线负责把 18 维画像真正转成可运行的数字孪生向量，而不是只输出解释性标签。

核心模块：

- `backend/app/modules/cognitive_profiler.py`
- `backend/app/modules/runtime_schema.py`

主产物：

- `CognitiveProfile`
- `persona_state_vector`
- `System 1 / System 2` 切换策略

运行时向量至少包含：

- `authority_compliance`
- `time_pressure_sensitivity`
- `financial_stress`
- `loss_aversion`
- `fomo_susceptibility`
- `verification_habit`
- `help_seeking_tendency`
- `analytic_control`
- `emotional_volatility`
- `digital_trust_boundary`
- `asset_sensitivity`
- `risk_recovery_awareness`
- `confidence_level`

### 4. Threat Graph Construction Layer

这条线由 `ThreatKnowledgeRAG` 负责，不再只是“防幻觉检索器”，而是主链风险图谱构建器。

核心模块：

- `backend/app/modules/threat_rag.py`

主产物：

- `risk_graph_bundle`
- `threat_template_nodes`
- `evidence_items`
- `persona_weakness_hits`
- `asset_targets`
- `environment_context`
- `fork_points`

核心关系至少包括：

- `TRUST_IN`
- `PRESSURED_BY`
- `MATCHES_WEAKNESS`
- `ESCALATES_TO`
- `THREATENS_ASSET`
- `MITIGATED_BY`
- `FORK_AT`

### 5. MIRO-FISH Runtime Layer

这条线现在是主判别核心。

核心模块：

- `backend/app/modules/mainline_runtime.py`
- `backend/app/modules/runtime_schema.py`
- `backend/app/modules/risk_scorer.py`

主状态对象：

- `WorldStateSnapshot`

主状态字段至少包括：

- `trust_score`
- `cognitive_mode`
- `asset_exposure`
- `intervention_window`
- `posterior_risk`
- `reversibility`
- `stage`
- `evidence_hits`

### 6. Fork-based Counterfactual Inference Layer

在以下关键不可逆节点会显式触发 `Fork`：

- 转账
- 屏幕共享
- 验证码泄露
- 下载不明 APP
- 脱离亲友沟通
- 伪官方核验流程

Fork 后必须生成：

- `Branch A = Compliance / High-Risk Path`
- `Branch B = Verification / Safe Path`

两个分支都会推进多个 step，并输出 `branch_trace_step + world_state_snapshot`。

### 7. Reporting & Intervention Layer

结果层的目标不再是“普通检测说明”，而是：

- 用户数字孪生摘要
- 本次命中的认知弱点链
- 攻击策略链
- Fork 节点
- Branch A / Branch B 对照
- 不可逆节点
- 最佳干预窗口
- 个性化防御建议

核心模块：

- `backend/app/modules/cf_reporter.py`
- `backend/app/services/cogsec_service.py`
- `frontend/src/components/cogsec/CogSecWorkbench.vue`

### 8. 创新点

本项目的创新点不在于“把诈骗文本送进大模型后做分类”，而在于：

- 先把用户建成可运行数字孪生
- 再把人、攻击、环境、证据构造成风险图谱
- 让 `MIRO-FISH` 运行时在 `Fork` 后推进双分支演化
- 让最终风险来自分支轨迹差值而不是单段文本
- 让干预建议绑定失败节点而不是笼统风险标签

### 9. 验收指标

以下指标已纳入主链验收口径：

- `T0 latency < 500ms`
- `End-to-end inference < 30s`
- `FSA > 70%`
- `CPA > 60%`
- `EWT > 2 steps`
- `FPR < 15%`
- `CAL < 0.2`
- `EAR > 65%`

评测脚本：

- `scripts/evaluate_cogsec_mainline.py`

## 主线结构图

### 前端主线

1. `Home`
2. `/process/:projectId`
3. `/simulation/:simulationId`
4. `/simulation/:simulationId/start`
5. `/report/:reportId`
6. `/interaction/:reportId`

### 后端主线

1. `POST /api/graph/ontology/generate`
2. `POST /api/graph/build`
3. `POST /api/simulation/create`
4. `POST /api/simulation/prepare`
5. `POST /api/simulation/start`
6. `POST /api/report/generate`
7. `POST /api/report/chat`
8. `GET /api/cogsec/report/<report_id>` 触发 MIRO-FISH 主判别运行时并返回五屏主链结果

## 仓库边界

当前仓库里，以下内容属于**正式主线**：

- `backend/app/api/graph.py`
- `backend/app/api/simulation.py`
- `backend/app/api/report.py`
- `backend/app/api/cogsec.py`
- `frontend/src/views/*`
- `frontend/src/components/Step*.vue`
- `frontend/src/components/cogsec/*`

以下内容更适合作为**验证、演示或交付辅助**，不建议当成主线对外介绍：

- `backend/run_cogsec_demo.py`
- `backend/templates/cogsec_demo.html`
- `backend/static/cogsec_demo.css`
- `backend/static/cogsec_demo.js`
- `backend/static/cogsec_demo_static.html`
- `tests/`
- `scripts/`

## 快速开始

### 前置要求

| 工具 | 版本要求 | 说明 |
|------|---------|------|
| Node.js | 18+ | 前端运行环境 |
| Python | >=3.11, <=3.12 | 后端运行环境 |
| uv | 最新版 | Python 包管理器 |

### 1. 配置环境变量

```bash
cp .env.example .env
```

最少需要补齐：

```env
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL_NAME=qwen-plus
ZEP_API_KEY=your_zep_api_key
```

如果启用本地 CogSec 模型，可补充：

```env
COGSEC_USE_LOCAL_GEMMA=true
COGSEC_LOCAL_MODEL_PATH=./models/google--gemma-4-E2B-it
CHROMA_PATH=./data/chroma_db
FRAUD_CASE_DB_PATH=./data/fraud_cases.json
```

### 2. 安装依赖

```bash
npm run setup:all
```

或者分步执行：

```bash
npm run setup
npm run setup:backend
```

### 3. 启动主线

```bash
npm run dev
```

服务地址：

- 前端：`http://localhost:3000`
- 后端：`http://localhost:5001`

单独启动：

```bash
npm run backend
npm run frontend
```

## CogSec 使用方式

完成原始主线的图谱、模拟和报告后：

1. 打开 `/report/:reportId`
2. 切换到顶部 `认知安全`
3. 查看 T0 响应、隐私脱敏、认知画像、风险打分和反事实报告

也可以直接调接口：

```bash
POST /api/cogsec/analyze
GET /api/cogsec/report/<report_id>
```

## 最小 Demo

如果你只想验证 CogSec 最小链路，而不先跑完整主线，可以使用：

```bash
cd backend
python run_cogsec_demo.py
```

访问：

- `http://127.0.0.1:5052/demo/cogsec`
- `http://127.0.0.1:5052/health`

注意：这条是**验证线**，不是仓库的正式业务主线。

## 测试

```bash
python -m pytest tests/test_cognitive_profiler.py
python -m pytest tests/test_threat_rag.py
python -m pytest tests/test_risk_scorer.py
python -m pytest tests/test_cf_reporter.py
python -m pytest tests
```

## 当前进度

本仓库当前实现了 **第二层（个体认知反事实引擎）** 的全部代码，以及原始 MiroFish 仿真主线。

### 已完成

**CogSec 认知安全引擎（第二层）：**

| 模块 | 状态 |
|------|------|
| `PrivacySanitizer` — 本地脱敏、最小必要、session_only | ✅ |
| `T0FastResponder` — <500ms 红旗护栏 | ✅ |
| `CognitiveProfileExtractor` — 18 维画像抽取 | ✅ |
| `PersonaStateVector` — 数字孪生运行时向量 | ✅ |
| `ThreatKnowledgeRAG` — 风险图谱构建、攻击策略链、Fork 节点候选 | ✅ |
| `MiroFishRuntime` — WorldState 初始化、Fork 选择、Branch A/B 推演 | ✅ |
| `RiskScorer` — 基于分支差值的反事实风险聚合 | ✅ |
| `CounterfactualReporter` — 数字孪生摘要、弱点链、分支对照、干预处方 | ✅ |
| `CogSecService` — 主链编排与统一结果结构 | ✅ |
| `CogSecWorkbench` — 前端五屏主链展示 (10 个 Vue 组件) | ✅ |
| 核心模块单元测试（profiler / threat_rag / risk_scorer / cf_reporter） | ✅ |
| 最小 Demo 验证链路 (`run_cogsec_demo.py`) | ✅ |

**MiroFish 原始仿真主线：**

| 模块 | 状态 |
|------|------|
| 图谱构建（本体生成 → Zep 图谱 → 节点/边展示） | ✅ |
| 多智能体仿真（OASIS 引擎 → 多平台模拟 → 时间线/访谈） | ✅ |
| 报告生成与深度交互（分章节流式报告 → Agent 问答） | ✅ |

### CogSec API 当前状态

| 端点 | 状态 |
|------|------|
| `POST /api/cogsec/analyze` | ✅ 已实现 |
| `GET /api/cogsec/report/<report_id>` | ✅ 已实现 |
| `POST /api/cogsec/mainline/analyze` | ❌ 未实现 |
| `GET /api/cogsec/diagram/master` | ❌ 未实现 |
| `POST /api/cogsec/evaluate` | ❌ 未实现 |

### 待完成：基于双层反事实推演的多模态认知攻击传播归因与干预平台

完整方案见 `D:\mirofish\方向调研\5_2调研.md`。当前已实现的 CogSec 引擎是**第二层（个体认知反事实）**，下一步需要构建**第一层（宏观传播反事实）**并打通两层之间的接口。

**P0 — 第一层：宏观传播反事实（核心新增）：**

- [ ] 五类平台模板系统（知乎型/小红书型/微博型/短视频型/私域群聊）
- [ ] 多模态叙事基因解析器（主张、证据形式、情绪框架、权威符号、行动号召、视觉触发物）
- [ ] 宏观反事实实验自动化（Agent 移除/平台移除/边阻断/叙事元素替换/视觉元素扰动 → 重新仿真 → 比较覆盖率变化）
- [ ] Agent 认知状态参数化（可信源偏好、情绪阈值、从众倾向、视觉敏感度、辟谣接受度等）
- [ ] 视觉元素扰动模块（去红章、模糊头像、删时间戳、换配色）

**P1 — 两层打通与系统集成：**

- [ ] 第一层→第二层 Agent 锁定与传递机制（Top-K 关键传播者 + 脆弱人群段代表性样本）
- [ ] 第二层→第一层策略反馈闭环（个体处方按认知画像聚合 → 差异化策略库 → 注入第一层蓝队参数）
- [ ] CogSec API 补全（`mainline/analyze`、`diagram/master`、`evaluate`）
- [ ] 前端宏观传播面板（新）+ 两层联动交互 + 策略对比面板

**P2 — 攻击场景与评测矩阵（来源：`D:\mirofish\方向调研\调研报告.md`）：**

- [ ] MCP 工具投毒场景（经多 Agent 视角改造 → 跨 Agent 信任链污染）
- [ ] 间接提示注入场景（注入源 → Agent A → Agent B → 终端影响传播链）
- [ ] 权限过度分析子模块（攻击阻断率 vs 功能损耗率的帕累托前沿）
- [ ] 最优人工介入点求解（MDP 建模 + 贪婪介入点选择 + 告警疲劳鲁棒性）
- [ ] Benchmark 评测脚本接入（FSA / CPA / EAR / FPR / 归因有效性 / 第二层增益）

**P3 — Demo 与答辩材料：**

- [ ] 主 Demo：校园突发事件假通知两层治理（GPT Image 2 级别假截图）
- [ ] 核心实验五对照组（无干预/检测后辟谣/仅宏观/静态中心性/宏观+CogSec）
- [ ] 答辩 PPT 与视频材料
- [ ] 海报与论文级图表（双层架构图、反事实归因对比图、干预窗口曲线）

## 致谢

MiroFish 的仿真引擎由 **[OASIS](https://github.com/camel-ai/oasis)** 驱动。

感谢原始 MiroFish 团队与 CAMEL-AI 团队的开源贡献。
