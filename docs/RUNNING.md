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
# 任选一家 OpenAI-compatible 接口；不要把真实 key 写入 README/代码。
MIRO_COGSEC_MAIN_LLM_API_KEY=your-api-key
MIRO_COGSEC_MAIN_LLM_BASE_URL=https://your-provider.example/v1
MIRO_COGSEC_MAIN_LLM_MODEL=your-model

# 完整 OASIS 候选复核使用独立配置（可选）
# MIRO_COGSEC_OASIS_API_KEY=your-api-key
# MIRO_COGSEC_OASIS_BASE_URL=https://your-provider.example/v1
# MIRO_COGSEC_OASIS_MODEL=your-model

# 本地模型默认关闭；只有明确需要时才设为 true
COGSEC_USE_LOCAL_GEMMA=false

# 最终回答默认复用可用的主 LLM，失败时回退到确定性 renderer
MIRO_REPORTER_POLICY_MODE=auto

# 可选本地 Reporter / LoRA adapter（仍走同一个分析 API）
# MIRO_REPORTER_MODEL_PATH=/path/to/reporter-base
# MIRO_REPORTER_ADAPTER_PATH=/path/to/reporter-lora

ENABLE_PPO_TRAINING=false
```
后端启动时由 `backend/app/config.py` 自动 `load_dotenv` 读入。
不配 key 也不开本地 Gemma时，主 API 可使用启发式/轻量运行态完成降级分析；结果会明确标注 `degraded`，不能当作真实 LLM/OASIS 运行结果。
最终回答的实际后端见 `reporter_provenance`。`trained_policy_used=true` 只会在显式选择 `trained_policy`、提供 checkpoint 且模型真实生成成功时出现。

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
# 期望: HTTP 200，返回非空 data.assistant_message；在线请求默认不生成 benchmark_prediction
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
set TORCHINDUCTOR_CACHE_DIR=C:\tmp\torchinductor
set TEMP=C:\tmp
set TMP=C:\tmp
python backend/run.py
```
或一劳永逸地在系统环境变量里把 `TEMP`/`TMP` 设为纯英文路径。

### 坑 2：transformers / huggingface_hub 版本

`backend/requirements.txt` 已把 HF 栈钉在互相兼容的区间
（`transformers>=4.46.0,<5.0.0`、`huggingface_hub>=0.24.0,<1.0.0`）。
**请勿把它们升级到 `transformers>=5` 或 `huggingface_hub>=1`** —— 与 sentence-transformers 互锁，pip 会直接报 `ResolutionImpossible`。
