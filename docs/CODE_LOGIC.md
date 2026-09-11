# MiroFish / CogSec Code Logic

这份代码可以分成两条线理解：

- MiroFish 原始主线：文档上传 -> 本体生成 -> Zep 图谱构建 -> OASIS 多智能体仿真 -> 报告生成 -> 报告对话。
- CogSec 增强线：在报告阶段和独立接口上运行认知安全主判别，把用户画像、诈骗知识图谱、WorldState 和 Fork 反事实分支组织成风险结论。

## 1. 启动入口

后端入口是 `backend/run.py`。它先加载 `backend/app/config.py` 中的环境变量配置，再调用 `app.create_app()` 创建 Flask 应用。

`backend/app/__init__.py` 完成四件事：

- 初始化 Flask、CORS、日志和 JSON 中文输出。
- 注册模拟进程清理逻辑。
- 注册蓝图：
  - `/api/graph`
  - `/api/simulation`
  - `/api/report`
  - `/api/cogsec`
- 提供 `/health` 健康检查。

前端入口是 `frontend/src/main.js`，路由在 `frontend/src/router/index.js`，核心页面路径包括：

- `/`
- `/process/:projectId`
- `/simulation/:simulationId`
- `/simulation/:simulationId/start`
- `/report/:reportId`
- `/interaction/:reportId`

## 2. 图谱构建主链

图谱相关接口在 `backend/app/api/graph.py`。

核心流程：

1. `POST /api/graph/ontology/generate`
   - 接收 PDF、Markdown、TXT 等文档。
   - `FileParser` 提取文本。
   - `TextProcessor` 做预处理。
   - `OntologyGenerator` 调用 LLM 生成实体类型和关系类型。
   - `ProjectManager` 持久化项目、文件、提取文本和本体。

2. `POST /api/graph/build`
   - 根据 `project_id` 找回文本和本体。
   - `TextProcessor.split_text()` 分块。
   - `GraphBuilderService` 在 Zep Cloud 中创建图谱、设置本体、批量写入文本。
   - 后台线程更新 `TaskManager` 任务进度。

3. `GET /api/graph/task/<task_id>` 和 `GET /api/graph/data/<graph_id>`
   - 前端轮询任务状态。
   - 图谱完成后拉取节点和边用于展示。

## 3. 仿真主链

仿真接口在 `backend/app/api/simulation.py`，对应服务在 `backend/app/services/`。

核心流程：

1. `POST /api/simulation/create`
   - 根据项目和图谱创建一次仿真状态。
   - `SimulationManager` 保存 `simulation_id`、`project_id`、`graph_id`、平台开关等信息。

2. `POST /api/simulation/prepare`
   - `ZepEntityReader` 从图谱读取实体。
   - `OasisProfileGenerator` 将实体转换为 OASIS Agent Profile。
   - `SimulationConfigGenerator` 生成平台、轮次、事件、活跃度等仿真配置。
   - 输出 `reddit_profiles.json`、`twitter_profiles.csv`、`simulation_config.json`。

3. `POST /api/simulation/start`
   - `SimulationRunner` 启动 OASIS 脚本。
   - 运行脚本位于 `backend/scripts/`，包括 Reddit、Twitter 和并行平台仿真。
   - 动作日志由 `action_logger.py` 记录，运行状态和平台数据可由接口读取。

4. Interview 相关接口
   - `/api/simulation/interview`
   - `/api/simulation/interview/batch`
   - `/api/simulation/interview/all`
   - 通过 IPC 向运行中的 Agent 发送采访问题。

## 4. 报告主链

报告接口在 `backend/app/api/report.py`，核心类在 `backend/app/services/report_agent.py`。

核心流程：

1. `POST /api/report/generate`
   - 为某个 `simulation_id` 创建报告任务。
   - `ReportAgent` 读取图谱、仿真日志、帖子、评论和 Agent 行为。
   - 分章节生成 Markdown 报告。
   - `ReportManager` 保存报告、章节、进度日志和控制台日志。

2. `GET /api/report/<report_id>`
   - 获取完整报告。

3. `POST /api/report/chat`
   - 让 Report Agent 在已有图谱和仿真结果上进行问答。
   - 可调用图谱搜索、统计等工具。

## 5. CogSec 增强线

CogSec 接口在 `backend/app/api/cogsec.py`，编排服务是 `backend/app/services/cogsec_service.py`。

入口有两个：

- `POST /api/cogsec/analyze`：直接提交场景文本进行分析。
- `GET /api/cogsec/report/<report_id>`：根据已有报告拼接场景上下文，再运行 CogSec 分析。

`CogSecService.analyze_text()` 的顺序是：

1. `T0FastResponder`
   - 在 LLM 之前执行正则红旗检测。
   - 目标是 500ms 内发现屏幕共享、验证码、安全账户、隔离沟通等高危片段。

2. `PrivacySanitizer`
   - 优先使用 Presidio。
   - 不可用时回退到本地正则。
   - 默认策略是 `session_only` 和最小必要。

3. `CognitiveProfileExtractor`
   - 提取 18 维认知画像。
   - 包括时间压力、经济压力、权威服从、稀缺敏感、验证习惯、求助倾向等。
   - 输出 `CognitiveProfile` 和 `PersonaStateVector`。

4. `ThreatKnowledgeRAG`
   - 从诈骗案例库中检索攻击策略。
   - 构建 `RiskGraphBundle`，包含攻击策略链、证据项、画像弱点、资产目标、环境上下文和 Fork 点。

5. `MiroFishRuntime`
   - 初始化 `WorldStateSnapshot`。
   - 选择主 Fork 点，如转账、屏幕共享、验证码泄露、未知 APP 下载等。
   - 推进两个分支：
     - A：Compliance / High-Risk Path
     - B：Verification / Safe Path
   - 比较轨迹差值、可逆性曲线、干预窗口和异常标记。

6. `RiskScorer`
   - 根据分支差值、不可逆损失、证据一致性和画像先验计算最终风险。

7. `CounterfactualReporter`
   - 输出数字孪生摘要、认知弱点链、攻击策略链、Fork 节点、分支对照、不可逆节点和个性化干预建议。

## 6. 前端如何接入

API 封装位于 `frontend/src/api/`。

- `graph.js` 对接图谱接口。
- `simulation.js` 对接仿真接口。
- `report.js` 对接报告接口。
- `cogsec.js` 对接 CogSec 接口。

报告页 `frontend/src/views/ReportView.vue` 默认切到 `cogsec` 视图，并加载：

- `frontend/src/components/cogsec/CogSecWorkbench.vue`

这个工作台分成五屏：

1. 用户数字孪生
2. 攻击-人-环境图谱
3. 双分支反事实推演
4. 风险 / 可逆性曲线
5. 个性化干预处方

## 7. 持久化位置

运行时数据默认写在：

- `backend/uploads/projects`
- `backend/uploads/tasks`
- `backend/uploads/simulations`
- `backend/uploads/reports`

这些属于本地运行数据，不应该提交到 GitHub。

可提交的轻量数据在：

- `data/fraud_cases.json`
- `data/liwc_chinese.json`
- `data/t0_regex_patterns.json`
- `data/cogsec_graph_schema.cypher`
- `data/persona_templates/cogsec_personas.json`

