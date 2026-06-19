# Miro-CogSec

基于 MiroFish 多智能体推演主链改造的**认知安全反事实推演平台**。

支持**诈骗IM、舆情分析、事件传播**三类场景，具备单次分析与多轮对话两种输入模式。

---

## 项目定位

Miro-CogSec 面向诈骗、舆情诱导等人因安全场景。核心思想：不仅对文本做分类，而是先用 ScenarioDetector 感知场景类型，再构造用户 18 维认知数字孪生和攻击-人-环境风险图谱，用 MiroFish 风格的 WorldState 运行时进行 Fork A/B 反事实推演，最后根据两条路径的轨迹差值生成风险结论与个性化干预处方。

舆情/事件传播场景额外调用 **OASIS 真实多 Agent 社交仿真**（camel-oasis），在 Fork A（自然传播）与 Fork B（官方辟谣注入）双分支中模拟社会网络扩散过程。

---

## 主链流程

```text
Input（单次文本 or 多轮 Session）
  -> ScenarioDetector          场景感知（fraud_im / public_opinion / event_propagation）
  -> T0FastResponder           毫秒级红旗检测
  -> PrivacySanitizer          本地脱敏（Presidio + 正则）
  -> CognitiveProfiler         18 维认知数字孪生
  -> ThreatKnowledgeRAG        攻击策略检索 + RiskGraphBundle（ChromaDB）
  -> MiroFishRuntime           Fork A/B WorldState 反事实推演（6 步 × 6 规则）
  -> RiskScorer                五因子聚合评分 + fork_count 多规则加成
  -> CounterfactualReporter    干预处方 + 最优行动窗口 + score_comparison
  -> RoleReporter              角色差异化报告（individual / media / official / target_group）
  -> PropagationSimulator      OASIS 多 Agent 传播仿真（仅 public_opinion / event_propagation）
```

---

## 支持场景

| canonical | 中文 | 传播仿真 |
|---|---|---|
| `fraud_im` | 诈骗IM（冒充公安/客服/领导等） | — |
| `public_opinion` | 舆情分析 | ✓ OASIS |
| `event_propagation` | 事件传播分析 | ✓ OASIS |

传入任意中文诈骗类别（如"刷单返利类"、"虚假征信类"）会自动映射到 `fraud_im`；未识别场景同样降级到 `fraud_im`。

---

## 仓库结构

```text
backend/
  app/
    api/                    # graph / simulation / report / cogsec API 路由
    modules/
      scenario_detector.py  # 场景感知（关键词竞争 + T0 信号）
      cognitive_profiler.py # 18 维认知数字孪生
      mainline_runtime.py   # Fork A/B 反事实推演运行时
      risk_scorer.py        # 风险聚合评分
      cf_reporter.py        # 反事实报告 + 干预处方 + score_comparison
      privacy_sanitizer.py  # 本地脱敏（Presidio + 正则 + 人名黑名单）
      t0_fast_responder.py  # 毫秒级红旗检测
      threat_rag.py         # 案例检索 + 风险图谱（ChromaDB）
      scenarios/            # 三类场景规格
      reporters/            # 角色差异化报告
      propagation/
        oasis_adapter.py    # OASIS Fork A/B 双分支仿真适配器
      session/              # 多轮对话数据结构
    services/
      cogsec_service.py     # 主链编排
      session_manager.py    # 多轮 Session 管理
    utils/
      local_gemma_client.py # 本地 Gemma 推理客户端
  requirements.txt
  run.py

frontend/                   # React + Tailwind（Vite，端口 3000）
  src/
    pages/
      Home.jsx              # 首页：智能识别 + 手动选择
      BenchmarkPage.jsx     # /benchmark 评测对比页
      scenarios/            # 三个场景页（FraudIm / PublicOpinion / EventPropagation）
    components/results/     # 三个结果面板
    api/                    # axios 封装

data/
  fraud_cases.json          # 诈骗案例库（10 条，22 个攻击策略）
  liwc_chinese.json         # 中文 LIWC 词典
  t0_regex_patterns.json    # T0 红旗规则

benchmark/
  data/                     # Gold 标注数据（三类场景各一份 .jsonl）
  outputs/
    api_*_after_adapter_v0.1.jsonl          # Miro 推理输出
    api_*_answer_scores_after_adapter_v0.1.json  # RES 语义评分结果
    llm_baseline/           # LLM-only baseline 输出 + 评分
    closed_model_judge/     # 盲评请求 + Qwen3.7-plus 评判结果
  cogsec_benchmark.py       # 评分框架（RES 语义相似度 v0.5）

scripts/
  quick_smoke.py            # 本地快速回归测试
  smoke_cogsec_http.py      # HTTP 端到端 smoke test
  make_closed_model_judge_input.py  # 生成盲评请求
  run_closed_model_judge.py         # 调用 LLM judge 打分
  rescore_miro_outputs.py           # 用 benchmark_prediction 字段重新打分

models/                     # 本地模型存放目录（不纳入 git）
```

