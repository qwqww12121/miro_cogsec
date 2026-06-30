# Closed-Model Judge — 迭代归档（v0.4 – v2.0）

本目录存放 Miro-CogSec 闭模裁判（closed-model judge）评测在 **v0.4 → v2.0** 开发过程中的全部迭代产物。
裁判模型统一为 **deepseek-v4-flash**，被评答案随版本演进（adapter 重建 → 语义帧 → 公共事件帧 → 直接动作报告）。

## 为什么归档在这里

这些文件是**开发 provenance（审计链）**，记录 miro 答案与裁判结果如何一步步演化，便于回溯。
它们**不是作品的头条数字**。早期对外提及的 **86.7% 胜率**（`v2.0_direct_actions`）即出自这里的最后一代，
但该数字使用的是偏松的同类裁判 deepseek-v4-flash（0 平局），未经公平条件校正。

## 官方（公平）结果在哪里

**不在这里。** 官方公平重跑结果在上一级目录的 3 个 `FAIR_v1.2` 文件：

- `../judge_requests_no_gold_FAIR_v1.2_norewrite.jsonl`
- `../judge_results_no_gold_FAIR_v1.2_qwen.jsonl`
- `../judge_summary_no_gold_FAIR_v1.2_qwen.json`

设置：miro=v1.2 重建（**未经 LLM 改写**）、baseline 不变、裁判换独立 **qwen3.7-plus**、同 30 题同 seed。
结果：**miro 18/30 = 60.0%**（7 平、llm 5 胜；miro 不败率 83%）。
完整说明见 `benchmark/reports/fair_rerun_report.md`。

## 两者的可追溯关系

本目录中的 `judge_requests_no_gold_v2.0_direct_actions.jsonl`（86% 那次的请求文件）与
官方公平重跑的请求文件 `judge_requests_no_gold_FAIR_v1.2_norewrite.jsonl` **逐字节相同** ——
即 86% 与 60% 评的是**同一批答案**，唯一变量是裁判模型（deepseek → qwen），构成干净的单变量对照。

## 关于改写脚本

v2 开发期曾存在一个对 miro 答案做 LLM 改写的脚本 `rewrite_miro_judge_reports.py`。
经逐字节取证，**86% 的最终候选并未流经该脚本**（= v1.2 adapter 重建 → 确定性 Python 渲染）。
出于评测诚信，该脚本**未纳入本最终仓库**。详见 `benchmark/reports/fair_rerun_report.md`。
