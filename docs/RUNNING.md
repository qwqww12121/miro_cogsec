# 运行说明（Miro-CogSec 后端）

> 面向评委 / 新 clone 者：从零装依赖、起后端、打一次分析接口的最短路径，
> 以及两个已知环境坑的解决办法。
> 实测通过的组合：Python 3.11.8 + transformers 4.57.6 + torch 2.12.1 + sentence-transformers 3.0.0。

## 1. 环境准备

- **Python 3.11**（camel-oasis 要求 `>=3.10,<3.12`）。建议用独立环境，避免与全局包冲突：
  ```bash
  conda create -n ciscn python=3.11 -y && conda activate ciscn
  # 或: python -m venv .venv && .venv/Scripts/activate      # Windows
  ```

## 2. 安装依赖

```bash
pip install -r backend/requirements.txt
```

正常情况会一次装通（flask / openai / transformers / camel-ai / camel-oasis / chromadb /
sentence-transformers / zep-cloud / presidio 等共约 150 个包）。
**PyTorch 会作为 sentence-transformers 的依赖自动装上（CPU 版）**，开箱即可跑。

### （可选）启用 GPU / 本地 Gemma 推理

默认走云端 LLM（见第 3 步配 key），不需要 GPU。若要用本地 Gemma 模型（`COGSEC_USE_LOCAL_GEMMA=true`）
或想用 CUDA 加速，需手动安装 CUDA 版 PyTorch（替换上面的 CPU 版）：
```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
```

## 3. 配置 LLM Key

在**仓库根目录**新建 `.env`（已被 `.gitignore` 忽略，不会提交）：
```dotenv
# 任选一家 OpenAI 兼容接口。以下为 DeepSeek 示例：
LLM_API_KEY=sk-你的key
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL_NAME=deepseek-chat

# 不用本地 Gemma 时务必设为 false（默认 true 会去找本地模型）
COGSEC_USE_LOCAL_GEMMA=false
```
后端启动时由 `backend/app/config.py` 自动 `load_dotenv` 读入。
不配 key 也不开本地 Gemma → 启动会报 “LLM_API_KEY 未配置”。

## 4. 启动后端

```bash
python backend/run.py
# => * Running on http://127.0.0.1:5001
```

冒烟测试（另开一个终端）：
```bash
curl -X POST http://127.0.0.1:5001/api/cogsec/analyze \
  -H "Content-Type: application/json" \
  -d "{\"scenario_type\":\"fraud_im\",\"text\":\"我是公安局，你的账户涉嫌洗钱，请把资金转入安全账户核查。\"}"
# 期望: HTTP 200, data.benchmark_prediction.risk_level == "high"
```

---

## ⚠️ 已知环境坑（遇到再处理，多数机器不会触发）

### 坑 1：Windows 用户名含中文 / 非 ASCII 字符 → torch 启动崩溃

**现象**：`import torch` 时报
`FileExistsError: [WinError 183] ... 'C:\WINDOWS\TEMP\torchinductor_<用户名>'`，
或 `Artifact of type=precompile already registered`。

**原因**：torch 2.x 的 inductor 缓存目录拼了用户名，非 ASCII 用户名会让 `os.makedirs` 失败。
**纯 ASCII 用户名的机器不会触发。**

**解决**：把 torch 的缓存目录指到一个纯英文路径，再启动：
```bash
# Windows (Git Bash / CMD)
set TORCHINDUCTOR_CACHE_DIR=D:\tmp\torchinductor
set TEMP=D:\tmp
set TMP=D:\tmp
python backend/run.py
```
或一劳永逸地在系统环境变量里把 `TEMP`/`TMP` 设为纯英文路径。

### 坑 2：transformers / huggingface_hub 版本

`backend/requirements.txt` 已把 HF 栈钉在互相兼容的区间
（`transformers>=4.46.0,<5.0.0`、`huggingface_hub>=0.24.0,<1.0.0`）。
**请勿把它们升级到 `transformers>=5` 或 `huggingface_hub>=1`** —— 与 sentence-transformers 互锁，pip 会直接报 `ResolutionImpossible`。
