# Miro-CogSec

基于 MiroFish 多智能体推演主链改造的认知安全反事实推演平台。

本仓库不是原版 MiroFish 的完整搬运版，而是保留了运行 CogSec 所必需的 MiroFish 图谱、仿真、报告组件，并删除了运行截图、宣传素材、PPT 交付文件、本地模型权重、依赖目录和运行日志后的独立项目结构。

## 项目定位

Miro-CogSec 面向诈骗、认知攻击、舆情诱导等人因安全场景。它的核心思想是：不要只把一段文本送进模型做分类，而是先构造用户数字孪生和攻击-人-环境风险图谱，再用 MiroFish 风格的 WorldState 运行时进行 Fork A/B 反事实推演，最后根据两条路径的轨迹差值生成风险结论与干预处方。

主链可以概括为：

```text
Input
  -> PrivacySanitizer
  -> T0FastResponder
  -> CognitiveProfile / PersonaStateVector
  -> Threat-Persona-Context RiskGraphBundle
  -> MiroFishRuntime WorldState
  -> Fork A/B Counterfactual Evolution
  -> RiskScorer
  -> CounterfactualReporter
  -> Intervention Prescription
```

## 仓库结构

```text
backend/
  app/
    api/                 # graph / simulation / report / cogsec API
    modules/             # CogSec 核心算法模块
    services/            # MiroFish 必要服务与 CogSec 编排服务
    utils/               # LLM、日志、文件解析、Zep 分页等工具
  scripts/               # OASIS 仿真和 CogSec 最小链路脚本
  run.py                 # 完整后端入口
  run_cogsec_demo.py     # CogSec 最小 Demo 入口

frontend/
  src/
    views/               # MiroFish 主流程页面
    components/          # 图谱、仿真、报告组件
    components/cogsec/   # CogSec 五屏工作台
    api/                 # 前端 API 封装

data/
  fraud_cases.json       # 轻量诈骗案例库
  liwc_chinese.json      # 简化中文 LIWC 词典
  t0_regex_patterns.json # T0 快速红旗规则
  cogsec_graph_schema.cypher

docs/
  CODE_LOGIC.md
  COGSEC_MIROFISH_MAINLINE_REFACTOR.md

tests/
  test_*.py
```

## 保留了哪些 MiroFish 组件

为保证项目可以独立跑通，仓库保留了以下原 MiroFish 必要运行组件：

- 文档上传、本体生成和 Zep 图谱构建：`backend/app/api/graph.py`
- 图谱实体读取、Agent Profile 生成和仿真准备：`backend/app/api/simulation.py`
- OASIS 多智能体仿真启动与状态读取：`backend/app/services/simulation_runner.py`
- Report Agent 报告生成和报告问答：`backend/app/api/report.py`
- 前端主流程页面：`frontend/src/views/` 与 `frontend/src/components/Step*.vue`

已经移除的内容：

- 原项目运行截图和演示封面
- QQ 群、学校 Logo、示例截图等展示素材
- PPT 生成脚本、PPT 素材、比赛交付型文档
- 原版英文 README
- 上游 GHCR Docker workflow
- `node_modules/`、`frontend/dist/`、`backend/logs/`、`backend/uploads/`、本地模型权重

## CogSec 核心模块

| 模块 | 作用 |
|---|---|
| `privacy_sanitizer.py` | 本地脱敏，保护手机号、身份证、银行卡等敏感信息 |
| `t0_fast_responder.py` | LLM 前的毫秒级红旗规则检测 |
| `cognitive_profiler.py` | 18 维认知画像抽取，生成用户数字孪生基础向量 |
| `runtime_schema.py` | PersonaStateVector、RiskGraphBundle、WorldStateSnapshot 等运行时结构 |
| `threat_rag.py` | 诈骗案例检索、攻击策略链构造、风险图谱生成 |
| `mainline_runtime.py` | MiroFish 风格 WorldState 主判别运行时与 Fork A/B 推演 |
| `risk_scorer.py` | 基于分支差值、不可逆损失和证据一致性的风险聚合 |
| `cf_reporter.py` | 输出分支对照、关键节点、干预窗口和个性化处方 |
| `cogsec_service.py` | 串联以上模块，对外提供统一 CogSec 分析结果 |

## 快速开始

### 1. 环境要求

- Node.js 18+
- Python 3.11 或 3.12
- uv

### 2. 配置环境变量

```bash
cp .env.example .env
```

完整 MiroFish 主链至少需要：

```env
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL_NAME=qwen-plus
ZEP_API_KEY=your_zep_api_key
```

CogSec 最小 Demo 可以不配置 Zep；如果没有本地模型，系统会回退到启发式画像和本地案例库。

### 3. 安装依赖

```bash
npm run setup:all
```

或者分开安装：

```bash
npm install
npm install --prefix frontend
cd backend
uv sync
```

### 4. 启动完整主线

```bash
npm run dev
```

访问：

- 前端：`http://localhost:3000`
- 后端：`http://localhost:5001`

### 5. 启动 CogSec 最小 Demo

```bash
cd backend
python run_cogsec_demo.py
```

访问：

- `http://127.0.0.1:5052/demo/cogsec`
- `http://127.0.0.1:5052/health`

## API

CogSec 独立分析：

```http
POST /api/cogsec/analyze
```

请求示例：

```json
{
  "scenario": "对方冒充客服说快递丢失，让我共享屏幕并提供银行卡验证码。",
  "scenario_type": "冒充电商物流客服类"
}
```

基于已有报告触发 CogSec 分析：

```http
GET /api/cogsec/report/<report_id>
```

完整主链接口：

```text
POST /api/graph/ontology/generate
POST /api/graph/build
POST /api/simulation/create
POST /api/simulation/prepare
POST /api/simulation/start
POST /api/report/generate
POST /api/report/chat
```

## 测试

```bash
python -m pytest tests
```

## Docker

```bash
docker compose up --build
```

默认暴露：

- `3000` 前端
- `5001` 后端
- `8000` Chroma

## 说明

本项目保留 MiroFish 的必要图谱、仿真与报告链路，是为了让 CogSec 能在完整多智能体推演环境中运行；仓库已去除与运行无关的截图、PPT、展示素材和本地临时文件，使其更适合作为独立 GitHub 项目维护。

MiroFish 原始仿真能力由 OASIS 驱动，感谢 MiroFish 与 CAMEL-AI 的开源基础。
