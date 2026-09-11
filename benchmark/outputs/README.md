# Benchmark 输出目录

本目录用于存放本地生成的评分结果：

- `aqs_v0.1.json` — 标注质量评分（`aqs` 命令）
- `run_v0.1.jsonl` — 运行时预测输出（`run` 命令）
- `metrics_v0.1.json` — 运行时评测输出（`evaluate` 命令）

这些文件不是固定标准答案，因此默认不提交。需要时在本地生成：

```bash
python benchmark/cogsec_benchmark.py aqs
python benchmark/cogsec_benchmark.py run
python benchmark/cogsec_benchmark.py evaluate
```
