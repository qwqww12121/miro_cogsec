# Miro-CogSec 前端

Vite + React + Tailwind。提供首页智能识别、三个场景分析页，以及对话式的「智能对话」页。

## 启动

需要后端已在 `localhost:5001` 运行。开发服务器把 `/api` 代理到后端，配置见 `vite.config.js`。

```bash
npm install
npm run dev
```

默认地址：http://localhost:3000

```bash
npm run build      # 输出到 dist/
npm run preview    # 预览构建结果
```

## 主要页面

| 路径 | 说明 |
|---|---|
| `/` | 首页：智能识别 + 手动进入场景 |
| `/chat` | 智能对话 |
| `/scenario/fraud-im` | 诈骗即时通讯 |
| `/scenario/public-opinion` | 舆情分析 |
| `/scenario/event-propagation` | 事件传播 |
| `/simulation-map` | 对照 / 关系图 |

智能识别调用真实接口 `POST /api/classify`。三个场景页和分析链路都走 `POST /api/cogsec/analyze`。

多模态输入（文件、可选语音）见 `src/components/MultimodalComposer.jsx`。语音服务是可选配置，变量名在仓库根目录 `.env.example` 的 `MIRO_SPEECH_*`。
