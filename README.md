# Miro-CogSec

基于 MiroFish 多智能体推演主链改造的**认知安全反事实推演平台**。

支持**诈骗IM、舆情分析、事件传播**三类场景，具备单次分析与多轮对话两种输入模式。

## 项目定位

Miro-CogSec 面向诈骗、舆情诱导等人因安全场景。核心思想：不仅对文本做分类，而是先用 ScenarioDetector 感知场景类型，再构造用户 18 维认知数字孪生和攻击-人-环境风险图谱，用 MiroFish 风格的 WorldState 运行时进行 Fork A/B 反事实推演，最后根据两条路径的轨迹差值生成风险结论与个性化干预处方。

舆情/事件传播场景额外调用 **OASIS 真实多 Agent 社交仿真**（camel-oasis 0.2.5），在 Fork A（自然传播）与 Fork B（官方辟谣注入）双分支中模拟社会网络扩散过程。

## 主链流程

```text
Input（单次文本 or 多轮 Session）
  -> ScenarioDetector          场景感知（fraud_im / public_opinion / event_propagation）
  -> PrivacySanitizer          本地脱敏（Presidio + 正则）
  -> T0FastResponder           毫秒级红旗检测
  -> CognitiveProfiler         18 维认知数字孪生
  -> ThreatKnowledgeRAG        攻击策略检索 + RiskGraphBundle（ChromaDB）
  -> MiroFishRuntime           Fork A/B WorldState 反事实推演（6 步 × 6 规则）
  -> RiskScorer                五因子聚合评分 + fork_count 多规则加成
  -> CounterfactualReporter    干预处方 + 最优行动窗口 + score_comparison
  -> RoleReporter              角色差异化报告（individual / media / official / target_group）
  -> PropagationSimulator      OASIS 多 Agent 传播仿真（仅 public_opinion / event_propagation）
```

## 支持场景

| canonical | 中文 | 传播仿真 |
|---|---|---|
| `fraud_im` | 诈骗IM（冒充公安/客服/领导等） | — |
| `public_opinion` | 舆情分析 | ✓ OASIS |
| `event_propagation` | 事件传播分析 | ✓ OASIS |

传入任意中文诈骗类别（如"刷单返利类"）会自动映射到 `fraud_im`；未识别场景同样降级到 `fraud_im`。

## 仓库结构

```text
backend/
  app/
    api/                    # graph / simulation / report / cogsec API
    modules/
      scenario_detector.py  # 场景感知检测器（关键词竞争 + T0 信号）
      cognitive_profiler.py # 18 维认知数字孪生
      mainline_runtime.py   # Fork A/B 反事实推演运行时
      risk_scorer.py        # 风险聚合评分
      cf_reporter.py        # 反事实报告 + 干预处方 + score_comparison
      privacy_sanitizer.py  # 本地脱敏（Presidio + 正则 + 人名黑名单）
      t0_fast_responder.py  # 毫秒级红旗检测
      threat_rag.py         # 案例检索 + 风险图谱（ChromaDB）
      scenarios/            # 三类场景规格（fraud_im / public_opinion / event_propagation）
      reporters/            # 角色差异化报告（individual / media / official / target_group）
      propagation/          # OASIS 真实多 Agent 传播仿真 + 轻量回退仿真器
        oasis_adapter.py    # OasisPropagationAdapter：Fork A/B 双分支 OASIS 仿真
      session/              # 多轮对话数据结构与文本组装
    services/
      cogsec_service.py     # 主链编排服务
      session_manager.py    # 多轮 Session 管理
    utils/
      local_gemma_client.py # 本地 Gemma 推理客户端（device_map GPU 全量加载）

frontend/
  src/
    views/Home.vue           # CogSec 输入 + 内联结果工作台（双模式）
    components/cogsec/       # 10 个分析屏幕组件（数字孪生 / 风险图 / 双分支 / 处方等）

data/
  fraud_cases.json           # 诈骗案例库（10 条案例，22 个攻击策略）
  liwc_chinese.json          # 中文 LIWC 词典
  t0_regex_patterns.json     # T0 红旗规则

scripts/
  smoke_cogsec_http.py       # HTTP 端到端 smoke test
  quick_smoke.py             # 本地快速回归测试（无编码问题）
```

## 快速开始

### 1. 环境要求

- Node.js 18+
- Python **3.11**（camel-oasis 要求 >=3.10,<3.12）
- Conda（Anaconda / Miniconda）

### 2. 创建 Python 环境并安装依赖

