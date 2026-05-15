# GitHub Packaging Notes

这个目录是从 `MiroFish-main/MIRO_PERSONAL_TEST` 整理出的 GitHub 版本。

## 已保留

- 后端源码：`backend/`
- 前端源码：`frontend/`
- CogSec 主链模块：`backend/app/modules/`
- 测试：`tests/`
- 轻量数据：`data/*.json`、`data/*.cypher`
- 运行脚本：`scripts/`、`backend/scripts/`
- Docker 和本地启动配置：`Dockerfile`、`docker-compose.yml`、`.env.example`
- 项目文档：`README.md`、`README-EN.md`、`docs/`

## 已剔除

- `node_modules/`
- `frontend/dist/`
- `__pycache__/`
- `.pytest_cache/`
- 日志文件和 `backend/logs/`
- 本地模型权重 `models/`
- 本地向量库 `data/chroma_db/`
- 临时前端启动日志
- 原目录中的 `GITHUB/` 局部快照

## 提交前建议

在这个目录里初始化仓库：

```bash
git init
git add .
git commit -m "Initial MiroFish CogSec package"
```

首次运行前复制环境变量：

```bash
cp .env.example .env
```

如果只验证 CogSec 最小链路，可以不配置 Zep；如果要跑完整图谱和 OASIS 仿真，需要配置 `LLM_API_KEY` 和 `ZEP_API_KEY`。

