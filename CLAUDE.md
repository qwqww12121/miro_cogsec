# CLAUDE.md — MiroFish CogSec Project

## 项目概述

`miro_cogsec` 是一个**双系统**平台，两套系统共存于同一代码库：

| 系统 | 定位 | 入口 |
|------|------|------|
| **MiroFish** | 基于 OASIS 的社会仿真平台（上传文档→图谱→多Agent群体推演） | `/process/:projectId` |
| **CogSec** | 实时反诈骗认知安全分析（粘贴对话→主链推演→风险评分→干预处方） | `POST /api/cogsec/analyze` |

用户（CISCN竞赛参赛者，无代码经验）主要关注 **CogSec** 系统，首页已改为 CogSec 风格。

---

## 运行方式

```bash
# 前端 + 后端同时启动
npm run dev

# 单独启动后端
npm run backend   # cd backend && uv run python run.py

# 单独启动前端
npm run frontend  # cd frontend && npm run dev
```

后端运行在 `http://localhost:5000`，前端运行在 `http://localhost:5173`。

**注意**：`uv` 是 Python 包管理器，激活虚拟环境用 `backend/.venv/Scripts/python`。

---

## 技术栈

- **前端**: Vue 3 + Vite + ECharts，代码在 `frontend/src/`
- **后端**: Flask + Blueprint，代码在 `backend/app/`
- **LLM**: 阿里百炼 qwen-plus（OpenAI 兼容格式），配置在 `.env`
- **向量库**: ChromaDB，路径 `../data/chroma_db`（相对于 `backend/` 目录）
- **知识图谱**: Zep Cloud（`ZEP_API_KEY` 已配置）
- **仿真框架**: camel-oasis（用于 MiroFish 系统）

---

## 关键文件地图

### 后端

```
backend/app/
├── api/
│   ├── __init__.py        # Blueprint 注册；graph/sim/report 用 try/except 静默容错
│   ├── cogsec.py          # POST /api/cogsec/analyze（主入口）
│   ├── graph.py           # MiroFish 图谱相关路由（13条）
│   ├── simulation.py      # OASIS 仿真路由（33条）
│   └── report.py          # 报告路由（19条）
├── models/                # ← 关键依赖，解决了所有blueprint的import报错
│   ├── __init__.py
│   ├── project.py         # ProjectManager + Project dataclass（文件持久化）
│   └── task.py            # TaskManager + Task dataclass（文件持久化）
├── modules/
│   ├── mainline_runtime.py   # MiroFishRuntime：Fork A/B 双分支，6条规则（全中文）
│   ├── cf_reporter.py        # CounterfactualReporter：生成反事实报告 + score_comparison
│   ├── cognitive_profiler.py # 18维特征提取（状态/易感/保护三层）
│   ├── risk_scorer.py        # 5因子复合公式 → FinalRisk（0-100）
│   ├── t0_fast_responder.py  # <500ms 关键词匹配
│   ├── privacy_sanitizer.py  # Presidio 敏感实体替换
│   └── threat_rag.py         # ChromaDB 相似案例检索
├── services/
│   ├── cogsec_service.py     # CogSec 主链编排（FSA/CPA/FPR 指标为 Phase-II 占位）
│   └── report_agent.py       # MiroFish 报告生成（ReportManager 参考实现）
└── config.py                 # 从根目录 .env 加载所有配置
```

### 前端