```bash
# 创建 Python 3.11 conda 环境
conda create -n ciscn python=3.11 -y
conda activate ciscn

# 安装 PyTorch（有 NVIDIA GPU 时安装 CUDA 版，无 GPU 去掉 --index-url 部分）
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124

# 安装 HuggingFace 兼容版本的 transformers
pip install "transformers>=5.0.0" "huggingface_hub>=1.0.0"

# 安装后端其余依赖
pip install -r backend/requirements.txt

# 安装前端依赖
npm install
npm install --prefix frontend
```

### 3. 配置环境变量

复制 `.env.example` 为 `.env` 并填写：

```env
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL_NAME=qwen-plus
ZEP_API_KEY=your_zep_api_key
```

未配置 Zep 时系统仍可运行；OASIS 传播仿真使用 `LLM_API_KEY` 调用同一模型。

### 4. 本地 Gemma 模型（可选）

若使用本地 Gemma 替代云端 LLM，需先在 HuggingFace 申请访问权限，然后：

```bash
hf auth login
hf download google/gemma-4-E2B-it --local-dir models/google--gemma-4-E2B-it
```

在 `.env` 中启用：

```env
COGSEC_USE_LOCAL_GEMMA=true
```

需要 GPU 显存 ≥ 8GB（fp16 全量加载到 GPU 0）。

### 5. 启动

```bash
npm run dev
```

- 前端：`http://localhost:5173`
- 后端：`http://localhost:5001`

## API

### 单次分析

```http
POST /api/cogsec/analyze
Content-Type: application/json

{
  "scenario": "对方自称公安局民警，要求我把钱转到安全账户配合调查。",
  "scenario_type": "fraud_im"
}
```

`scenario_type` 可填 `fraud_im` / `public_opinion` / `event_propagation` 或中文诈骗类别，省略时由 ScenarioDetector 自动识别。

### 多轮 Session

```http
# 1. 创建 Session
POST /api/cogsec/session/create
{ "scenario_type": "fraud_im", "user_role": "individual" }

# 2. 逐轮追加（可多次）
POST /api/cogsec/session/<session_id>/turn
{ "role": "user", "content": "对方让我下载一个 APP..." }

# 3. 触发完整分析
POST /api/cogsec/session/<session_id>/analyze

# 其他
GET    /api/cogsec/session/<session_id>     # 查看 Session 详情
DELETE /api/cogsec/session/<session_id>     # 删除 Session
GET    /api/cogsec/session/list             # 列出所有 Session
```

支持的 `user_role`：`individual`（个人）/ `official`（官方机构）/ `media`（媒体）/ `target_group`（目标群体）。

### MiroFish 主链（jzh 模块）

```text
POST /api/graph/ontology/generate
POST /api/graph/build
POST /api/simulation/create
POST /api/simulation/start
POST /api/report/generate
```

## 核心模块说明

| 模块 | 作用 |
|---|---|
| `scenario_detector.py` | 关键词竞争 + T0 信号 → 识别 canonical 场景类型，优先级：用户声明 > T0 欺诈命中 > 关键词竞争 > fallback |
| `cognitive_profiler.py` | 18 维认知画像：状态层 / 易感层 / 保护层，LLM 驱动 |
| `mainline_runtime.py` | Fork A（顺从）vs Fork B（干预）WorldState 推演，6 步 × 6 规则，各规则独立 label |
| `risk_scorer.py` | 五因子评分 × fork_count 加成（最高×1.20）→ FinalRisk，等级 LOW/MEDIUM/HIGH/CRITICAL |
| `cf_reporter.py` | 分支对照、关键节点、干预窗口、处方，生成 score_comparison（含四维评分时间线） |
| `privacy_sanitizer.py` | Presidio + 正则，含 AMOUNT 金额模式、PERSON_NAME 误报黑名单 |
| `scenarios/` | 三类场景规格，各自定义风险维度、报告结构、传播仿真入口 |
| `reporters/` | 四种角色差异化报告，orchestrator 统一调度 |
| `propagation/oasis_adapter.py` | OASIS 真实多 Agent 传播仿真：Branch A（自然传播）vs Branch B（官方辟谣注入），结果写 SQLite，转 PropagationTrace |
| `session/` | 多轮对话组装，turns → merged text → 主链分析 |

## 测试

```bash
# 快速回归（后端需运行）
conda run -n ciscn python scripts/quick_smoke.py

# 完整 HTTP smoke test（输出 JSON 报告）
conda run -n ciscn python scripts/smoke_cogsec_http.py --output benchmark/outputs/result.json
```

期望结果：`success: True`，`risk_level: HIGH`，`final_risk: 55.0`（冒充公安场景）。

## 说明

本项目保留 MiroFish 的图谱、仿真与报告链路，使 CogSec 能在完整多智能体推演环境中运行。MiroFish 原始仿真能力由 OASIS 驱动，感谢 MiroFish 与 CAMEL-AI 的开源基础。