---

## Benchmark 评测

评测包含三项指标，样本量：诈骗IM 20 条、舆情分析 5 条、事件传播 5 条。

### RES 语义总分

RES（Result Evaluation Score）采用语义相似度 v0.5：自由文本字段用向量余弦相似度，分类字段用软匹配。

| 场景 | Miro-CogSec | LLM-only |
|---|---|---|
| 诈骗IM | **0.712** | 0.714 |
| 舆情分析 | **0.414** | 0.376 |
| 事件传播 | **0.597** | 0.589 |

Miro 在舆情与事件传播场景超过 LLM-only 基线，诈骗 IM 几乎持平（差 0.2%）。

### 分维度得分

| 场景 | 系统 | 检测 | 推理 | 干预 | 证据 | 运行 |
|---|---|---|---|---|---|---|
| 诈骗IM | Miro | 0.825 | 0.700 | **0.800** | **0.870** | **1.000** |
| 诈骗IM | LLM-only | **0.892** | **0.863** | 0.330 | 0.790 | — |
| 舆情分析 | Miro | **0.700** | **0.374** | **0.474** | 0.738 | **0.667** |
| 舆情分析 | LLM-only | 0.277 | 0.128 | 0.159 | **0.843** | — |
| 事件传播 | Miro | **0.700** | **0.613** | **0.900** | 0.758 | **0.667** |
| 事件传播 | LLM-only | 0.354 | 0.413 | 0.607 | **0.927** | — |

Miro 优势在干预窗口与运行完整性；LLM-only 在检测（诈骗IM）和证据归因（舆情/事件传播）上更高。

### 盲评胜率（Qwen3.7-plus）

无参考答案盲测，结构化预测 dict 格式，温度 0.0。

| 场景 | 样本 | Miro 胜 | LLM 胜 | Miro 胜率 |
|---|---|---|---|---|
| 诈骗IM | 20 | 1 | 19 | 5% |
| 舆情分析 | 5 | 0 | 5 | 0% |
| 事件传播 | 5 | 2 | 3 | 40% |
| **合计** | **30** | **3** | **27** | **10%** |

盲评反映表达流畅度，LLM-only 以自然语言叙述风格占优；RES 语义评分反映字段精确度，两者衡量维度不同。

---

## 快速开始

### 第一步：系统依赖

| 依赖 | 版本要求 | 说明 |
|---|---|---|
| **Python** | 3.11（推荐） | camel-oasis 要求 >=3.10,<3.12 |
| **Conda** | Anaconda / Miniconda 任意版本 | 管理 Python 环境 |
| **Node.js** | 18+ | 前端构建与开发服务器 |
| **npm** | 随 Node.js 安装 | 前端依赖管理 |
| **NVIDIA GPU** | 显存 ≥ 8GB（可选） | 仅本地 Gemma 模型需要 |

---

### 第二步：创建 Python 环境

```bash
conda create -n ciscn python=3.11 -y
conda activate ciscn
```

---

### 第三步：安装 PyTorch

**有 NVIDIA GPU（推荐）：**
```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
```

**仅 CPU（无 GPU / 不使用本地 Gemma）：**
```bash
pip install torch torchvision torchaudio
```

> 验证 GPU 是否可用：`python -c "import torch; print(torch.cuda.is_available())"`

---

### 第四步：安装后端依赖

```bash
pip install -r backend/requirements.txt
```

**安装 camel-oasis（舆情/事件传播 OASIS 仿真所需）：**
```bash
pip install camel-ai[all]==0.2.5
pip install oasis
```

> 若网络较慢，可使用国内镜像：
> ```bash
> pip install -r backend/requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
> ```

---

### 第五步：安装前端依赖

```bash
npm install
npm install --prefix frontend
```

---

### 第六步：配置环境变量

在项目**根目录**创建 `.env` 文件（不要放在 backend/ 里）：

