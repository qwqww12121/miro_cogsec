# CogSec 配套 PPT 素材索引

本文档整理了 `COGSEC_COMPETITION_SUMMARY_REPOSITIONED.tex` 配套 PPT 可直接使用的素材、链接与代码证据，便于后续单独增删页面或二次排版。

## 输出文件

- 主生成脚本：`generate_cogsec_ppt.py`
- 生成结果：`COGSEC_COMPETITION_SUPPORT_DECK.pptx`
- 整理后的本地素材目录：`ppt_assets/`
- 兼容说明：输出为标准 `pptx`，可直接使用 WPS 演示打开和继续编辑

## 本地图片素材

### 1. 项目标识

- `ppt_assets/mirofish_logo.jpeg`
  - 来源：`../static/image/MiroFish_logo_compressed.jpeg`
  - 用途：封面页、MiroFish 底座说明页

### 2. 本地运行截图

- `ppt_assets/run_1.png`
  - 来源：`../static/image/Screenshot/运行截图1.png`
  - 内容：原始 MiroFish 首页与输入入口
  - 推荐页面：为什么基于 MiroFish

- `ppt_assets/run_3.png`
  - 来源：`../static/image/Screenshot/运行截图3.png`
  - 内容：图谱可视化 + 环境搭建/双栏工作流
  - 推荐页面：现有界面与产品形态证据

- `ppt_assets/run_6.png`
  - 来源：`../static/image/Screenshot/运行截图6.png`
  - 内容：复杂图谱和右侧节点详情面板
  - 推荐页面：图谱构建与解释性输出

## 可直接放进 PPT 的代码证据

### 1. 主链编排

- 文件：`../backend/app/services/cogsec_service.py`
- 重点：
  - `CogSecAnalysisResult`
  - `PrivacySanitizer`
  - `T0FastResponder`
  - `CognitiveProfileExtractor`
  - `ThreatKnowledgeRAG`
  - `MiroFishRuntime`
  - `RiskScorer`
  - `CounterfactualReporter`

### 2. 最小 Demo 入口

- 文件：`../backend/run_cogsec_demo.py`
- 重点：
  - `/health`
  - `/api/cogsec/sample`
  - `/api/cogsec/analyze`

### 3. 五屏工作台

- 文件：`../frontend/src/components/cogsec/CogSecWorkbench.vue`
- 重点：
  - 用户数字孪生
  - 攻击-人-环境图谱
  - 双分支反事实推演
  - 风险 / 可逆性曲线
  - 个性化干预处方

## 外部公开资料入口

### MiroFish / 开源相关

- MiroFish GitHub：
  - https://github.com/666ghj/MiroFish
- MiroFish-Offline：
  - https://github.com/nikmcfly/MiroFish-Offline
- Pretexta：
  - https://github.com/dalpan/Pretexta

### 竞品 / 产品页

- Bitdefender Scamio：
  - https://www.bitdefender.com/en-us/consumer/scamio
- Norton AI Scam Protection / Genie：
  - https://hk-en.norton.com/feature/ai-scam-protection
- SoSafe：
  - https://sosafe-awareness.com/products/phishing-simulations/
- KnowBe4 AIDA：
  - https://www.knowbe4.com/products/aida
- Adaptive Security：
  - https://www.adaptivesecurity.com/
- Microsoft Defender Phishing Triage Agent：
  - https://learn.microsoft.com/en-us/defender-xdr/phishing-triage-agent

### 理论 / 论文

- Frontiers 2025 双系统诈骗论文：
  - https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2025.1637935/full
- NIST Phish Scale：
  - https://www.nist.gov/publications/phishing-user-context-understanding-nist-phish-scale
- Social engineering cognition（PMC）：
  - https://pmc.ncbi.nlm.nih.gov/articles/PMC7554349/
- Digital deception：
  - https://link.springer.com/article/10.1007/s10462-024-10973-2
- Persuasion survey：
  - https://doi.org/10.48550/arXiv.2412.18488
- AXIS：
  - https://arxiv.org/abs/2505.17801

## 推荐 PPT 结构

1. 封面
2. 系统是做什么的
3. 为什么基于 MiroFish
4. 原版 MiroFish 与当前项目的差异
5. 同类竞品与开源调研
6. 为什么系统要这样设计
7. 总体架构与主链工作流
8. 现有界面与工作台证据
9. 关键代码证据
10. 创新点与差异化
11. 风险治理与迭代路线
12. 资料入口与结束页
