"""OASIS propagation adapter — real multi-agent social simulation.

Round 2 Completion upgrade:
- Single graph generation with DB copy for A/B equivalence (when supported)
- Per-tick action binding via DB row-id windowing
- Active-agent scheduling to reduce LLM calls
- Honest counterfactual initialization status tracking
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import csv
import json
import os
import shutil
import sqlite3
import tempfile
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from .schema import (
    ForkedPropagationResult,
    PropagationAction,
    PropagationAgent,
    PropagationEvent,
    PropagationTrace,
)
from ..social_state.behavior import actor_state_persona_summary

try:
    from camel.models import OpenAICompatibleModel
    from oasis import generate_twitter_agent_graph, DefaultPlatformType
    from oasis.environment.env import OasisEnv
    from oasis.environment.env_action import LLMAction, ManualAction
    from oasis.social_platform.typing import ActionType
    _OASIS_AVAILABLE = True
except ImportError:
    _OASIS_AVAILABLE = False


class UnsupportedOasisIntervention(ValueError):
    """Raised when a caller requests an action outside the adapter contract."""


class OasisTimeout(TimeoutError):
    """Wall-clock OASIS budget exhausted; callers should fall back immediately."""


def oasis_timeout_sec() -> float:
    return max(0.5, float(os.environ.get("MIRO_OASIS_TIMEOUT_SEC", "10")))


def is_oasis_timeout(exc: BaseException) -> bool:
    if isinstance(exc, OasisTimeout):
        return True
    if isinstance(exc, TimeoutError):
        return True
    return "timeout" in str(exc).lower()


# ============================================================================
# Counterfactual initialization status — honest tracking
# ============================================================================

@dataclass
class CounterfactualInitStatus:
    """Tracks what is and isn't guaranteed about Branch A/B initial state."""
    actor_equivalence: str = "guaranteed"          # same CSV + same actor_ids
    profile_equivalence: str = "guaranteed"         # same CSV content
    initial_event_equivalence: str = "guaranteed"   # same seed_text
    db_state_equivalence: str = "best_effort"        # DB-level state identity
    agent_graph_equivalence: str = "best_effort"    # LLM graph gen may differ
    # The adapter cannot guarantee graph identity when OASIS regenerates a
    # branch graph; keep this explicit for downstream counterfactual metrics.
    graph_equivalence: str = "not_guaranteed"
    random_seed: int = 42
    seed_equivalence: str = "best_effort"           # seed passed but LLM may ignore
    platform: str = "TWITTER"
    db_copy_method: str = "none"                    # none | post_init_copy | per_branch_generate
    initialization_method: str = "per_branch_generate"
    topology_source: str = "oasis_generated_from_profiles"
    social_state_topology_injected: bool = False
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        from dataclasses import asdict as _asdict
        return _asdict(self)


# ============================================================================
# Role descriptions
# ============================================================================

_ROLE_CHARS: Dict[str, str] = {
    "student_kol": "你是一名在校大学生，关注热点话题，粉丝较多，喜欢转发和评论社会新闻；你会根据当前证据和互动判断是否传播。",
    "ordinary_student": "你是一名普通学生，偶尔刷社交媒体，看到感兴趣的内容会点赞，有时会转发给朋友。",
    "teacher": "你是一名高校教师，重视信息准确性，会核实信息来源，不轻易传播未经证实的消息。",
    "school_official": "你是学校官方账号，负责发布权威信息，会及时辟谣和澄清不实消息。",
    "media_observer": "你是一名媒体观察员，关注舆情动态，会分析信息传播路径，有时会撰写评论文章。",
    "anonymous_amplifier": "你是一个匿名账号，常参与争议话题并关注讨论热度；是否传播取决于当前认知状态。",
    "original_poster": "你是这条信息的首发者，会根据自己掌握的证据和互动反馈决定是否继续传播。",
    "repost_kol": "你是一名有影响力的大V，看到重要消息会迅速转发，你的转发会引发大量关注。",
    "ordinary_viewer": "你是普通网民，偶尔刷社交媒体，对感兴趣的内容会点赞，有时也会转发。",
    "fact_checker": "你是一名事实核查员，专门验证网络信息的真实性，发现谣言会及时辟谣。",
    "official_responder": "你是政府或权威机构的官方发言人，负责发布权威声明，澄清虚假信息。",
    "controversy_amplifier": "你是一个喜欢制造争议的账号，会夸大事实，引发情绪化讨论。",
    "victim": "你是诈骗受害者，正在经历一场紧张的诈骗过程，感到困惑和恐慌。",
    "attacker": "你是诈骗者，正在实施诈骗，试图让受害者相信你并按你的要求行动。",
    "family_member": "你是受害者的家人，担心家人的安全，试图联系和劝阻。",
    "platform_moderator": "你是平台审核员，负责监控违规内容，发现违规会及时处理。",
    "police_or_bank": "你是警方或银行工作人员，负责提醒用户注意防范诈骗。",
}

_DEFAULT_INTERVENTION_CONTENT = {
    "public_opinion": "【官方辟谣】网络流传的相关信息经核实存在严重失实，请广大网友不信谣、不传谣。如有疑问请拨打官方热线核实。",
    "event_propagation": "【权威发布】关于近期网络流传信息，经相关部门核查，部分内容存在夸大和失实。以官方渠道发布信息为准，请理性看待。",
}

_INTERVENTION_DESCRIPTIONS: Dict[str, str] = {
    "official_response": "官方澄清公告注入",
    "community_note": "社区注释/更正内容注入",
    "node_targeting": "针对特定传播节点的干预",
    "warning": "警告/审核通知注入",
}