```
frontend/src/
├── views/
│   ├── Home.vue           # ← 已重写为 CogSec 风格（输入模式 + 内联结果模式）
│   └── MainView.vue       # MiroFish 项目处理页（/process/:projectId）
├── components/cogsec/
│   ├── CogSecWorkbench.vue      # 通过 reportId 获取数据展示（旧入口）
│   ├── RiskDashboard.vue        # 四维风险仪表板（雷达图 + 折线图，需 score_comparison）
│   ├── BranchTimeline.vue       # 双分支演化时间线（ECharts）
│   ├── GraphVisualization.vue   # 认知风险关系图（ECharts）
│   ├── MasterStaticDiagram.vue  # 静态总图（仅在 CogSecWorkbench 使用，不出现在各屏幕）
│   └── screens/                 # 10个子屏幕组件（Home.vue 直接引用）
│       ├── DigitalTwinScreen.vue              # 模块1：用户数字孪生
│       ├── RiskGraphScreen.vue                # 模块2：攻击-人-环境风险图谱
│       ├── CounterfactualEvolutionScreen.vue  # 模块3：双分支反事实推演
│       ├── RiskCurveScreen.vue                # 模块4：风险/可逆性曲线
│       ├── InterventionPrescriptionScreen.vue # 模块5：个性化干预处方
│       ├── CognitiveProfileScreen.vue         # 认知画像 + 威胁知识检索
│       ├── RiskScorerScreen.vue               # 风险评分器（含 RiskDashboard）
│       ├── T0FastResponderScreen.vue          # T0 快速响应结果
│       ├── PrivacySanitizerScreen.vue         # 隐私脱敏结果
│       └── CounterfactualReporterScreen.vue   # 反事实报告摘要
├── api/
│   └── cogsec.js          # analyzeCogSec() + getCogSecByReport()
└── router/index.js        # 路由表（无专属 CogSec 结果路由，结果内联在 Home）
```

---

## CogSec 主链流程

```
用户粘贴对话文本
    │
    ├─ T0FastResponder      关键词匹配，<500ms，返回场景类型和初始风险
    ├─ PrivacySanitizer     Presidio 替换手机号/身份证等敏感实体
    ├─ CognitiveProfiler    18维特征向量（状态6 + 易感6 + 保护6）
    ├─ ThreatKnowledgeRAG   ChromaDB 检索相似诈骗案例（10条案例库）
    ├─ MiroFishRuntime      Fork A（顺从）vs Fork B（核实干预），各6步
    ├─ RiskScorer           FinalRisk = (5因子乘积)^0.55 × 100
    └─ CounterfactualReport 干预处方 + 最优行动窗口 + score_comparison（含四维评分）
```

**风险等级**: LOW<25 / MEDIUM<50 / HIGH<75 / CRITICAL≥75

**6条 Fork 规则**（触发分支推演）:
- transfer_money(0.96), verification_code(0.92), screen_share(0.88)
- unknown_app_download(0.83), fake_official_verification(0.80), social_isolation(0.74)

---

## score_comparison 数据结构

`counterfactual_report.score_comparison` 是 `RiskDashboard` 的数据来源：

```json
{
  "final_risk": 62.3,
  "risk_breakdown": { ... },
  "branch_a_final": { "CHS": 42.1, "ASS": 18.5, "SSS": 24.0, "EES": 58.3 },
  "branch_b_final": { "CHS": 87.2, "ASS": 81.0, "SSS": 68.5, "EES": 12.1 },
  "timeline_a": [ { "t": 0, "CHS": ..., "ASS": ..., "SSS": ..., "EES": ..., "posterior_risk": ..., "reversibility": ..., "cognitive_mode": ... }, ... ],
  "timeline_b": [ ... ],
  "reversibility_curve": [ ... ]
}
```

`branch_a_final`/`branch_b_final` 由 `cf_reporter.py` 的 `_synth_scores()` 从 world_state 末态合成。

---

## 当前完成状态

