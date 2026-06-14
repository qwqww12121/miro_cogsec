# Fraud IM 样本审核清单 v0.1

本文件是 `fraud_im` 20 条样本的人工审核记录摘要。早期版本用于把 `silver_pending_review` 样本升级为 `gold_reviewed`；当前 20 条 fraud 样本已经完成审核，并已在 `benchmark/data/cogsec_v0.1.jsonl` 中标记为 `gold_reviewed`。

更完整的当前状态请见：

- `benchmark/reports/fraud_im_benchmark_v0.1.md`
- `benchmark/reports/benchmark_v0.1_report.md`

## 当前样本概况

| 项目 | 当前情况 |
|---|---|
| 样本数量 | 20 |
| 风险样本 | 14 |
| 低风险/正常样本 | 6 |
| 主要来源 | ChiFraud 17 条，TeleAntiFraud 2 条，NIST Phish Scale 1 条 |
| 当前审核状态 | 全部为 `gold_reviewed` |
| AQS | 1.0 |

## 审核标准

每条样本审核时主要检查：

| 检查项 | 要求 |
|---|---|
| 输入文本 | 清晰、已脱敏、能代表一个具体风险或正常场景 |
| 风险标签 | `is_fraud`、`fraud_type`、`risk_level` 与文本一致 |
| 证据 | `evidence_spans` 必须能在原文中找到 |
| 资产目标 | 资金、凭证、身份信息、设备控制权、社交支持等标注合理 |
| Fork 点 | 能说明用户在哪一步进入高风险路径 |
| 干预窗口 | 应早于转账、验证码泄露、屏幕共享、身份资料泄露等不可逆节点 |
| 反事实路径 | 高风险路径和安全路径逻辑清楚 |
| 不确定性 | 近似映射、来源限制、推断链条应写入 `uncertainty` |

## 逐条样本审核摘要

| ID | 场景类型 | 风险等级 | 资产目标 | Fork 点 | 审核结论 |
|---|---|---|---|---|---|
| cogsec-v0.1-001 | identity_asset_trade | high | identity, funds | private_contact_lure | 保留。关键分叉点调整为私域引流，较早于付款和身份资产交换。 |
| cogsec-v0.1-002 | cashout_or_credit_card_service | high | funds, credential | private_contact_lure | 保留。信用卡代还/养卡属于高风险灰黑产金融服务，私下联系是最早干预点。 |
| cogsec-v0.1-003 | gambling_recruitment | high | funds | private_contact_lure | 保留。赌博引流样本合理，联系接待/入群前是最早阻断点。 |
| cogsec-v0.1-004 | gambling_recruitment | high | funds | transfer_money | 保留。样本强调后续投注和资金转移，使用 nearest runtime fork。 |
| cogsec-v0.1-005 | withdrawal_unfreeze_scam | high | funds | transfer_money | 保留。提现/解冻骗局场景明确。 |
| cogsec-v0.1-006 | withdrawal_unfreeze_scam | critical | funds | transfer_money, fake_official_verification | 保留。连续贷款、充值、拉黑构成完整高风险链；不可逆节点已调整到 step 3。 |
| cogsec-v0.1-007 | loan_fraud | critical | identity, credential | identity_asset_exchange | 保留。无抵押秒放款、提交身份证银行卡照片构成身份和凭证风险。 |
| cogsec-v0.1-008 | fake_document_service | high | funds | private_contact_lure | 保留。假证明服务属于高风险非法服务诱导，私域联系是早期 fork。 |
| cogsec-v0.1-009 | fake_certificate_service | high | funds | private_contact_lure | 保留。与 008 相近，但仍提供非法证书交易风险覆盖。 |
| cogsec-v0.1-010 | fake_card_service | high | funds | transfer_money | 保留。高额度信用卡、包装费、通道费较典型，资金 fork 清楚。 |
| cogsec-v0.1-011 | illegal_goods_payment_risk | high | funds | transfer_money | 保留。偏非法交易风险，但用于覆盖非典型诈骗式认知诱导。 |
| cogsec-v0.1-012 | benign_public_info | low | 无 | no_fork_needed | 保留。正常低风险控制样本。 |
| cogsec-v0.1-013 | benign_public_notice | low | 无 | no_fork_needed | 保留。公开招投标信息，适合控制误报。 |
| cogsec-v0.1-014 | benign_public_notice | low | 无 | no_fork_needed | 保留。寻人启事类公开信息，当前文本已规范化。 |
| cogsec-v0.1-015 | benign_tech_article | low | 无 | no_fork_needed | 保留。技术文章正常样本。 |
| cogsec-v0.1-016 | benign_public_info | low | 无 | no_fork_needed | 保留。合同范本页面正常样本。 |
| cogsec-v0.1-017 | benign_public_info | low | 无 | no_fork_needed | 保留。企业服务介绍正常样本。 |
| cogsec-v0.1-018 | refund_impersonation | critical | credential, device_control | verification_code, screen_share | 保留。冒充客服、共享屏幕、银行卡和验证码均典型。 |
| cogsec-v0.1-019 | authority_impersonation | critical | funds, social_support | transfer_money, social_isolation | 保留。冒充公安、安全账户、保密要求都与 runtime direct 对齐。 |
| cogsec-v0.1-020 | phishing_email | high | credential | verification_code | 保留。密码钓鱼使用 `verification_code` 作为最近似 credential-leakage fork。 |

## 后续扩展建议

fraud_im 后续版本可以优先补充：

| 类型 | 建议数量 | 说明 |
|---|---:|---|
| 冒充客服/退款理赔 | 3-5 | 覆盖验证码、共享屏幕、银行卡信息 |
| 冒充公检法/权威机构 | 3-5 | 覆盖保密、恐惧、转安全账户 |
| 投资理财/杀猪盘 | 3-5 | 覆盖长期信任建立和多轮诱导 |
| 刷单返利 | 3-5 | 覆盖小额返利到大额垫付 |
| 钓鱼链接/账号凭证 | 3-5 | 覆盖密码、验证码、非官方链接 |
| 正常低风险样本 | 8-12 | 用于控制误报 |

public_opinion 和 event_propagation 已在 v0.1 中分别补充 5 条 seed gold，详见：

- `benchmark/data/public_opinion_v0.1.jsonl`
- `benchmark/data/event_propagation_v0.1.jsonl`