_INTERVENTION_MESSAGE_TEMPLATES: Dict[str, str] = {
    "official_response": "【官方声明】经核实，相关信息存在不实内容。请以官方渠道发布的权威信息为准。",
    "community_note": "【社区注释】此内容已由社区核实存在争议。建议参考多方来源后理性判断。",
    "node_targeting": "【事实核查】此信息传播路径中的关键节点已被标记，内容真实性待核实。",
    "warning": "【内容警告】此信息可能包含未经证实的内容。请在转发前核实信息真实性。",
}


def _build_intervention_message(
    scenario_type: str,
    evidence_refs: Optional[List[str]] = None,
) -> str:
    """Build an evidence-grounded intervention message."""
    base = _DEFAULT_INTERVENTION_CONTENT.get(
        scenario_type, _DEFAULT_INTERVENTION_CONTENT["public_opinion"]
    )
    if evidence_refs:
        refs_text = "；".join(evidence_refs[:3])
        base = base.rstrip("。") + f"。具体依据：{refs_text}。"
    return base


# ============================================================================
# Trace retention
# ============================================================================

_OASIS_TRACE_RETENTION = os.environ.get("OASIS_TRACE_RETENTION", "metadata")
_TRACE_DIR = os.environ.get(
    "OASIS_TRACE_DIR",
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "data", "oasis_traces"),
)