### 已完成
- [x] CogSec 主链全模块（T0 → Privacy → Profiler → RAG → Fork → Risk → Report）
- [x] `backend/app/models/`（ProjectManager + TaskManager，文件持久化）
- [x] MiroFish 图谱/仿真/报告 API（图谱13条 + 仿真33条 + 报告19条路由均已可加载）
- [x] 前端 CogSec 组件体系（10个屏幕 + Workbench + RiskDashboard + BranchTimeline）
- [x] 首页重写为 CogSec 风格（输入→分析→内联结果工作台）
- [x] 前端全中文化（所有 eyebrow 标签、向量字段名、维度字段名均有中文映射）
- [x] 后端 Fork A/B 行动模板全中文（`mainline_runtime.py` 所有 label 方法）
- [x] `cf_reporter.py` 生成 `branch_a_final`/`branch_b_final` 和带 `t` 索引的时间线
- [x] `.env` 数据路径修正（`../data/` 相对于 `backend/` 目录）
- [x] `data/fraud_cases.json` 扩展至 10 条案例（22个攻击策略）

### 待完成（优先级顺序）
- [ ] **P1**: FSA/CPA/FPR 三项评估指标实现（`cogsec_service.py` 168-171 行，当前为硬编码占位）
- [ ] **P1**: Zep 知识图谱注入 CogSec 主链（`threat_rag.py` 目前仅用 ChromaDB）
- [ ] **P1**: OASIS 仿真事件作为 CogSec EvidenceItems 输入
- [ ] **P2**: README 更新
- [ ] **P3**: 本地 Gemma 模型配置（`.env` 中 `COGSEC_USE_LOCAL_GEMMA=false`，需下载模型）

---

## 重要 Gotchas

1. **`api/__init__.py` 静默容错**: graph/simulation/report 三个 blueprint 用 `try/except` 包裹，import 失败时不报错只是路由不注册。如果这些路由消失，优先检查 `models/` 目录是否存在。

2. **`models/` 目录是关键依赖**: graph.py / simulation.py / report.py 都从 `..models.project` 和 `..models.task` 导入，`models/` 丢失会导致三个 blueprint 静默失效。

3. **`.env` 敏感配置已填写**: `LLM_API_KEY`（阿里百炼 qwen-plus）和 `ZEP_API_KEY` 已配置，不要覆盖。`LLM_BOOST_*` 字段留空时不能出现在 `.env`（会导致 URL 解析错误）。数据路径须用 `../data/`（相对于 `backend/` 运行目录），不能用 `./data/`。

4. **本地 Gemma 未启用**: `COGSEC_USE_LOCAL_GEMMA=false`，系统回退到启发式模式。

5. **首页 Home.vue 双模式**: `mode='input'`（默认）→ 输入框；`mode='result'`→ 内联工作台。结果模式直接从 `analyzeCogSec()` 响应拿数据，不走 `getCogSecByReport()`。

6. **文件持久化路径**: 项目数据在 `uploads/projects/{project_id}/meta.json`，任务数据在 `uploads/tasks/{task_id}.json`，报告在 `uploads/reports/{report_id}/`。

7. **`MasterStaticDiagram` 仅在旧 Workbench 使用**: 不要将其添加到任何屏幕组件（`screens/` 目录下）中，已从 `RiskGraphScreen.vue` 移除。

8. **`score_comparison` 字段来源**: `RiskDashboard` 需要的 `branch_a_final`/`branch_b_final` 和 `timeline_{a,b}` 由 `cf_reporter.py:_synth_scores()` 和 `_ws_to_timeline()` 从 world_state 合成，不是真正的 RiskScorer 滚动评分。Phase-II 可替换为真实评分。

---

## 设计规范（前端）

```css
--black:  #0f172a    /* 主深色 */
--orange: #f97316    /* 强调色 */
--teal:   #0f766e    /* 主题色 */
--teal-light: #5eead4 /* 导航高亮 */
--font-mono: 'JetBrains Mono', monospace
--font-sans: 'Space Grotesk', 'Noto Sans SC', system-ui
```

- 深色 navbar（`rgba(15,23,42,0.9)`）+ 毛玻璃效果
- 白色卡片 + 浅灰背景（`#f4f7fb`）
- 单文件 scoped 样式，不使用全局 CSS 框架
