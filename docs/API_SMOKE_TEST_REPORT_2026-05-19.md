# CogSec API 与前后端 Smoke Test 报告

## 1. 测试概述

- 测试日期：2026-05-19
- 测试项目：`miro_cogsec-chm`
- 测试类型：单条样本 smoke test，不执行 20 条 benchmark 全量测试
- 测试目标：
  - 确认后端服务可启动并响应健康检查
  - 确认 `/api/cogsec/analyze` 可通过 HTTP 调用返回分析结果
  - 确认前端 Vite 服务可启动并返回页面
  - 验证外部 LLM API Key 是否真正可用

## 2. 本次修改内容

| 类型 | 路径 | 说明 |
|---|---|---|
| Benchmark 输出迁移 | `benchmark/outputs/aqs_v0.1.json` | 从老项目 `MiroFish-GitHub` 迁移 AQS 标注质量分析结果 |
| 环境配置 | `.env` | 新增本地运行配置，当前 `LLM_API_KEY` 已清空 |
| 环境配置 | `backend/.env` | 新增后端读取用配置，当前 `LLM_API_KEY` 已清空 |
| 测试脚本 | `scripts/smoke_cogsec_http.py` | 新增单条 HTTP API smoke test 脚本，保存响应为 JSON |
| Benchmark 辅助脚本 | `scripts/run_cogsec_api_benchmark.py` | 新增通过完整 `CogSecService` 路径跑 benchmark 的辅助脚本，未执行 20 条全量测试 |
| 前端依赖 | `frontend/node_modules/` | 使用 npm 镜像安装前端依赖，用于启动前端 smoke test |
| API 响应产物 | `benchmark/outputs/api_one_result.json` | 保存本次单条 API 响应结果 |

## 3. 测试环境

| 项目 | 实际状态 |
|---|---|
| 工作目录 | `D:\mirofish\miro_cogsec-chm` |
| Python 环境 | `D:\mirofish\5_16以前\.conda_envs\mirofish_cogsec312` |
| Python 版本 | `3.12.13` |
| Node 环境 | 同一 conda 环境内置 `node` |
| Node 版本 | `v25.8.2` |
| npm 版本 | `11.11.1` |
| Python 依赖状态 | `pip check` 通过，无破损依赖 |
| 前端依赖状态 | `npm ci --registry=https://registry.npmmirror.com` 安装成功 |

备注：`camel-oasis==0.2.5` 不支持 Python 3.12，要求 `<3.12`。本次 CogSec API smoke test 不依赖 OASIS，因此未在 3.12 环境中安装该包。

## 4. 配置处理

本次曾临时配置外部 LLM API Key，用于验证百炼兼容 OpenAI 接口。测试结束后已清空：

- `.env` 中 `LLM_API_KEY=`
- `backend/.env` 中 `LLM_API_KEY=`

当前保留的非敏感配置：

```env
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL_NAME=qwen-plus
COGSEC_USE_LOCAL_GEMMA=false
PRESIDIO_ENABLED=false
```

## 5. 跑通方式

### 5.1 后端启动

```powershell
cd D:\mirofish\miro_cogsec-chm\backend
conda run -p "D:\mirofish\5_16以前\.conda_envs\mirofish_cogsec312" python run.py
```

健康检查：

```powershell
Invoke-WebRequest -Uri http://127.0.0.1:5001/health -UseBasicParsing
```

实际返回：

```json
{"service":"MiroFish Backend","status":"ok"}
```

### 5.2 单条 API Smoke Test

执行脚本：

```powershell
cd D:\mirofish\miro_cogsec-chm
conda run -p "D:\mirofish\5_16以前\.conda_envs\mirofish_cogsec312" python scripts\smoke_cogsec_http.py
```

测试样本：

```text
来电者自称公安机关，称账户涉嫌洗钱，要求全程保密并把资金转入安全账户接受核查。
```

响应保存位置：

```text
benchmark/outputs/api_one_result.json
```

### 5.3 前端启动

安装依赖：

```powershell
cd D:\mirofish\miro_cogsec-chm\frontend
conda run -p "D:\mirofish\5_16以前\.conda_envs\mirofish_cogsec312" npm ci --registry=https://registry.npmmirror.com
```

启动前端：

```powershell
conda run -p "D:\mirofish\5_16以前\.conda_envs\mirofish_cogsec312" npm run dev -- --host 127.0.0.1 --port 5174
```

页面检查：

```powershell
Invoke-WebRequest -Uri http://127.0.0.1:5174/ -UseBasicParsing
```

实际结果：HTTP `200 OK`，返回页面长度 `887`。

## 6. 跑通结果

### 6.1 后端服务

| 检查项 | 结果 |
|---|---|
| 后端进程启动 | 通过 |
| `/health` | 通过 |
| API 路由 `/api/cogsec/analyze` | 通过 |
| 响应 JSON 保存 | 通过 |

### 6.2 单条 API 响应摘要

| 字段 | 结果 |
|---|---|
| `success` | `true` |
| `scenario_type` | `authority_impersonation` |
| `overall_vulnerability_score` | `40.0` |
| `risk_level` | `HIGH` |
| `final_risk` | `55.0` |
| `fork_point_type` | `transfer_money` |
| `trajectory_gap` | `0.774` |
| `t0_fast_response.alert` | `true` |
| `t0_fast_response.summary` | 命中 1 条红旗片段，规则：`police_secrecy_isolation` |
| `best_intervention_window` | `open_step=1`，`close_step=2` |
| `end_to_end_ms` | `1312.07` |

### 6.3 前端服务

| 检查项 | 结果 |
|---|---|
| 前端依赖安装 | 通过 |
| Vite 服务启动 | 通过 |
| 首页 HTTP 访问 | 通过，`200 OK` |
| 前端默认 API 地址 | `http://localhost:5001` |

## 7. 外部 LLM API 验证结果

单独使用 `LLMClient` 对百炼兼容 OpenAI 接口做直连探针时，返回鉴权失败：

```text
openai.AuthenticationError: 401 invalid_api_key
Incorrect API key provided.
```

因此，本次 `/api/cogsec/analyze` 虽然成功返回结果，但不能判定为“外部 LLM 已接通”。从代码路径看，`CogSecService` 会在 LLM 调用异常时回退到启发式/规则链路，因此本次成功主要证明：

- 后端服务可运行
- API 路由可调用
- CogSec 规则链路可返回完整结构
- 前端服务可打开

但外部 LLM API Key 未通过鉴权。

## 8. 结论

| 项目 | 结论 |
|---|---|
| 后端运行状态 | 已跑通 |
| 单条 CogSec API 调用 | 已跑通 |
| 前端页面启动 | 已跑通 |
| 外部 LLM API 接入 | 未跑通，当前 key 鉴权失败 |
| Benchmark AQS 迁移 | 已完成，`AQI=0.993` |
| 20 条全量 API benchmark | 未执行，按需求仅跑 1 条 |

最终结论：系统的前后端基础运行链路和 CogSec API 返回链路已经可用；外部 LLM 真实接入尚未成功，需更换有效的百炼 API Key 后再做 LLM 模式测试。

## 9. 后续建议

1. 使用有效百炼 API Key 后，先执行 `LLMClient` 直连探针，确认返回正常文本。
2. 直连探针通过后，再跑 `scripts/smoke_cogsec_http.py` 做单条 API 验证。
3. 单条验证通过后，再考虑运行 `scripts/run_cogsec_api_benchmark.py --limit 20` 做全量 API benchmark。
4. 如需测试 OASIS 社交模拟链路，另建 Python 3.11 环境处理 `camel-oasis` 兼容性。

