# Fraud IM Benchmark v0.1 Report

本文档记录 `fraud_im` 场景在 Miro-CogSec benchmark v0.1 中的 gold 数据、标注原则、质量评分和当前 baseline 状态。

## Summary

`fraud_im` 面向电信诈骗、即时通讯诈骗、冒充客服、冒充公检法、刷单返利、虚假贷款、投资理财诈骗、钓鱼链接等场景。评测重点不是简单判断文本是否“像诈骗”，而是系统能否识别用户被推向的关键高风险动作，并在转账、验证码泄露、屏幕共享、未知 App 下载、社会隔离等不可逆或高损失节点前给出干预建议。

当前 v0.1 gold set 包含 20 条样本，均已人工复核为 `gold_reviewed`。其中 14 条为风险样本，6 条为低风险或正常控制样本。

| 项目 | 当前结果 |
|---|---:|
| Gold samples | 20 |
| Fraud / high-risk samples | 14 |
| Benign / low-risk samples | 6 |
| Human review status | 20 `gold_reviewed` |
| Annotation Quality Index | 1.0 |

## Data Sources

| 来源 | 数量 | 说明 |
|---|---:|---|
| ChiFraud | 17 | 公开中文诈骗/风险文本来源，覆盖短广告和公开页面样本 |
| TeleAntiFraud | 2 | 电话诈骗场景 taxonomy，覆盖冒充客服和冒充公检法 |
| NIST Phish Scale | 1 | 钓鱼邮件线索公开参考，构造凭据窃取样本 |

样本来源仅提供原文或粗粒度标签。`fork_points`、`intervention_window`、`asset_targets`、`counterfactual_expectation`、`expected_warning`、`expected_safe_action` 等 CogSec 字段均为本 benchmark 人工构造和复核的 gold annotation。

License notes:

| License / terms | 数量 |
|---|---:|
| `CC BY-NC 4.01` | 17 |
| `check_upstream_terms_before_redistribution` | 2 |
| `public_reference` | 1 |

## Label Distribution

### Risk Level

| Risk level | 数量 |
|---|---:|
| `critical` | 4 |
| `high` | 10 |
| `low` | 6 |

### Fraud Type

| Fraud type | 数量 |
|---|---:|
| `authority_impersonation` | 1 |
| `benign_public_info` | 3 |
| `benign_public_notice` | 2 |
| `benign_tech_article` | 1 |
| `cashout_or_credit_card_service` | 1 |
| `fake_card_service` | 1 |
| `fake_certificate_service` | 1 |
| `fake_document_service` | 1 |
| `gambling_recruitment` | 2 |
| `identity_asset_trade` | 1 |
| `illegal_goods_payment_risk` | 1 |
| `loan_fraud` | 1 |
| `phishing_email` | 1 |
| `refund_impersonation` | 1 |
| `withdrawal_unfreeze_scam` | 2 |

### Input Channel

| Channel | 数量 |
|---|---:|
| `short_text_ad` | 10 |
| `dialogue_summary` | 2 |
| `email_summary` | 1 |
| `narrative_case` | 1 |
| `public_info` | 3 |
| `public_notice` | 2 |
| `software_article` | 1 |

## Annotation Principles

`fraud_im` gold annotation follows these principles:

- `fork_point` marks the earliest meaningful branching point where the user could enter a dangerous path.
- `irreversible_nodes` mark truly high-loss or hard-to-reverse operations, such as transfer, verification-code leakage, screen sharing, credential disclosure, identity asset exchange, or isolation from help.
- `intervention_window` should close before the irreversible node whenever the text provides enough sequence information.
- `expected_warning` and `expected_safe_action` should be concrete enough for a user-facing assistant or safety system.
- `uncertainty` records unsupported inference, source limitation, and runtime alignment gaps instead of hiding them.

## Fork And Asset Coverage

### Fork Types

| Fork type | 数量 |
|---|---:|
| `transfer_money` | 6 |
| `private_contact_lure` | 5 |
| `no_fork_needed` | 6 |
| `verification_code` | 2 |
| `fake_official_verification` | 1 |
| `identity_asset_exchange` | 1 |
| `screen_share` | 1 |
| `social_isolation` | 1 |