def _save_trace_metadata(
    run_id: str, branch_id: str, init_status: Dict[str, Any],
    tick_actions: Dict[int, List[Dict]], metrics: Dict[str, Any],
) -> None:
    if _OASIS_TRACE_RETENTION == "none":
        return
    os.makedirs(_TRACE_DIR, exist_ok=True)
    meta = {
        "run_id": run_id, "branch_id": branch_id,
        "counterfactual_init": init_status,
        "tick_summary": {str(t): len(a) for t, a in tick_actions.items()},
        "metrics": metrics, "timestamp": time.time(),
    }
    path = os.path.join(_TRACE_DIR, f"{run_id}_{branch_id}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, default=str, indent=2)


# ============================================================================
# Adapter
# ============================================================================


class OasisPropagationAdapter:
    """OASIS multi-agent social simulation adapter.

    Round 2 Completion: single graph generation with DB copy, per-tick
    action binding, active-agent scheduling, honest status tracking.
    """

    def __init__(self):
        # Per-branch action records keyed by tick
        self._tick_actions_a: Dict[int, List[Dict]] = defaultdict(list)
        self._tick_actions_b: Dict[int, List[Dict]] = defaultdict(list)
        # Init status
        self._init_status = CounterfactualInitStatus()
        # Scheduling stats
        self._scheduling_stats_a: Dict[str, int] = {}
        self._scheduling_stats_b: Dict[str, int] = {}
        self._action_diagnostics_a: Dict[str, Any] = self._new_action_diagnostics()
        self._action_diagnostics_b: Dict[str, Any] = self._new_action_diagnostics()

    def is_available(self) -> bool:
        return _OASIS_AVAILABLE

    # ==================================================================
    # Public entry point
    # ==================================================================

    def run(
        self,
        event: PropagationEvent,
        agents: List[PropagationAgent],
        scenario_type: str = "public_opinion",
        n_ticks: int = 5,
        intervention_tick: int = 2,
        llm_api_key: Optional[str] = None,
        llm_base_url: Optional[str] = None,
        llm_model_name: Optional[str] = None,
        snapshot: Any = None,
        evidence_refs: Optional[List[str]] = None,
        seed: int = 42,
        intervention: Optional[Dict[str, Any]] = None,
    ) -> ForkedPropagationResult:
        intervention_payload = intervention or {}
        intervention_type = intervention_payload.get("intervention_type", "official_response")
        target_nodes = intervention_payload.get("target_nodes") or []
        if intervention_type != "official_response" or target_nodes:
            raise UnsupportedOasisIntervention(
                "unsupported_oasis_intervention: only official_response "
                "with target_nodes=[] is supported"
            )
        if not _OASIS_AVAILABLE:
            raise RuntimeError("camel-oasis 未安装，无法运行 OASIS 仿真。")
        timeout_sec = oasis_timeout_sec()
        payload = dict(
            event=event, agents=agents, scenario_type=scenario_type,
            n_ticks=n_ticks, intervention_tick=intervention_tick,
            llm_api_key=llm_api_key, llm_base_url=llm_base_url,
            llm_model_name=llm_model_name, snapshot=snapshot,
            evidence_refs=evidence_refs, seed=seed,
            intervention=intervention,
        )

        def _invoke():
            return asyncio.run(asyncio.wait_for(
                self._run_forked(**payload),
                timeout=timeout_sec,
            ))

        # Wall-clock budget: do not wait for the OASIS thread after timeout.
        # asyncio.wait_for alone cannot interrupt blocking provider calls.
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        future = executor.submit(_invoke)
        try:
            return future.result(timeout=timeout_sec)
        except concurrent.futures.TimeoutError as exc:
            raise OasisTimeout(f"OASIS exceeded {timeout_sec}s") from exc
        except TimeoutError as exc:
            raise OasisTimeout(f"OASIS exceeded {timeout_sec}s") from exc
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    # ==================================================================
    # Forked run — single graph generation with DB copy
    # ==================================================================

    async def _run_forked(
        self,
        event: PropagationEvent,
        agents: List[PropagationAgent],
        scenario_type: str,
        n_ticks: int,
        intervention_tick: int,
        llm_api_key: Optional[str],
        llm_base_url: Optional[str],
        llm_model_name: Optional[str],
        snapshot: Any,
        evidence_refs: Optional[List[str]],
        seed: int,
        intervention: Optional[Dict[str, Any]] = None,
    ) -> ForkedPropagationResult:
        model = self._build_model(llm_api_key, llm_base_url, llm_model_name, seed)
        csv_path, db_a, db_b, tmpdir = self._prepare_paths()

        # Write CSV once
        self._write_agent_csv(agents, csv_path)

        # Reset status
        self._init_status = CounterfactualInitStatus(
            platform="TWITTER",
            seed_equivalence="best_effort",
        )
        if snapshot is not None:
            self._init_status.notes.append(
                "SocialState snapshot retained as context; OASIS generates the topology "
                "from agent profiles and does not inject the SocialState topology."
            )

        try:
            # --- Attempt 1: generate graph once, copy initialized DB ---
            db_copy_succeeded = await self._try_single_graph_with_db_copy(
                csv_path, db_a, db_b, model, event, agents, n_ticks
            )
            if db_copy_succeeded:
                self._init_status.db_state_equivalence = "guaranteed"
                # Branch execution still reopens/regenerates the graph object;
                # DB identity is guaranteed, graph-object identity is not.
                self._init_status.agent_graph_equivalence = "best_effort"
                self._init_status.db_copy_method = "post_init_copy"
                self._init_status.initialization_method = "db_copy"
                self._init_status.notes.append(
                    "Graph generated once; Branch A/B use copies of the same initialized DB."
                )
            else:
                # --- Fallback: per-branch generation ---
                self._init_status.db_state_equivalence = "best_effort"
                self._init_status.agent_graph_equivalence = "best_effort"
                self._init_status.db_copy_method = "per_branch_generate"
                self._init_status.initialization_method = "per_branch_generate"
                self._init_status.notes.append(
                    "DB copy failed or OASIS API does not support DB reuse; "
                    "graph was generated separately for each branch. "
                    "Same CSV + same seed used for both branches. "
                    "Both branches receive identical seed event. "
                    "LLM non-determinism may produce different agent graphs."
                )

            # Run Branch A (no intervention)
            self._tick_actions_a = defaultdict(list)
            self._scheduling_stats_a = {}
            self._action_diagnostics_a = self._new_action_diagnostics()
            trace_a = await self._run_branch_from_db(
                db_path=db_a, model=model, event=event, agents=agents,
                n_ticks=n_ticks, intervention_tick=None, scenario_type=scenario_type,
                branch_id="A", seed=seed, evidence_refs=evidence_refs,
                intervention=intervention,
            )
            self._ensure_branch_has_llm_outcomes("A")

            # Run Branch B — if DB copy succeeded, B starts from identical state
            self._tick_actions_b = defaultdict(list)
            self._scheduling_stats_b = {}
            self._action_diagnostics_b = self._new_action_diagnostics()
            trace_b = await self._run_branch_from_db(
                db_path=db_b, model=model, event=event, agents=agents,
                n_ticks=n_ticks, intervention_tick=intervention_tick,
                scenario_type=scenario_type, branch_id="B", seed=seed,
                evidence_refs=evidence_refs,
                intervention=intervention,
            )
            self._ensure_branch_has_llm_outcomes("B")
        finally:
            self._cleanup(tmpdir, db_a, db_b)

        # Build comparison with candidate-specific fork point
        intervention_type = (intervention or {}).get("intervention_type", "official_response")
        intervention_desc = _INTERVENTION_DESCRIPTIONS.get(intervention_type, "干预注入")
        fork_point = {
            "tick": intervention_tick,
            "type": intervention_type,
            "description": intervention_desc,
            "evidence_refs": evidence_refs or [],
            "intervention_message": (intervention or {}).get("message", ""),
            "target_nodes": (intervention or {}).get("target_nodes", []),
        }
        comparison = self._compare_traces(trace_a, trace_b)

        # Attach init status and scheduling stats to comparison
        comparison["counterfactual_initialization"] = self._init_status.to_dict()
        comparison["scheduling"] = {
            "branch_a": self._scheduling_stats_a,
            "branch_b": self._scheduling_stats_b,
        }
        comparison["action_diagnostics"] = {
            "branch_a": self._action_diagnostics_a,
            "branch_b": self._action_diagnostics_b,
        }

        return ForkedPropagationResult(
            fork_point=fork_point, branch_a=trace_a, branch_b=trace_b,
            comparison=comparison,
        )

    def _make_oasis_env(self, agent_graph, database_path: str):
        """Build OasisEnv without downloading local recsys models.

        DefaultPlatformType.TWITTER hardcodes recsys_type=twhin-bert, which
        loads paraphrase-MiniLM-L6-v2 or Twitter/twhin-bert-base from Hugging
        Face on the first recommendation refresh. Agent LLMs already use
        MIRO_COGSEC_OASIS_*; recsys does not need a second local model.

        MIRO_OASIS_RECSYS:
          random (default) — no embedding download, Twitter agent graph kept
          reddit — same, Reddit-style rec table
          twhin-openai — TWHIN recsys with OpenAI embeddings (needs embedding API)
          twhin — original local Hugging Face path
        """
        from oasis.social_platform.channel import Channel
        from oasis.social_platform.platform import Platform

        recsys = os.environ.get("MIRO_OASIS_RECSYS", "random").strip().lower() or "random"
        channel = Channel()
        if recsys in {"twhin", "twhin-bert", "twhin-openai", "openai"}:
            platform = Platform(
                db_path=database_path,
                channel=channel,
                recsys_type="twhin-bert",
                refresh_rec_post_count=2,
                max_rec_post_len=2,
                following_post_count=3,
                use_openai_embedding=recsys in {"twhin-openai", "openai"},
            )
        elif recsys == "reddit":
            platform = Platform(
                db_path=database_path,
                channel=channel,
                recsys_type="reddit",
                allow_self_rating=True,
                show_score=True,
                max_rec_post_len=100,
                refresh_rec_post_count=5,
            )
        else:
            platform = Platform(
                db_path=database_path,
                channel=channel,
                recsys_type="random",
                refresh_rec_post_count=2,
                max_rec_post_len=2,
                following_post_count=3,
            )
        if hasattr(self, "_init_status") and self._init_status is not None:
            self._init_status.notes.append(f"oasis_recsys={recsys}")
        return OasisEnv(
            agent_graph=agent_graph,
            platform=platform,
            database_path=database_path,
        )

    # ==================================================================
    # Single graph generation with DB copy
    # ==================================================================

    async def _try_single_graph_with_db_copy(
        self, csv_path: str, db_a: str, db_b: str,
        model: Any, event: PropagationEvent,
        agents: List[PropagationAgent], n_ticks: int,
    ) -> bool:
        """Attempt to generate graph once and copy the initialized DB.

        Returns True if both branches now have identical starting states.
        Returns False if we must fall back to per-branch generation.
        """
        try:
            from oasis.social_platform.typing import ActionType as AT
        except ImportError:
            return False

        available = [AT.CREATE_POST, AT.REPOST, AT.LIKE_POST, AT.DO_NOTHING]

        try:
            # Generate agent graph once
            agent_graph = await generate_twitter_agent_graph(
                profile_path=csv_path, model=model, available_actions=available,
            )

            # Create env pointing to db_a. Do not pass DefaultPlatformType.TWITTER:
            # that constructor hardcodes twhin-bert and downloads Hugging Face models.
            env = self._make_oasis_env(agent_graph, db_a)
            await env.reset()

            # Seed post
            all_agents = [a for _, a in agent_graph.get_agents()]
            self._validate_agent_alignment(all_agents, agents)
            seed_actions = {
                all_agents[0]: ManualAction(
                    action_type=AT.CREATE_POST,
                    action_args={"content": event.seed_text},
                )
            }
            await env.step(seed_actions)

            # Close env to flush DB
            await env.close()

            # Copy initialized DB from A → B
            if os.path.exists(db_a):
                shutil.copy2(db_a, db_b)

            return os.path.exists(db_a) and os.path.exists(db_b)

        except Exception as exc:
            self._record_action_failure("A", exc)
            return False

    # ==================================================================
    # Run branch from an existing (possibly copied) DB
    # ==================================================================

    async def _run_branch_from_db(
        self,
        db_path: str, model: Any, event: PropagationEvent,
        agents: List[PropagationAgent], n_ticks: int,
        intervention_tick: Optional[int], scenario_type: str,
        branch_id: str, seed: int,
        evidence_refs: Optional[List[str]] = None,
        intervention: Optional[Dict[str, Any]] = None,
    ) -> PropagationTrace:
        from oasis.social_platform.typing import ActionType as AT

        available = [AT.CREATE_POST, AT.REPOST, AT.LIKE_POST, AT.DO_NOTHING]

        # If DB was copied, we need to regenerate graph (or reopen from DB)
        # Since OASIS requires agent_graph for env creation, generate it again
        # from same CSV. If graph gen is deterministic enough this is fine.
        csv_path = os.path.join(os.path.dirname(db_path), "agents.csv")
        agent_graph = await generate_twitter_agent_graph(
            profile_path=csv_path, model=model, available_actions=available,
        )

        env = self._make_oasis_env(agent_graph, db_path)
        await env.reset()

        all_agents = [a for _, a in agent_graph.get_agents()]
        self._validate_agent_alignment(all_agents, agents)
        n_agents = len(agents)

        # Track previous tick's spreaders for scheduling
        prev_spreaders: Set[int] = set()

        # Track row ID windows for per-tick DB binding
        last_post_max_id = self._get_max_row_id(db_path, "post")
        last_trace_max_id = self._get_max_row_id(db_path, "trace")

        # Reset after seed post / existing initialization
        # In DB-copy mode, seed post was already applied in _try_single_graph_with_db_copy.
        # In per_branch_generate mode, BOTH branches must receive the same seed event
        # to ensure A/B initial state equivalence.
        if self._init_status.db_copy_method == "per_branch_generate":
            seed_actions = {
                all_agents[0]: ManualAction(
                    action_type=AT.CREATE_POST,
                    action_args={"content": event.seed_text},
                )
            }
            await env.step(seed_actions)
            self._record_tick_action(branch_id, 0, agents[0].agent_id if agents else "unknown",
                                     "seed_post", "broadcast")

        # Determine scheduler reason for seed/source agents
        seed_agent_idx = 0
        official_indices: Set[int] = set()
        official_roles = {"official_responder", "school_official", "police_or_bank", "fact_checker"}
        for i, pa in enumerate(agents):
            if pa.role in official_roles:
                official_indices.add(i)

        # Identify key nodes (high influence agents)
        sorted_by_inf = sorted(enumerate(agents), key=lambda x: x[1].influence, reverse=True)
        key_indices: Set[int] = {i for i, _ in sorted_by_inf[: max(1, n_agents // 5)]}

        # ================================================================
        # Main simulation loop
        # ================================================================
        for tick in range(n_ticks):
            # --- Determine which agents need LLM calls (active scheduling) ---
            agents_to_schedule: Set[int] = set()
            schedule_reasons: Dict[int, str] = {}

            for i in range(n_agents):
                reason = None
                # 1. Seed source / official actor — always active
                if i == seed_agent_idx or i in official_indices:
                    reason = "source_or_official"
                # 2. Had new info this tick (intervention tick for B)
                elif intervention_tick is not None and tick == intervention_tick:
                    reason = "new_information"
                # 3. Neighbor spread in previous tick
                elif i in prev_spreaders:
                    reason = "previously_active"
                # 4. Key node
                elif i in key_indices and tick > 0:
                    reason = "key_node"
                # 5. Intervention target (official agent)
                elif intervention_tick is not None and tick == intervention_tick and i in official_indices:
                    reason = "intervention_target"

                if reason:
                    agents_to_schedule.add(i)
                    schedule_reasons[i] = reason

            # Build actions
            step_actions: Dict[Any, Any] = {}
            for i, oa in enumerate(all_agents):
                if i in agents_to_schedule:
                    step_actions[oa] = LLMAction()
                else:
                    step_actions[oa] = ManualAction(
                        action_type=AT.DO_NOTHING, action_args={},
                    )
            llm_scheduled_indices = set(agents_to_schedule)

            # Branch B: inject candidate-specific intervention at intervention tick
            if intervention_tick is not None and tick == intervention_tick:
                official_agent, official_idx = self._find_official_agent(all_agents, agents)

                # Dispatch intervention message based on intervention_type
                itype = (intervention or {}).get("intervention_type", "official_response")
                custom_message = (intervention or {}).get("message", "")
                if custom_message:
                    intervention_content = custom_message
                else:
                    intervention_content = _INTERVENTION_MESSAGE_TEMPLATES.get(
                        itype, _build_intervention_message(scenario_type, evidence_refs)
                    )

                step_actions[official_agent] = ManualAction(
                    action_type=AT.CREATE_POST,
                    action_args={"content": intervention_content},
                )
                self._record_tick_action(
                    branch_id, tick,
                    agents[official_idx].agent_id if official_idx < len(agents) else "unknown",
                    f"intervention_{itype}", "broadcast",
                    is_intervention_action=True,
                )
                # Intervention target should be in scheduled set
                agents_to_schedule.add(official_idx)
                # This actor was overridden by a manual intervention action,
                # so it must not be counted as an attempted LLM decision.
                llm_scheduled_indices.discard(official_idx)

            # Record pre-step row IDs
            pre_post_max = self._get_max_row_id(db_path, "post")
            pre_trace_max = self._get_max_row_id(db_path, "trace")

            # Execute step
            await env.step(step_actions)

            # Record post-step row IDs
            post_post_max = self._get_max_row_id(db_path, "post")
            post_trace_max = self._get_max_row_id(db_path, "trace")

            # --- Read ONLY new rows added this tick ---
            self._capture_tick_rows(
                db_path, branch_id, tick, agents,
                pre_post_max, post_post_max,
                pre_trace_max, post_trace_max,
            )
            self._record_llm_outcomes(
                branch_id,
                llm_scheduled_indices,
                (self._tick_actions_a if branch_id == "A" else self._tick_actions_b).get(tick, []),
            )

            # --- Track this tick's spreaders for next tick's scheduling ---
            tick_actions = self._tick_actions_a if branch_id == "A" else self._tick_actions_b
            spreader_indices: Set[int] = set()
            for rec in tick_actions.get(tick, []):
                uid = rec.get("user_id")
                if uid is not None and uid < n_agents:
                    action_name = rec.get("action_name", "")
                    if action_name in ("create_post", "repost"):
                        spreader_indices.add(uid)
            prev_spreaders = spreader_indices

            # --- Record scheduling stats ---
            stats = self._scheduling_stats_a if branch_id == "A" else self._scheduling_stats_b
            stats[f"tick_{tick}"] = {
                "total_possible": n_agents,
                "actual_llm_actions": len(agents_to_schedule),
                "skipped": n_agents - len(agents_to_schedule),
            }
            for reason in ("source_or_official", "new_information", "previously_active",
                           "key_node", "intervention_target"):
                count = sum(1 for r in schedule_reasons.values() if r == reason)
                if count > 0:
                    stats.setdefault(f"scheduled_by_{reason}", 0)
                    stats[f"scheduled_by_{reason}"] += count

        await env.close()

        # Build trace
        trace = self._build_trace_from_tick_actions(
            agents, n_ticks, scenario_type, branch_id, db_path,
        )

        # Save metadata
        run_id = str(uuid.uuid4())[:8]
        tick_actions = self._tick_actions_a if branch_id == "A" else self._tick_actions_b
        _save_trace_metadata(
            run_id, branch_id, self._init_status.to_dict(),
            tick_actions, trace.final_metrics,
        )

        return trace

    # ==================================================================
    # Per-tick DB row capture — bind actions to exact ticks
    # ==================================================================

    def _get_max_row_id(self, db_path: str, table: str) -> int:
        """Get the maximum rowid for a table, or 0 if table is empty."""
        try:
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute(f"SELECT MAX(rowid) FROM {table}")
            row = cur.fetchone()
            conn.close()
            return row[0] if row and row[0] is not None else 0
        except Exception as exc:
            self._record_action_failure("A", exc)
            return 0

    def _capture_tick_rows(
        self, db_path: str, branch_id: str, tick: int,
        agents: List[PropagationAgent],
        pre_post_max: int, post_post_max: int,
        pre_trace_max: int, post_trace_max: int,
    ) -> None:
        """Read ONLY the rows added during this tick and bind them to the tick."""
        records = self._tick_actions_a if branch_id == "A" else self._tick_actions_b
        records.setdefault(tick, [])
        intervention_actor_ids = {
            rec.get("canonical_actor_id")
            for rec in records.get(tick, [])
            if rec.get("is_intervention_action")
        }

        n_agents = len(agents)

        # Read new trace rows
        if post_trace_max > pre_trace_max:
            try:
                conn = sqlite3.connect(db_path)
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                cur.execute(
                    "SELECT rowid, user_id, action, info FROM trace "
                    "WHERE rowid > ? AND rowid <= ? ORDER BY rowid",
                    (pre_trace_max, post_trace_max),
                )
                for row in cur.fetchall():
                    uid = int(row["user_id"])
                    action_name = str(row["action"]).lower()
                    records[tick].append({
                        "user_id": uid,
                        "action_name": action_name,
                        "info": str(row["info"])[:80],
                        "canonical_actor_id": agents[uid].agent_id if uid < n_agents else f"agent_{uid:04d}",
                        "rowid": row["rowid"],
                        "table": "trace",
                        "is_intervention_action": (
                            agents[uid].agent_id if uid < n_agents else f"agent_{uid:04d}"
                        ) in intervention_actor_ids,
                    })
                conn.close()
            except Exception as exc:
                self._record_action_failure(branch_id, exc)

        # Read new post rows
        if post_post_max > pre_post_max:
            try:
                conn = sqlite3.connect(db_path)
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                cur.execute(
                    "SELECT rowid, post_id, user_id, content FROM post "
                    "WHERE rowid > ? AND rowid <= ? ORDER BY rowid",
                    (pre_post_max, post_post_max),
                )
                for row in cur.fetchall():
                    uid = int(row["user_id"])
                    records[tick].append({
                        "user_id": uid,
                        "action_name": "create_post",
                        "info": str(row["content"])[:80],
                        "canonical_actor_id": agents[uid].agent_id if uid < n_agents else f"agent_{uid:04d}",
                        "post_id": row["post_id"],
                        "table": "post",
                        "is_intervention_action": (
                            agents[uid].agent_id if uid < n_agents else f"agent_{uid:04d}"
                        ) in intervention_actor_ids,
                    })
                conn.close()
            except Exception as exc:
                self._record_action_failure(branch_id, exc)

    def _record_tick_action(
        self, branch_id: str, tick: int, actor_id: str,
        action_type: str, target_id: str,
        is_intervention_action: bool = False,
    ) -> None:
        """Record a manually triggered action at a specific tick."""
        records = self._tick_actions_a if branch_id == "A" else self._tick_actions_b
        records.setdefault(tick, [])
        records[tick].append({
            "canonical_actor_id": actor_id,
            "action_type": action_type,
            "target_id": target_id,
            "manual": True,
            "is_intervention_action": is_intervention_action,
            "timestamp": time.time(),
        })
        diagnostics = self._action_diagnostics_a if branch_id == "A" else self._action_diagnostics_b
        diagnostics["action_attempted"] += 1
        diagnostics["action_success"] += 1
        if target_id and target_id != "broadcast":
            diagnostics["affected_node_count"] += 1

    @staticmethod
    def _new_action_diagnostics() -> Dict[str, Any]:
        return {
            "action_attempted": 0,
            "action_success": 0,
            "action_failed": 0,
            "affected_node_count": 0,
            "exception_type": None,
            "llm_action_attempted": 0,
            "llm_action_success": 0,
            "llm_action_failed": 0,
        }

    def _record_llm_outcomes(
        self,
        branch_id: str,
        scheduled_indices: Set[int],
        tick_records: List[Dict[str, Any]],
    ) -> None:
        """Reconcile scheduled LLM decisions with rows OASIS actually wrote.

        OASIS logs provider exceptions internally and lets ``env.step``
        return.  Without this reconciliation an all-403 run was reported as
        a completed native simulation.
        """
        diagnostics = self._action_diagnostics_a if branch_id == "A" else self._action_diagnostics_b
        attempted = len(scheduled_indices)
        observed = {
            int(record["user_id"])
            for record in tick_records
            if record.get("table") == "trace"
            and record.get("user_id") is not None
            and int(record["user_id"]) in scheduled_indices
        }
        succeeded = len(observed)
        diagnostics["llm_action_attempted"] += attempted
        diagnostics["llm_action_success"] += succeeded
        diagnostics["llm_action_failed"] += max(0, attempted - succeeded)
        if attempted > succeeded:
            diagnostics["exception_type"] = "MissingOasisActionResult"

    def _ensure_branch_has_llm_outcomes(self, branch_id: str) -> None:
        diagnostics = self._action_diagnostics_a if branch_id == "A" else self._action_diagnostics_b
        attempted = int(diagnostics.get("llm_action_attempted", 0))
        succeeded = int(diagnostics.get("llm_action_success", 0))
        if attempted > 0 and succeeded == 0:
            raise RuntimeError(
                f"oasis_all_llm_actions_failed: branch={branch_id}, attempted={attempted}"
            )

    def _record_action_failure(self, branch_id: str, exc: Exception) -> None:
        diagnostics = self._action_diagnostics_a if branch_id == "A" else self._action_diagnostics_b
        diagnostics["action_failed"] += 1
        diagnostics["exception_type"] = exc.__class__.__name__

    # ==================================================================
    # Build trace from tick-bound actions
    # ==================================================================

    def _build_trace_from_tick_actions(
        self, agents: List[PropagationAgent], n_ticks: int,
        scenario_type: str, branch_id: str, db_path: str,
    ) -> PropagationTrace:
        """Build PropagationTrace from per-tick action records (no post-hoc bucketing)."""
        tick_records = self._tick_actions_a if branch_id == "A" else self._tick_actions_b

        # Count posts from DB
        total_posts = 0
        try:
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM post")
            row = cur.fetchone()
            total_posts = row[0] if row else 0
            conn.close()
        except Exception as exc:
            self._record_action_failure(branch_id, exc)

        actions: List[PropagationAction] = []
        cumulative_spreaders: Set[str] = set()
        coverage_curve: List[Dict] = []
        emotion_curve: List[Dict] = []

        action_type_map = {
            "create_post": "spread", "repost": "spread",
            "like_post": "engage", "do_nothing": "idle",
        }
        n_agents = max(1, len(agents))

        for tick in range(n_ticks):
            tick_rows = tick_records.get(tick, [])
            tick_spreaders: Set[str] = set()
            tick_action_count = len(tick_rows)

            for rec in tick_rows:
                canonical_id = rec.get("canonical_actor_id", "unknown")
                action_name = rec.get("action_name", rec.get("action_type", "act"))
                mapped = action_type_map.get(action_name, "act")

                if mapped == "spread" and not rec.get("is_intervention_action", False):
                    tick_spreaders.add(canonical_id)
                    cumulative_spreaders.add(canonical_id)

                actions.append(PropagationAction(
                    tick=tick,
                    source_agent_id=canonical_id,
                    target_agent_id=rec.get("target_id", "broadcast"),
                    action_type=mapped,
                    content_summary=rec.get("info", rec.get("action_type", ""))[:80],
                    influence_delta=0.0,
                    risk_delta=0.0,
                ))

            coverage_curve.append({
                "tick": tick,
                "cumulative_coverage": round(len(cumulative_spreaders) / n_agents, 3),
                "organic_propagation_coverage": round(len(cumulative_spreaders) / n_agents, 3),
                "new_spreaders": len(tick_spreaders),
                "total_actions_this_tick": tick_action_count,
            })
            emotion_curve.append({
                "tick": tick,
                "spread_actions_this_tick": len(tick_spreaders),
                "total_actions_this_tick": tick_action_count,
            })

        # Key nodes using real adjacency
        adj = self._build_adjacency_from_agents(agents)
        key_nodes = self._compute_key_nodes(agents, adj, actions)

        # Metrics
        total_actions = len(actions)
        spread_count = sum(1 for a in actions if a.action_type == "spread")
        unique_spreaders = len(cumulative_spreaders)

        final_metrics = {
            "cumulative_coverage": round(len(cumulative_spreaders) / n_agents, 3),
            "organic_propagation_coverage": round(len(cumulative_spreaders) / n_agents, 3),
            "spread_actions": spread_count,
            "engage_actions": sum(1 for a in actions if a.action_type == "engage"),
            "idle_actions": sum(1 for a in actions if a.action_type == "idle"),
            "total_actions": total_actions,
            "unique_spreaders": unique_spreaders,
            "unique_spreader_ratio": round(unique_spreaders / n_agents, 3),
            "total_posts": total_posts,
            "key_node_count": len(key_nodes),
            "oasis_driven": True,
            "metric_source": "native",
            "metric_semantics": {
                "primary_metric": "organic_propagation_coverage",
                "direction": "lower_is_better",
                "system_intervention_action_excluded": True,
                "content_semantics_classified": False,
                "interpretation": "propagation_activity_proxy",
            },
        }

        return PropagationTrace(
            trace_id=str(uuid.uuid4()),
            scenario_type=scenario_type, ticks=n_ticks,
            agents=agents, actions=actions,
            coverage_curve=coverage_curve, emotion_curve=emotion_curve,
            key_nodes=key_nodes, final_metrics=final_metrics,
        )

    # ==================================================================
    # Helpers
    # ==================================================================

    def _compute_key_nodes(self, agents, adjacency, actions, top_k=5):
        n = max(1, len(agents))
        raw_max_deg = max((len(adjacency.get(a.agent_id, [])) for a in agents), default=0)
        max_deg = max(raw_max_deg, 1)
        action_counts: Dict[str, int] = {}
        for act in actions:
            if act.action_type == "spread":
                action_counts[act.source_agent_id] = action_counts.get(act.source_agent_id, 0) + 1
        max_actions = max(action_counts.values(), default=1)
        scores = []
        for a in agents:
            deg = len(adjacency.get(a.agent_id, []))
            cnt = action_counts.get(a.agent_id, 0)
            score = 0.45 * (deg / max_deg) + 0.35 * (cnt / max_actions) + 0.20 * a.influence
            scores.append({
                "agent_id": a.agent_id, "role": a.role,
                "score": round(score, 3), "out_degree": deg,
                "action_count": cnt, "influence": a.influence,
            })
        scores.sort(key=lambda x: x["score"], reverse=True)
        seen_roles = set()
        deduped = [s for s in scores if s["role"] not in seen_roles and not seen_roles.add(s["role"])]
        return deduped[:top_k]

    def _build_adjacency_from_agents(self, agents) -> Dict[str, List[str]]:
        adj: Dict[str, List[str]] = {a.agent_id: [] for a in agents}
        role_groups: Dict[str, List[str]] = {}
        for a in agents:
            role_groups.setdefault(a.role, []).append(a.agent_id)
        for group in role_groups.values():
            for i, aid in enumerate(group):
                for offset in range(1, min(4, len(group))):
                    nb = group[(i + offset) % len(group)]
                    if nb != aid and nb not in adj[aid]:
                        adj[aid].append(nb)
        return adj

    def _find_official_agent(self, oasis_agents, prop_agents) -> Tuple[Any, int]:
        if not oasis_agents:
            raise RuntimeError("OASIS agent graph is empty after profile generation")
        official_roles = {"official_responder", "school_official", "police_or_bank", "fact_checker"}
        for i, pa in enumerate(prop_agents):
            if pa.role in official_roles and i < len(oasis_agents):
                return oasis_agents[i], i
        return oasis_agents[-1], len(prop_agents) - 1

    @staticmethod
    def _validate_agent_alignment(oasis_agents, canonical_agents) -> None:
        if not oasis_agents:
            raise RuntimeError("OASIS agent graph is empty after profile generation")
        if len(oasis_agents) != len(canonical_agents):
            raise RuntimeError(
                "OASIS/canonical actor alignment failed: "
                f"oasis_agents={len(oasis_agents)} canonical_agents={len(canonical_agents)}"
            )

    def _compare_traces(self, a, b) -> Dict[str, Any]:
        cov_a = a.final_metrics.get("cumulative_coverage", 0.0)
        cov_b = b.final_metrics.get("cumulative_coverage", 0.0)
        return {
            "cumulative_coverage_a": round(cov_a, 3),
            "cumulative_coverage_b": round(cov_b, 3),
            "coverage_reduction": round(max(0.0, cov_a - cov_b), 3),
            "intervention_effectiveness": round(max(0.0, (cov_a - cov_b) / max(cov_a, 0.01)), 3),
            "spread_actions_a": a.final_metrics.get("spread_actions", 0),
            "spread_actions_b": b.final_metrics.get("spread_actions", 0),
            "posts_a": a.final_metrics.get("total_posts", 0),
            "posts_b": b.final_metrics.get("total_posts", 0),
            "trajectory_gap": round(abs(cov_a - cov_b), 3),
        }

    def _write_agent_csv(self, agents, csv_path):
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["user_char", "username", "description"])
            writer.writeheader()
            for agent in agents:
                writer.writerow({
                    "user_char": _ROLE_CHARS.get(
                        agent.role, f"你是一名{agent.role}，正在社交平台上浏览内容。")
                    + "\n" + actor_state_persona_summary(agent),
                    "username": agent.agent_id,  # canonical actor_id
                    "description": (
                        f"role={agent.role} influence={agent.influence:.2f} "
                        f"susceptibility={agent.susceptibility:.2f} stance={agent.stance} "
                        f"community={agent.community_id or agent.metadata.get('community_id', '')}"
                    ),
                })

    @staticmethod
    def _build_model(api_key, base_url, model_name, seed=42):
        # Round 3: OASIS uses only project-specific settings — no fallback.
        _api_key = api_key or os.environ.get("MIRO_COGSEC_OASIS_API_KEY", "")
        _base_url = base_url or os.environ.get("MIRO_COGSEC_OASIS_BASE_URL")
        _model_name = model_name or os.environ.get("MIRO_COGSEC_OASIS_MODEL")
        if not all((_api_key, _base_url, _model_name)):
            raise RuntimeError(
                "OASIS requires MIRO_COGSEC_OASIS_API_KEY, "
                "MIRO_COGSEC_OASIS_BASE_URL, and MIRO_COGSEC_OASIS_MODEL."
            )
        return OpenAICompatibleModel(
            model_type=_model_name, api_key=_api_key, url=_base_url,
            model_config_dict={"temperature": 0.7, "seed": seed},
        )

    def _prepare_paths(self):
        tmpdir = tempfile.mkdtemp(prefix="oasis_")
        return (os.path.join(tmpdir, "agents.csv"),
                os.path.join(tmpdir, "branch_a.db"),
                os.path.join(tmpdir, "branch_b.db"),
                tmpdir)

    def _read_observed_oasis_edges(
        self, db_path: str, agents: list, branch_id: str
    ) -> List[Dict[str, Any]]:
        """Read observed follow edges from OASIS SQLite DB.

        Maps ``user_id`` → OASIS agent index → canonical ``actor_id`` using
        the positional correspondence between the agent list and OASIS
        CSV rows (OASIS assigns social_agent_id = row index).

        Returns list of edge dicts with canonical actor_ids.
        """
        edges: List[Dict[str, Any]] = []
        if not os.path.exists(db_path):
            return edges

        try:
            import sqlite3
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()

            # Check if follow table exists
            cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='follow'"
            )
            if not cur.fetchone():
                conn.close()
                return edges

            # Read follow edges: (follower_id, followee_id) are user_ids
            cur.execute("SELECT follower_id, followee_id FROM follow")
            rows = cur.fetchall()

            # Build user_id → canonical actor_id mapping
            # OASIS user_id = OASIS agent index = positional CSV row index
            # = list index in self.agents (the canonical list)
            for follower_uid, followee_uid in rows:
                src_idx = int(follower_uid)
                tgt_idx = int(followee_uid)
                if 0 <= src_idx < len(agents) and 0 <= tgt_idx < len(agents):
                    src_agent = agents[src_idx]
                    tgt_agent = agents[tgt_idx]
                    edges.append({
                        "source_actor_id": getattr(src_agent, "agent_id", f"agent_{src_idx:04d}"),
                        "target_actor_id": getattr(tgt_agent, "agent_id", f"agent_{tgt_idx:04d}"),
                        "relation_type": "follow",
                        "weight": 1.0,
                        "provenance": "observed_oasis",
                        "branch": branch_id,
                    })

            conn.close()
        except Exception as exc:
            self._record_action_failure(branch_id, exc)

        return edges

    def _cleanup(self, tmpdir, db_a, db_b):
        if _OASIS_TRACE_RETENTION == "sanitized_full":
            os.makedirs(_TRACE_DIR, exist_ok=True)
            run_ts = int(time.time())
            for label, db_path in [("A", db_a), ("B", db_b)]:
                if os.path.exists(db_path):
                    dest = os.path.join(_TRACE_DIR, f"run_{run_ts}_branch_{label}.db")
                    try:
                        shutil.copy2(db_path, dest)
                    except OSError:
                        pass
        try:
            shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception:
            pass
