# Miro-CogSec 输出偏好与训练边界

## 结论

仓库此前修好的主要是数据流、仿真 provenance、benchmark 泄露和渲染错误。这些改动是获得可信结果的前提，但不等于已经获得 RLHF 或人类偏好优势。

2026-08-06 的结构化输出改造提升了证据覆盖、动作完整度和盲测中的可执行性；它没有训练策略模型、没有基于偏好数据更新参数，也没有在线 reward 优化，因此准确名称应是“面向偏好维度的 Prompt/规划/渲染工程”，不是已经完成的 RLHF。

## 根因

当前系统的独特价值在上游：同一 `CanonicalCase` 和 `SocialState S0` 上，多 Agent/传播机制、RiskGraph、反事实分支和 OASIS 复核能产生单次网页 LLM 没有的机制证据。

历史链路的问题在最后一公里：丰富状态进入 `ReportState` 后，又被固定标题和固定句式压缩。网页端 LLM 的语言偏好对齐很强，因此上游推理更丰富并不自动带来更自然的最终回答。旧 `direct_llm` 也先输出结构化 JSON、再套同一模板，不能代表真正的网页端自然回答。

修订后的边界是：

```text
Canonical runtime / multi-agent simulation
  -> ReportState（事实与 provenance 硬边界）
  -> ResponsePlan（内容选择，不写最终文风）
  -> ReporterPolicy
       auto/main_llm      严格 grounded prompt，输出自然文本
       local_model        可选 0.7B/1.5B 类本地模型
       trained_policy     可选 SFT/DPO adapter
       deterministic      离线/异常回退
  -> 同一个 assistant_message
```

外部入口仍是 `POST /api/cogsec/analyze`。内部策略可替换不等于拆分产品接口。

## 小模型应该放在哪里

- 约 0.7B：适合做轻量内容规划、字段选择、长度/语气决策或候选排序；不建议把它作为唯一的中文最终写作者，复杂场景中更容易丢证据关系和生成模板腔。
- 约 1.5B：更适合作为本地最终 Reporter 的最低实用档。输入是受限 `ReportState + ResponsePlan`，不是整个日志；用 LoRA/QLoRA 做 Reporter SFT，再用真实成对偏好做 DPO。
- 主分析大模型：在没有足够训练数据时，默认用现有 OpenAI-compatible 客户端做 grounded final generation，最能立即验证“上游多 Agent 状态是否能转化为更好的人类回答”。

本地模型与主模型共用 `chat(...)` 契约。配置 `MIRO_REPORTER_MODEL_PATH` 和可选 `MIRO_REPORTER_ADAPTER_PATH` 后即可替换 Reporter，不改主 API。

## PPO 放在哪里

PPO 不应被当成一般的“权重分类器”。如果目标只是从若干指标学习一组排序权重，现有 pairwise linear ranker 或监督式上下文 ranker更直接、样本效率也更高。

PPO 的合理对象是多步干预策略：

```text
InterventionState_t
  -> InterventionAction_t（actor + target + action + timing + strength）
  -> proxy/OASIS environment
  -> InterventionState_t+1
  -> traceable reward
```

`backend/training/ppo/interface.py` 因此只定义干预策略的 state/action/environment/reward/trainer。环境和 trainer 必须真实注入；未配置时显式报错，不返回恒定零奖励或伪 `no_op`。

最终语言偏好优先采用 Reporter SFT/DPO。只有获得稳定的人类 reward model、足够轨迹和可复现环境后，才考虑 PPO；它不应成为当前输出自然度问题的第一切入点。

## 数据与评价

结构评分和人类偏好应分开：

- 硬约束：证据可追溯、动作不越权、proxy/OASIS 不混称、benchmark 不回流。
- 软偏好：自然、具体、简洁、机制清楚、建议可执行。

训练前先做同模型、同输入的盲 A/B：

1. `deterministic reporter` 对 `grounded main-LLM reporter`；
2. `direct web-style LLM` 对 `Miro ReportState + reporter`；
3. 按场景分层，记录胜/负/平以及自然度、证据、机制、行动性；
4. 保存真实 `assistant_message`，禁止从 benchmark 字段重建第二份答案；
5. 偏好数据留出按案例/措辞隔离的测试集，防止同义句泄露。

在没有这组新数据前，只能证明接口和边界已修好，不能声称人类偏好已经优于网页端 LLM。

## 当前状态

- 已完成：单一 Reporter 边界、严格 grounded prompt、LLM 重试与确定性回退、模型/Prompt/checkpoint provenance、直出 baseline、SFT/DPO/PPO 诚实接口。
- 未执行：SFT、DPO、PPO 正式训练。
- 未证明：0.7B/1.5B 微调后的偏好增益，以及当前 Miro 对网页端 LLM 的新一轮盲测优势。