Some samples contain more than one fork point, so fork totals can exceed case totals.

### Runtime Alignment

| Alignment | 数量 |
|---|---:|
| `direct` | 15 |
| `nearest` | 2 |
| `unsupported` | 6 |

`direct` means the benchmark fork type can be consumed by the current runtime. `nearest` means the benchmark uses the closest available runtime type. `unsupported` means the gold annotation captures a scenario-relevant semantic fork that is not yet represented in runtime fork rules.

Current unsupported or partial-alignment areas:

- `private_contact_lure`: private-channel migration is important for short ads and group recruitment, but current runtime is still more transfer-centric.
- `identity_asset_exchange`: illegal phone-card or identity-asset exchange is semantically different from ordinary money transfer.
- `phishing_email`: credential capture is currently mapped to `verification_code` as the nearest runtime credential-leakage fork.

### Asset Types

| Asset type | 数量 |
|---|---:|
| `funds` | 12 |
| `credential` | 4 |
| `identity` | 2 |
| `device_control` | 1 |
| `social_support` | 1 |

## Annotation Quality

Latest command:

```powershell
py benchmark\cogsec_benchmark.py validate
py benchmark\cogsec_benchmark.py aqs
```

Current result:

| Metric | Score |
|---|---:|
| ECR | 1.0 |
| FVS | 1.0 |
| WCS | 1.0 |
| TRS | 1.0 |
| RFS | 1.0 |
| AQI | 1.0 |

Interpretation:

- Evidence spans are traceable to the input text.
- Fork types and runtime alignment metadata are structurally valid.
- Intervention windows close before irreversible nodes.
- Evidence references are internally consistent.
- Required rich fields are present.

## Baseline Experiment Status

v0.1 uses three experiment layers:

| Layer | Name | Status |
|---|---|---|
| Reference | Human Annotation / Expert Review | Completed for 20 gold samples |
| Baseline | LLM-only Prompting | Prompt and output collection pending |
| Method | Miro-CogSec Full Pipeline | API run pending; previous local smoke results are not submitted as benchmark artifacts |

### Miro-CogSec Full Pipeline

No API output files are submitted as current benchmark artifacts. A previous local smoke run covered 3 / 20 cases and is kept only as a development note.

Because only 3 cases were run through the API path earlier, those metrics should be treated as a smoke-test signal rather than a final runtime baseline. They are not part of the current cleaned benchmark submission.

Previous local smoke metrics, for reference only:

| Metric | Value |
|---|---:|
| Runtime success rate | 15.0 |
| FPA | 100.0 |
| ATA | 66.67 |
| CPA | 50.0 |
| IWA | 100.0 |
| RCA | 100.0 |
| EAR | 0.0 |
| RES | 0.7 |

The success rate is low because metrics are computed over 20 gold cases while only 3 API outputs are present. The next required runtime step is a full 20-case API run.

Recommended command:

```powershell
C:\Users\19579\.conda\envs\miro-cogsec\python.exe scripts\run_cogsec_api_benchmark.py
```

## Known Gaps

- The current gold set is small and intentionally focused on controlled, inspectable samples.
- Short-text ads are overrepresented relative to full multi-turn conversations.
- Some semantic fork types are ahead of the current runtime fork rules.
- Normal control samples have no evidence pack by design, but later versions may add explicit benign evidence fields.
- LLM-only baseline prompts and outputs are not yet collected.
- Full 20-case API baseline is still pending.

## Next Steps

1. Run the full 20-case API benchmark and regenerate `api_run_v0.1.jsonl` plus `api_metrics_v0.1.json`.
2. Add `llm_baseline_fraud_im.md` and collect LLM-only outputs for the same 20 gold samples.
3. Summarize per-case runtime alignment gaps, especially private-contact lure, identity-asset exchange, and phishing credential capture.
4. Link this report from the three-scenario report once `public_opinion` and `event_propagation` seed gold files are created.
