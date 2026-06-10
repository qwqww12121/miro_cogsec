# MiroCog-Guard 前端

MiroCog-Guard 系统的前端，基于 **Vite + React + Tailwind CSS** 构建。
提供首页智能识别、三个场景分析页和 Benchmark 对比页。

---

## 启动方式

```bash
npm install
npm run dev
```

- 开发服务器默认监听 `http://localhost:3000`。
- `/api/*` 通过 Vite 代理转发到 `http://localhost:5001`，
  因此**需要后端在 `localhost:5001` 运行**。代理配置见 `vite.config.js`。
- 后端启动方式见仓库根目录 `backend/` 下的说明。

构建产物：

```bash
npm run build      # 输出到 dist/
npm run preview    # 本地预览构建结果
```

---

## 目录结构

```
frontend/
├── index.html
├── vite.config.js
├── tailwind.config.js
├── postcss.config.js
└── src/
    ├── main.jsx              # React 入口，挂载 BrowserRouter
    ├── App.jsx               # 路由表
    ├── index.css             # Tailwind 入口 + 通用组件类（card / btn-* / input-base）
    ├── pages/                # 路由级页面，一个文件一个 URL
    │   ├── Home.jsx                       # 首页：智能识别 + 手动选择两栏
    │   ├── BenchmarkPage.jsx              # Benchmark 对比页（当前为 mock）
    │   └── scenarios/
    │       ├── FraudImPage.jsx            # 诈骗即时通讯
    │       ├── PublicOpinionPage.jsx      # 舆情分析
    │       └── EventPropagationPage.jsx   # 事件传播分析
    ├── components/           # 可复用 UI 组件
    │   ├── Navbar.jsx                     # 顶部导航
    │   ├── Breadcrumbs.jsx                # 面包屑
    │   ├── ScenarioCard.jsx               # 场景卡（含 compact 变体）
    │   ├── ScenarioLayout.jsx             # 场景页公用左右分栏布局
    │   ├── IntelligentClassifier.jsx      # 首页智能识别区块
    │   ├── FormField.jsx                  # 表单字段封装（label + 控件）
    │   ├── Section.jsx                    # 标题 + 内容卡
    │   ├── StatTile.jsx                   # 关键指标小卡
    │   ├── Empty.jsx                      # 空状态占位
    │   ├── Icon.jsx                       # 内联 SVG 图标集
    │   └── results/                       # 各场景的结果展示面板
    │       ├── FraudImResult.jsx
    │       ├── PublicOpinionResult.jsx
    │       └── EventPropagationResult.jsx
    ├── api/                  # 后端调用封装
    │   ├── client.js                      # axios 实例（统一错误处理）
    │   ├── cogsec.js                      # POST /api/cogsec/analyze
    │   ├── classify.js                    # POST /api/classify（mock）
    │   └── scenarios.js                   # 三个场景的入口函数，统一拼装 scenario 文本
    └── scenarios/
        └── config.js                      # 场景元数据（名称 / 主题色 / 路径 / 图标）
```

---

## 场景说明

| 场景 | 路径 | 主题色 | 对应后端 |
|---|---|---|---|
| 诈骗即时通讯 `fraud_im` | `/scenario/fraud-im` | 蓝 `#4a90d9` | `POST /api/cogsec/analyze`，scenario_type 取自下拉选择的诈骗类别 |
| 舆情分析 `public_opinion` | `/scenario/public-opinion` | 绿 `#52a882` | `POST /api/cogsec/analyze`，`scenario_type='舆情分析'` |
| 事件传播分析 `event_propagation` | `/scenario/event-propagation` | 黄 `#e8b84b` | `POST /api/cogsec/analyze`，`scenario_type='事件传播分析'` |

三个场景共享同一个 CogSec 引擎入口，靠 `scenario_type` 与拼装出的 `scenario` 文本区分。
每个场景的结果面板都从 `CogSecAnalysisResult` 中按本场景视角抽取字段展示，不构造假数据。

### 首页"智能识别"

粘贴一段文本，调用 `POST /api/classify`（**当前为 mock**），
返回 `{ scenario_type, confidence, reason }` 后给出"已识别为 xxx 场景"的提示，
点"进入分析"会跳转到对应场景页，并通过 `react-router` 的 `location.state.prefillText`
预填进对应输入框（`conversation` / `samples` / `nodes`）。

mock 逻辑写在 `src/api/classify.js`，按关键词命中数排序；
无任何关键词命中时默认返回示例固定结果。

---

## 待对接项

| 项 | 状态 | 说明 |
|---|---|---|
| `POST /api/classify` 智能识别接口 | **未实现，当前为 mock** | mock 在 `src/api/classify.js`，文件顶部已标注 `TODO`；后端实现后取消 mock 区段、启用真实 `client.post('/api/classify', { text })` 调用即可。 |
| `PublicOpinionPage` 分析结果 | 已接 `/api/cogsec/analyze`，**展示字段待后端完善** | 目前结果面板只能从通用 CogSec 输出里提取情绪维度、T0 关键词、攻击话术等代理字段。等后端补充舆情专属字段（情绪占比、KOL 列表、刷量集群等）后，可在 `src/components/results/PublicOpinionResult.jsx` 直接消费。 |
| `EventPropagationPage` 分析结果 | 已接 `/api/cogsec/analyze`，**展示字段待后端完善** | 当前时间线由 `branch_a_log` / `branch_b_log` 累计派生。等后端补充传播专属字段（节点图、扩散曲线、峰值步等）后，可在 `src/components/results/EventPropagationResult.jsx` 直接消费。 |
| `GET /api/benchmark/metrics` | **未实现，BenchmarkPage 当前为 mock** | mock 数据写在 `src/pages/BenchmarkPage.jsx` 顶部 `ROWS` 常量；后端实现后请取消该页 mock，真实调用代码可见 git history。 |
