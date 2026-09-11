"""Small standard-library helpers for paired benchmark uncertainty reports."""

from __future__ import annotations

import math
import random
import statistics
from collections import defaultdict
from typing import Any, Iterable, List, Mapping, Sequence


def paired_summary(
    miro: Sequence[float],
    baseline: Sequence[float],
    *,
    bootstrap_samples: int = 2000,
    seed: int = 42,
) -> dict[str, Any]:
    if len(miro) != len(baseline):
        raise ValueError("paired benchmark arrays must have equal length")
    deltas = [float(a) - float(b) for a, b in zip(miro, baseline)]
    if not deltas:
        return {"n": 0, "miro_mean": None, "baseline_mean": None, "paired_delta": None, "paired_delta_ci95": None}
    rng = random.Random(seed)
    means = []
    for _ in range(max(1, int(bootstrap_samples))):
        sample = [deltas[rng.randrange(len(deltas))] for _ in deltas]
        means.append(statistics.mean(sample))
    means.sort()
    return {
        "n": len(deltas),
        "miro_mean": round(statistics.mean(miro), 6),
        "miro_std": round(statistics.stdev(miro), 6) if len(miro) > 1 else 0.0,
        "baseline_mean": round(statistics.mean(baseline), 6),
        "baseline_std": round(statistics.stdev(baseline), 6) if len(baseline) > 1 else 0.0,
        "paired_delta": round(statistics.mean(deltas), 6),
        "paired_delta_ci95": [round(_quantile(means, 0.025), 6), round(_quantile(means, 0.975), 6)],
    }


def summarize_by_scenario(rows: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("scenario") or "unknown")].append(row)
    return {
        scenario: paired_summary(
            [float(row["miro"]) for row in items],
            [float(row["baseline"]) for row in items],
        )
        for scenario, items in sorted(grouped.items())
    }


def _quantile(values: Sequence[float], probability: float) -> float:
    if not values:
        return math.nan
    position = (len(values) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)
    fraction = position - lower
    return values[lower] + (values[upper] - values[lower]) * fraction
