"""CogSec 基准测试脚本。"""

from __future__ import annotations

import argparse
import json
import time
import tracemalloc
from pathlib import Path

from backend.app.cogsec_minimal_runtime import run_minimal_cogsec_analysis
from backend.app.modules.t0_fast_responder import T0FastResponder


def run_t0_benchmark(samples: int, responder: T0FastResponder) -> float:
    scenario = "公安要求保密并让我共享屏幕后转账到安全账户。"
    started = time.perf_counter()
    for _ in range(samples):
        responder.scan(scenario)
    elapsed = time.perf_counter() - started
    return (elapsed * 1000) / max(1, samples)


def run_pipeline_benchmark() -> float:
    scenario = (
        "对方冒充客服说我的快递丢失，需要马上退款。"
        "让我共享屏幕并把银行卡验证码发过去。"
    )
    started = time.perf_counter()
    run_minimal_cogsec_analysis(scenario_text=scenario)
    return time.perf_counter() - started


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark CogSec modules")
    parser.add_argument("--samples", type=int, default=1000)
    parser.add_argument("--output", type=Path, default=Path("data/cogsec_benchmark.json"))
    args = parser.parse_args()

    responder = T0FastResponder()
    tracemalloc.start()

    avg_t0_ms = run_t0_benchmark(args.samples, responder)
    e2e_seconds = run_pipeline_benchmark()
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    result = {
        "t0_avg_latency_ms": round(avg_t0_ms, 3),
        "t0_target_under_500ms": avg_t0_ms < 500.0,
        "end_to_end_seconds": round(e2e_seconds, 3),
        "end_to_end_target_under_30s": e2e_seconds < 30.0,
        "peak_memory_mb": round(peak / (1024 * 1024), 3),
        "peak_memory_target_under_2gb": peak < 2 * 1024 * 1024 * 1024,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"benchmark result saved: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
