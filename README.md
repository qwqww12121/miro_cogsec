# Miro-CogSec

这是我们参加 **2026 年全国大学生信息安全作品赛（信安作品赛）** 的作品，决赛拿了优胜奖。赛后我们问过小队成员，大家都同意把它开源，所以这份代码就摊开了。

Miro-CogSec 是一套面向人因安全的**认知安全反事实推演**系统，主干改自开源项目 [MiroFish](https://github.com/666ghj/MiroFish)。它不满足于给一段文本贴「诈骗 / 不是诈骗」的标签，而是把同一份案例事实、同一份初始社会状态，推成可对照的危险路径和干预路径。

支持三类场景：


| 场景     | 代码名                 | 做什么                  |
| ------ | ------------------- | -------------------- |
| 诈骗即时通讯 | `fraud_im`          | 看对话里的话术、资产目标和关键分岔    |
| 舆情分析   | `public_opinion`    | 看叙事怎么竞争、情绪和官方回应缺口    |
| 事件传播   | `event_propagation` | 看一条信息怎么被放大、失真、以及能否拦住 |


前端有首页智能识别、三个场景页，以及更对话式的「智能对话」页。后端是 Flask API；舆情 / 事件场景在依赖齐全时可以用 OASIS 做候选复核，装不上也会自动降级，不会假装跑过完整仿真。

---

## 它实际能做什么

- **场景识别**：把一段聊天、舆情帖或事件描述分到三类场景，并给出置信度和理由。
- **本地脱敏**：正则 + 可选 Presidio，尽量先把手机号、身份证这类信息挡掉再往下走。
- **毫秒级红旗**：T0 规则先抓明显危险信号，不等大模型。
- **案例事实化**：整理成带证据来源的 `CanonicalCase`，避免后面各模块各说各话。
- **18 维认知画像**：状态 / 易感 / 保护三层，给后续推演一个可比较的人因起点。
- **策略检索**：用案例库 + ChromaDB 检索攻击策略，并生成风险图谱。
- **反事实推演**：诈骗走威胁方 / 用户孪生 / 核验方的策略互动；舆情看叙事竞争；事件跟踪 Claim 保真与失真。
- **干预搜索**：先在同一初始社会状态上做轻量 proxy 搜索；有 OASIS 时只把受支持的候选交给它复核，来源互相分开，不会混称。
- **角色化报告**：面向个人、媒体、官方、目标群体给出不同表述，并带上 `reporter_provenance`，失败会明确回退。

缺 key、缺 OASIS、缺本地模型时，系统仍可能给出启发式 / 轻量结果，但会标成 `degraded` / `proxy` / `not_run`。那种结果**不能**当成完整 LLM 或 OASIS 跑出来的结论。

---



## 架构与目录

```text
输入（单次文本 / 多轮 Session / 文件 / 可选语音）
  -> 场景识别
  -> 本地脱敏
  -> T0 红旗
  -> CanonicalCase
  -> 认知画像 + 策略检索 + 共享 SocialState S0
  -> 场景运行时（诈骗 / 舆情 / 事件）
  -> proxy 干预搜索（可选 OASIS 复核）
  -> 风险评分 + ReportState
  -> 自然语言结论 / 证据 / 干预建议
```

```text
backend/          Flask 后端、CogSec 主链、可选旧版 MiroFish API
frontend/         Vite + React + Tailwind
data/             诈骗案例库、T0 规则、LIWC 词典等（不含向量库）
benchmark/        小样本评测数据、prompt 与脚本
scripts/          冒烟测试、评测与可选训练入口
tests/            pytest
docs/             运行说明和主链设计笔记
```

本地生成、不要提交的东西：`.env`、`node_modules/`、`data/chroma_db/`、`data/oasis_traces/`、`models/`、日志和 `benchmark/outputs/` 里的跑分结果。

---



## 快速开始



### 环境


| 依赖           | 建议                                        |
| ------------ | ----------------------------------------- |
| Python       | **3.11**（`camel-oasis` 要求 `>=3.10,<3.12`） |
| Node.js      | 18+                                       |
| Conda / venv | 建议独立环境                                    |
| GPU          | 可选；只有本地 Gemma 才需要大约 8GB 显存                |




### 1. 后端

```bash
conda create -n ciscn python=3.11 -y
conda activate ciscn

# 可选：有 NVIDIA GPU 时先装 CUDA 版 PyTorch
# pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124

pip install -r backend/requirements.txt
python -m spacy download zh_core_web_sm
```

舆情 / 事件的完整 OASIS 仿真还需要：

```bash
pip install "camel-ai[all]==0.2.5"
pip install oasis
```

`camel-ai==0.2.78` 依赖 `mcp>=1.3,<2`。`mcp 2.x` 会让 OASIS 导入失败。

也可以用 `uv`：`npm run setup:backend`（读取 `backend/pyproject.toml` 与 `uv.lock`）。

### 2. 前端

在仓库根目录：

```bash
npm install
npm install --prefix frontend
```



### 3. 配置

复制根目录的 `.env.example` 为 `.env`，填你自己的 OpenAI 兼容接口：

```env
MIRO_COGSEC_MAIN_LLM_API_KEY=YOUR_API_KEY
MIRO_COGSEC_MAIN_LLM_BASE_URL=https://your-provider.example/v1
MIRO_COGSEC_MAIN_LLM_MODEL=YOUR_MODEL_NAME
```

不要把真实 key 写进 README、issue 或截图。主分析和 OASIS 使用各自的项目变量，默认不会去借 `OPENAI_API_KEY`。

可选：`MIRO_COGSEC_OASIS_*`、`MIRO_REPORTER_*`、`MIRO_SPEECH_*`、`ZEP_API_KEY`。不配也能起服务，相关能力会降级。

更完整的环境说明见 [docs/RUNNING.md](docs/RUNNING.md)。

### 4. 运行

仓库根目录一键前后端：

```bash
npm run dev
```

或分开启动：

```bash
conda activate ciscn
python backend/run.py          # http://127.0.0.1:5001

cd frontend
npm run dev                    # http://localhost:3000
```


| 服务   | 地址                                             |
| ---- | ---------------------------------------------- |
| 前端   | [http://localhost:3000](http://localhost:3000) |
| 后端   | [http://localhost:5001](http://localhost:5001) |
| 分析接口 | `POST /api/cogsec/analyze`                     |
| 场景识别 | `POST /api/classify`                           |


首次启动会下载 sentence-transformers 向量模型并建 Chroma 索引，可能要等一两分钟。

### 5. 冒烟测试

后端起来之后：

```bash
python scripts/smoke_cogsec_http.py
```

Docker 可选：`docker compose up --build`。镜像会读根目录 `.env`，同样不要把真实密钥打进镜像层。

---



## 使用注意

- **这是比赛作品，不是执法或风控生产系统。** 输出用于研究、演示和解释，不能代替报警、银行核实或专业研判。
- 案例库和演示文本是构造出来的诈骗 / 舆情 / 事件材料，用来测识别和推演，不是真实受害人数据。
- OASIS、Zep、本地 Gemma、语音转写都是可选件。缺依赖时请看响应里的 `latency_profile` / `reporter_provenance`，不要把降级结果说成完整仿真。
- 原始 MiroFish 的 graph / simulation / report API 默认关闭（`ENABLE_LEGACY_MIROFISH_API=false`）。
- Windows 用户名含非 ASCII 字符时，torch 缓存目录可能踩坑，处理办法写在 `docs/RUNNING.md`。
- 训练相关脚本（Ranker / Reporter SFT / PPO）是研究入口，默认关闭；没有自己的数据和 checkpoint 时不要指望“一键训出模型”。

更细的主链、传播运行时和响应字段见 `docs/`。

---



## API 摘要



### 单次分析

```http
POST /api/cogsec/analyze
Content-Type: application/json

{
  "scenario": "攻击者：您好，我是公安局民警，您的账户涉及洗钱...\n受害人：好的，我怎么配合？",
  "scenario_type": "虚假征信类",
  "tone": "friendly"
}
```

常用字段：`scenario`（必填）、`scenario_type`（canonical 名或中文诈骗类别，可省略并自动识别）、`user_role`（`individual` / `official` / `media` / `target_group`）、`tone`。

成功时关注 `assistant_message`、`plain_view`、`graph_payload`、`counterfactual_report`、`reporter_provenance`、`latency_profile`。

### 多轮 Session

```http
POST /api/cogsec/session/create
POST /api/cogsec/session/<session_id>/turn
POST /api/cogsec/session/<session_id>/analyze
```

---



## 开源说明

- 许可证：**AGPL-3.0**。上游 MiroFish 使用 AGPL，本仓库沿用同一许可证，没有改成 MIT。
- Copyright © 2026 Miro-CogSec Team。
- 请自行准备大模型 / 语音 / Zep 等服务的密钥与额度。仓库里只有占位符。
- 欢迎提 issue 和 PR；这是学生作品，架构和评测都还有明显边界，`docs/project_limitations_and_improvement_notes.md` 里写过一部分。



## 致谢

感谢 [MiroFish](https://github.com/666ghj/MiroFish) 提供的多智能体推演主链，以及 OASIS / CAMEL-AI 在传播仿真上的开源工作。也谢谢评委和一起熬过决赛的队友。