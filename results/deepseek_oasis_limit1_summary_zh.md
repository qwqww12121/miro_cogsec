# DeepSeek API / OASIS Smoke 结果

## 运行方式

本次没有把 API key 写入代码或配置文件，只在命令进程环境变量中临时设置：

- `LLM_API_KEY`
- `OPENAI_API_KEY`
- `DEEPSEEK_API_KEY`
- `LLM_BASE_URL=https://api.deepseek.com`
- `OPENAI_BASE_URL=https://api.deepseek.com`
- `LLM_MODEL_NAME=deepseek-v4-flash`

运行场景：

```powershell
conda run -n ai_basic python scripts\run_scenario_api_benchmark.py --scenario public_opinion --limit 1 --disable-chroma --no-local-gemma
```

## 结果

| 指标 | 数值 |
|---|---:|
| 场景 | `public_opinion` |
| 样本数 | 1 |
| Runtime Success | 100.0 |
| Scenario Match | 100.0 |
| Propagation Present | 100.0 |
| OASIS engine | `oasis` |
| Branch A OASIS driven | true |
| Branch B OASIS driven | true |
| Latency | 126211.193 ms |
| Complete Schema | 100.0 |
| Answer RES | 0.777 |
| Mechanistic Score | 100.0 |
| OASIS Runtime Grounding | 100.0 |
| Counterfactual Branch Count | 4 |
| Counterfactual branch metric source | `proxy` |

## 输出文件

- `benchmark/outputs/api_public_opinion_deepseek_oasis_limit1_v0.1.jsonl`
- `benchmark/outputs/api_public_opinion_deepseek_oasis_limit1_scores_v0.1.json`
- `benchmark/outputs/api_public_opinion_deepseek_oasis_limit1_smoke_v0.1.json`
- `benchmark/outputs/api_public_opinion_deepseek_oasis_limit1_mechanistic_v0.1.json`

## 结论

DeepSeek API 已经可以驱动 OASIS baseline propagation 的 branch A/B，且不再 fallback 到 lightweight。当前多候选 intervention search 仍然使用本地 proxy branch runner，因此不能声称已经完成 full OASIS per-candidate counterfactual branches。

下一步如果继续升级，应把 `propagation_intervention_search` 中的每个 candidate 也交给 OASIS 运行，而不是只让 baseline branch A/B 走 OASIS。