```env
# ===== LLM 配置（三选一）=====

# 方案 A：DeepSeek（推荐，速度快、价格低）
LLM_API_KEY=sk-xxxxxxxxxxxxxxxx
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL_NAME=deepseek-chat

# 方案 B：阿里云百炼 qwen-plus
# LLM_API_KEY=sk-xxxxxxxxxxxxxxxx
# LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
# LLM_MODEL_NAME=qwen-plus

# 方案 C：本地 Gemma（需 GPU 显存 ≥ 8GB，见下方模型下载说明）
# COGSEC_USE_LOCAL_GEMMA=true

# ===== ChromaDB 向量库路径 =====
# 相对于 backend/ 运行目录，不要改成 ./data/
CHROMA_PATH=../data/chroma_db

# ===== 其他配置（可留空）=====
ZEP_API_KEY=
PRESIDIO_ENABLED=true
LOCAL_SANITIZE_ENABLED=true
```

> **注意：**
> - `LLM_BOOST_*` 等字段留空时**不要写进 `.env`**，否则 URL 解析报错。
> - `.env` 已在 `.gitignore` 中，不会被提交。

---

### 第七步：下载模型

#### 7.1 Presidio 脱敏模型（必须）

```bash
conda activate ciscn
python -m spacy download zh_core_web_sm
```

> 若下载失败，手动安装：
> ```bash
> pip install https://github.com/explosion/spacy-models/releases/download/zh_core_web_sm-3.7.0/zh_core_web_sm-3.7.0-py3-none-any.whl
> ```

#### 7.2 sentence-transformers 向量模型（首次运行自动下载）

ChromaDB 使用 `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` 做向量索引，**首次启动后端时会自动下载**（约 470 MB），无需手动操作。

> 若网络受限，可提前手动下载：
> ```bash
> python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')"
> ```

#### 7.3 本地 Gemma 模型（可选，需 GPU 显存 ≥ 8GB）

```bash
conda activate ciscn
pip install huggingface_hub
huggingface-cli login

huggingface-cli download google/gemma-4-E2B-it \
    --local-dir models/google--gemma-4-E2B-it \
    --local-dir-use-symlinks False
```

> **国内下载（hf-mirror）：**
> ```bash
> HF_ENDPOINT=https://hf-mirror.com huggingface-cli download google/gemma-4-E2B-it \
>     --local-dir models/google--gemma-4-E2B-it \
>     --local-dir-use-symlinks False
> ```

下载完成后在 `.env` 中启用：`COGSEC_USE_LOCAL_GEMMA=true`

---

### 第八步：启动项目

**同时启动前端 + 后端（推荐）：**

```bash
npm run dev
```

**分别启动（调试时）：**

```bash
# 启动后端（端口 5001）
conda activate ciscn
cd backend && python run.py

# 另开终端，启动前端（端口 3000）
cd frontend && npm run dev
```

| 服务 | 地址 |
|---|---|
| **前端** | http://localhost:3000 |
| **后端 API** | http://localhost:5001 |
| **CogSec 分析接口** | http://localhost:5001/api/cogsec/analyze |
| **Benchmark 评测页** | http://localhost:3000/benchmark |

> **首次启动较慢**：ChromaDB 会下载向量模型并建立索引，约需 1-3 分钟。

---

### 第九步：验证运行

```bash
conda activate ciscn
python scripts/quick_smoke.py
```

预期输出：
```
✓ status=success  risk_level=HIGH  final_risk=55.0  t0_hits=...
```

---

## API 参考

### 单次分析

```http
POST /api/cogsec/analyze
Content-Type: application/json

{
  "scenario": "攻击者：您好，我是公安局民警，您的账户涉及洗钱，需要配合调查...\n受害人：好的，我怎么配合？",
  "scenario_type": "虚假征信类"
}
```

**请求字段：**

| 字段 | 类型 | 说明 |
|---|---|---|
| `scenario` | string（必填） | 分析文本，支持对话格式（"角色：内容"） |
| `scenario_type` | string（可选） | 场景类型，支持 canonical（`fraud_im` / `public_opinion` / `event_propagation`）或中文诈骗类别（`虚假征信类` / `刷单返利类` 等），省略时自动识别 |
| `questionnaire` | object（可选） | 额外的用户画像问卷数据 |
| `user_role` | string（可选） | 报告角色：`individual`（默认）/ `official` / `media` / `target_group` |

**响应关键字段：**

```json
{
  "profile": {
    "overall_vulnerability_score": 81.4,
    "protection_score": 2.75,
    "scenario_type": "fraud_im"
  },
  "strategies": [...],
  "counterfactual_report": {
    "summary_branch_a": "分支 A（危险路径）共 6 步...",
    "summary_branch_b": "分支 B（防御路径）共 6 步...",
    "risk_level": "HIGH"
  },
  "intervention_prescriptions": [...],
  "metrics": {
    "t0_latency_ms": 0.043,
    "end_to_end_ms": 8500
  }
}
```

