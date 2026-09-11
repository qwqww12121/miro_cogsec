"""Reproducible multi-seed orchestration for candidate-level OASIS checks."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from importlib import metadata
import os
from statistics import mean, pstdev
import sys
from typing import Any, Callable, Dict, Iterable, Mapping, Sequence

from .oasis_verification import run_topk_oasis_verification


@dataclass(frozen=True)
class OasisExperimentConfig:
    seeds: tuple[int, ...] = (42, 43, 44)
    top_k: int = 2
    quick_mode: bool = False
    require_shared_initial_world: bool = True
    require_oasis_metrics: bool = True

    def validate(self) -> None:
        if not self.seeds:
            raise ValueError("at least one OASIS seed is required")
        if len(set(self.seeds)) != len(self.seeds):
            raise ValueError("OASIS seeds must be unique")
        if self.top_k < 1:
            raise ValueError("top_k must be >= 1")


def oasis_environment_status() -> Dict[str, Any]:
    """Return a secret-free dependency/config preflight report."""
    packages = {}
    for package in ("camel-oasis", "camel-ai"):
        try:
            packages[package] = metadata.version(package)
        except metadata.PackageNotFoundError:
            packages[package] = None
    configured = {
        key: bool(os.environ.get(key))
        for key in (
            "MIRO_COGSEC_OASIS_API_KEY",
            "MIRO_COGSEC_OASIS_BASE_URL",
            "MIRO_COGSEC_OASIS_MODEL",
        )
    }
    try:
        from .oasis_adapter import _OASIS_AVAILABLE

        adapter_importable = bool(_OASIS_AVAILABLE)
    except Exception:
        adapter_importable = False
    python_ok = (3, 10) <= sys.version_info[:2] < (3, 12)
    ready = python_ok and all(packages.values()) and adapter_importable and all(configured.values())
    missing_packages = [name for name, version in packages.items() if not version]
    if ready:
        hint = "当前后端进程已接到 OASIS，分析时会走多智能体仿真。"
    elif missing_packages:
        hint = f"当前跑 Flask 的 Python 里没有 {', '.join(missing_packages)}。若它只装在 miro_test 里，请用那个环境启动后端。"
    elif not python_ok:
        hint = "OASIS 需要 Python 3.10 或 3.11。当前进程版本不匹配。"
    elif not all(configured.values()):
        hint = "后端已能导入 OASIS，但还缺 MIRO_COGSEC_OASIS_API_KEY / BASE_URL / MODEL。"
    elif not adapter_importable:
        hint = "camel-oasis 已安装，但适配器导入失败，请检查依赖是否完整。"
    else:
        hint = "OASIS 接口保留；本次分析走传播仿真。"
    return {
        "python": ".".join(str(item) for item in sys.version_info[:3]),
        "python_supported": python_ok,
        "executable": sys.executable,
        "packages": packages,
        "credentials_configured": configured,
        "adapter_importable": adapter_importable,
        "ready": ready,
        "hint": hint,
        "secrets_exposed": False,
    }


def run_multiseed_oasis_experiment(
    *,
    scenario_type: str,
    seed_text: str,
    agents: Sequence[Any],
    proxy_result: Dict[str, Any],
    snapshot: Any = None,
    simulation_state_id: str | None = None,
    config: OasisExperimentConfig | None = None,
    verification_runner: Callable[..., Dict[str, Any]] = run_topk_oasis_verification,
) -> Dict[str, Any]:
    """Run identical candidate verification under several random seeds.

    ``verification_runner`` is injectable so orchestration, aggregation and
    acceptance rules can be tested without calling a paid model.
    """
    cfg = config or OasisExperimentConfig()
    cfg.validate()
    runs = []
    for seed in cfg.seeds:
        result = verification_runner(
            scenario_type=scenario_type,
            seed_text=seed_text,
            agents=list(agents),
            proxy_result=proxy_result,
            quick_mode=cfg.quick_mode,
            k=cfg.top_k,
            seed=int(seed),
            snapshot=snapshot,
            simulation_state_id=simulation_state_id,
        )
        runs.append({"seed": int(seed), **result})

    completed = [run for run in runs if int(run.get("top_k_oasis_completed", 0)) > 0]
    shared_world = bool(simulation_state_id) and all(
        run.get("shared_initial_world") is True
        and run.get("simulation_state_id") == simulation_state_id
        for run in runs
    )
    utilities: dict[str, list[float]] = defaultdict(list)
    winners: Counter[str] = Counter()
    for run in completed:
        selected = run.get("selected") if isinstance(run.get("selected"), Mapping) else {}
        selected_id = str(selected.get("candidate_id") or "")
        if selected_id:
            winners[selected_id] += 1
        for branch in run.get("oasis_verified_branches", []):
            if not isinstance(branch, Mapping) or branch.get("metric_source") != "oasis":
                continue
            utility = branch.get("signed_utility")
            candidate_id = str(branch.get("candidate_id") or "")
            if candidate_id and isinstance(utility, (int, float)):
                utilities[candidate_id].append(float(utility))

    utility_summary = {
        candidate_id: {
            "runs": len(values),
            "mean": round(mean(values), 6),
            "stddev": round(pstdev(values), 6) if len(values) > 1 else 0.0,
            "min": round(min(values), 6),
            "max": round(max(values), 6),
        }
        for candidate_id, values in sorted(utilities.items())
    }
    acceptance_checks = {
        "all_seeds_completed": len(completed) == len(runs),
        "shared_initial_world": shared_world,
        "oasis_metrics_observed": bool(utilities),
        "candidate_level_results": all(
            isinstance(run.get("oasis_verified_branches"), list) for run in runs
        ),
    }
    accepted = (
        acceptance_checks["all_seeds_completed"]
        and (shared_world or not cfg.require_shared_initial_world)
        and (acceptance_checks["oasis_metrics_observed"] or not cfg.require_oasis_metrics)
    )
    return {
        "schema_version": "oasis_multiseed_experiment.v1",
        "scenario_type": scenario_type,
        "config": {
            "seeds": list(cfg.seeds),
            "top_k": cfg.top_k,
            "quick_mode": cfg.quick_mode,
            "require_shared_initial_world": cfg.require_shared_initial_world,
            "require_oasis_metrics": cfg.require_oasis_metrics,
        },
        "runs": runs,
        "completed_seeds": len(completed),
        "candidate_utility": utility_summary,
        "winner_frequency": dict(winners),
        "acceptance_checks": acceptance_checks,
        "accepted": accepted,
        "metric_source": "oasis" if utilities else "not_observed",
        "provenance": {
            "runner": getattr(verification_runner, "__name__", type(verification_runner).__name__),
            "proxy_scores_compared_to_oasis_scale": False,
            "shared_initial_state_id": simulation_state_id,
        },
    }