### 多轮 Session

```http
# 1. 创建 Session
POST /api/cogsec/session/create
{ "scenario_type": "fraud_im", "user_role": "individual" }

# 2. 逐轮追加（可多次）
POST /api/cogsec/session/<session_id>/turn
{ "role": "user", "content": "对方让我下载一个 APP 并打开屏幕共享..." }

# 3. 触发完整分析（返回与 /analyze 相同的结构）
POST /api/cogsec/session/<session_id>/analyze

# 其他管理接口
GET    /api/cogsec/session/<session_id>   # 查看详情
DELETE /api/cogsec/session/<session_id>   # 删除
GET    /api/cogsec/session/list           # 列出所有
```

---

## 常见问题

### Q：启动时报 `ModuleNotFoundError: No module named 'presidio_analyzer'`

```bash
conda activate ciscn
pip install presidio-analyzer presidio-anonymizer
python -m spacy download zh_core_web_sm
```

### Q：ChromaDB 报 `sqlite3` 版本错误

```bash
pip install pysqlite3-binary
```

然后在 `backend/app/modules/threat_rag.py` 顶部添加：
```python
__import__('pysqlite3')
import sys
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
```

### Q：`oasis_adapter.py` 报 `ImportError`（camel-oasis 未安装）

系统会自动回退到轻量级传播仿真器，舆情/事件传播场景仍可运行，但 OASIS 多 Agent 仿真不可用。完整安装：

```bash
pip install camel-ai[all]==0.2.5 oasis
```

### Q：本地 Gemma 报 `meta device` 警告 / 显存不足

检查 `.env` 中 `COGSEC_LOCAL_GEMMA_OFFLOAD_DIR` 是否为空（留空则关闭 CPU offload，强制全 GPU 加载）。最低显存要求：fp16 下约 6.5GB。

### Q：OASIS 分析耗时很长（90s+）

OASIS 多 Agent 仿真每次需调用 LLM 约 60-120 次（12 个 Agent × 5 tick × 双分支），是正常现象。使用 DeepSeek API 时约 90-120 秒。诈骗 IM 场景不使用 OASIS，通常 8-15 秒。

### Q：前端启动后访问空白页 / 接口 404

确认前端配置的 proxy 指向 `:5001`（已在 `frontend/vite.config.js` 中配置），后端端口不是 5000。

---

## 核心模块说明

| 模块 | 作用 |
|---|---|
| `scenario_detector.py` | 关键词竞争 + T0 信号 → canonical 场景类型，优先级：用户声明 > T0 欺诈命中 > 关键词竞争 > fallback |
| `cognitive_profiler.py` | 18 维认知画像：状态层 / 易感层 / 保护层，LLM + 受害人背景关键词推断 |
| `mainline_runtime.py` | Fork A（顺从）vs Fork B（干预）WorldState 推演，6 步 × 6 分岔规则 |
| `risk_scorer.py` | 五因子评分 × fork_count 加成（最高×1.20）→ FinalRisk（LOW/MEDIUM/HIGH/CRITICAL） |
| `cf_reporter.py` | 分支对照、关键节点、干预窗口、处方；传播场景生成专属干预建议 |
| `privacy_sanitizer.py` | Presidio + 正则，含 AMOUNT 金额模式、PERSON_NAME 误报黑名单 |
| `threat_rag.py` | ChromaDB 语义检索 + 分类过滤，非诈骗场景返回专属传播策略模板 |
| `propagation/oasis_adapter.py` | Fork A（自然传播）vs Fork B（官方辟谣注入），SQLite 结果 → PropagationTrace |
| `session/` | 多轮对话组装，turns → merged text → 主链分析 |

---

## 风险等级

| 等级 | 分数范围 | 含义 |
|---|---|---|
| LOW | < 25 | 风险极低，无需干预 |
| MEDIUM | 25-49 | 中等风险，建议核实关键信息 |
| HIGH | 50-74 | 高风险，需立即干预 |
| CRITICAL | ≥ 75 | 极高风险，受害人处于即时危险中 |

---

## 致谢

本项目保留 MiroFish 的图谱、仿真与报告链路，使 CogSec 能在完整多智能体推演环境中运行。MiroFish 原始仿真能力由 OASIS 驱动，感谢 MiroFish 与 CAMEL-AI 的开源基础。
