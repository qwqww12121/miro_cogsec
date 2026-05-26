"""OASIS propagation adapter — real multi-agent social simulation."""

from __future__ import annotations

import asyncio
import csv
import os
import sqlite3
import tempfile
import time
import uuid
from typing import Any, Dict, List, Optional

from .schema import (
    ForkedPropagationResult,
    PropagationAction,
    PropagationAgent,
    PropagationEvent,
    PropagationTrace,
)
from .metrics import compute_key_nodes, summarize_trace

try:
    from camel.models import OpenAICompatibleModel
    from camel.types import ModelType
    from oasis import generate_twitter_agent_graph, DefaultPlatformType
    from oasis.environment.env import OasisEnv
    from oasis.environment.env_action import LLMAction, ManualAction
    from oasis.social_platform.typing import ActionType
    _OASIS_AVAILABLE = True
except ImportError:
    _OASIS_AVAILABLE = False


# 角色中文人设 → OASIS user_char
_ROLE_CHARS: Dict[str, str] = {
    "student_kol": "你是一名在校大学生，关注热点话题，粉丝较多，喜欢转发和评论社会新闻，对官方说法持保留态度。",
    "ordinary_student": "你是一名普通学生，偶尔刷社交媒体，看到感兴趣的内容会点赞，有时会转发给朋友。",
    "teacher": "你是一名高校教师，重视信息准确性，会核实信息来源，不轻易传播未经证实的消息。",
    "school_official": "你是学校官方账号，负责发布权威信息，会及时辟谣和澄清不实消息。",
    "media_observer": "你是一名媒体观察员，关注舆情动态，会分析信息传播路径，有时会撰写评论文章。",
    "anonymous_amplifier": "你是一个匿名账号，喜欢传播耸人听闻的消息，不在乎信息真假，以引发讨论为乐。",
    "original_poster": "你是这条信息的首发者，你认为这个消息很重要，希望更多人知道。",
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

_INTERVENTION_CONTENT = {
    "public_opinion": "【官方辟谣】网络流传的相关信息经核实存在严重失实，请广大网友不信谣、不传谣。如有疑问请拨打官方热线核实。",
    "event_propagation": "【权威发布】关于近期网络流传信息，经相关部门核查，部分内容存在夸大和失实。以官方渠道发布信息为准，请理性看待。",
}


class OasisPropagationAdapter:
    """使用 OASIS 框架运行真实多 Agent 社交传播仿真。"""

    def is_available(self) -> bool:
        return _OASIS_AVAILABLE

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
    ) -> ForkedPropagationResult:
        """运行 Fork A/B 仿真，返回 ForkedPropagationResult。"""
        if not _OASIS_AVAILABLE:
            raise RuntimeError("camel-oasis 未安装，无法运行 OASIS 仿真。")

        return asyncio.run(
            self._run_forked(
                event=event,
                agents=agents,
                scenario_type=scenario_type,
                n_ticks=n_ticks,
                intervention_tick=intervention_tick,
                llm_api_key=llm_api_key,
                llm_base_url=llm_base_url,
                llm_model_name=llm_model_name,
            )
        )

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
    ) -> ForkedPropagationResult:
        model = self._build_model(llm_api_key, llm_base_url, llm_model_name)

        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = os.path.join(tmpdir, "agents.csv")
            self._write_agent_csv(agents, csv_path)

            db_a = os.path.join(tmpdir, "branch_a.db")
            db_b = os.path.join(tmpdir, "branch_b.db")

            trace_a = await self._run_branch(
                csv_path=csv_path,
                db_path=db_a,
                model=model,
                event=event,
                agents=agents,
                n_ticks=n_ticks,
                intervention_tick=None,
                scenario_type=scenario_type,
            )
            trace_b = await self._run_branch(
                csv_path=csv_path,
                db_path=db_b,
                model=model,
                event=event,
                agents=agents,
                n_ticks=n_ticks,
                intervention_tick=intervention_tick,
                scenario_type=scenario_type,
            )

        fork_point = {
            "tick": intervention_tick,
            "type": "official_clarification",
            "description": "官方辟谣注入",
        }
        comparison = self._compare_traces(trace_a, trace_b)
        return ForkedPropagationResult(
            fork_point=fork_point,
            branch_a=trace_a,
            branch_b=trace_b,
            comparison=comparison,
        )

    async def _run_branch(
        self,
        csv_path: str,
        db_path: str,
        model: Any,
        event: PropagationEvent,
        agents: List[PropagationAgent],
        n_ticks: int,
        intervention_tick: Optional[int],
        scenario_type: str,
    ) -> PropagationTrace:
        from oasis.social_platform.typing import ActionType as AT

        available = [
            AT.CREATE_POST, AT.REPOST, AT.LIKE_POST, AT.DO_NOTHING,
        ]
        agent_graph = await generate_twitter_agent_graph(
            profile_path=csv_path,
            model=model,
            available_actions=available,
        )

        env = OasisEnv(
            agent_graph=agent_graph,
            platform=DefaultPlatformType.TWITTER,
            database_path=db_path,
        )
        await env.reset()

        all_agents = list(agent_graph.get_agents())

        # 种子帖：第0个 Agent 发布初始信息
        seed_actions: Dict[Any, Any] = {
            all_agents[0]: ManualAction(
                action_type=AT.CREATE_POST,
                action_args={"content": event.seed_text},
            )
        }
        await env.step(seed_actions)

        # 主仿真循环
        for tick in range(n_ticks):
            step_actions: Dict[Any, Any] = {a: LLMAction() for a in all_agents}

            # Branch B：在干预时刻注入官方辟谣
            if intervention_tick is not None and tick == intervention_tick:
                official = self._find_official_agent(all_agents, agents)
                clarification = _INTERVENTION_CONTENT.get(
                    scenario_type, _INTERVENTION_CONTENT["public_opinion"]
                )
                step_actions[official] = ManualAction(
                    action_type=AT.CREATE_POST,
                    action_args={"content": clarification},
                )

            await env.step(step_actions)

        await env.close()

        return self._db_to_trace(db_path, agents, n_ticks, scenario_type)

    def _find_official_agent(self, oasis_agents: list, prop_agents: List[PropagationAgent]) -> Any:
        """找到 official_responder 或 school_official 角色的 Agent。"""
        official_roles = {"official_responder", "school_official", "police_or_bank"}
        for i, pa in enumerate(prop_agents):
            if pa.role in official_roles and i < len(oasis_agents):
                return oasis_agents[i]
        return oasis_agents[-1]

    def _db_to_trace(
        self,
        db_path: str,
        agents: List[PropagationAgent],
        n_ticks: int,
        scenario_type: str,
    ) -> PropagationTrace:
        """从 SQLite 读取仿真结果，转换为 PropagationTrace。"""
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # 读取 trace 表
        cur.execute("SELECT user_id, created_at, action, info FROM trace ORDER BY created_at")
        trace_rows = cur.fetchall()

        # 读取 post 表
        cur.execute("SELECT post_id, user_id, content, num_likes, num_shares, created_at FROM post ORDER BY created_at")
        post_rows = cur.fetchall()

        conn.close()

        # 统计传播覆盖
        covered_users: set = set()
        actions: List[PropagationAction] = []
        coverage_curve: List[Dict] = []
        emotion_curve: List[Dict] = []

        action_type_map = {
            "create_post": "spread",
            "repost": "spread",
            "like_post": "engage",
            "sign_up": "join",
            "do_nothing": "idle",
        }

        tick_buckets: Dict[int, list] = {i: [] for i in range(n_ticks + 1)}
        for row in trace_rows:
            action_name = str(row["action"]).lower()
            if action_name in ("sign_up", "signup"):
                continue
            t = min(int(row["created_at"]) if str(row["created_at"]).isdigit() else 0, n_ticks)
            tick_buckets[t].append(row)

        for tick, rows in tick_buckets.items():
            for row in rows:
                uid = int(row["user_id"])
                covered_users.add(uid)
                pa = agents[uid] if uid < len(agents) else None
                actions.append(PropagationAction(
                    tick=tick,
                    source_agent_id=str(uid),
                    target_agent_id="broadcast",
                    action_type=action_type_map.get(str(row["action"]).lower(), "act"),
                    content_summary=str(row["info"])[:80],
                    influence_delta=pa.influence * 0.1 if pa else 0.05,
                    risk_delta=0.05,
                ))
            coverage_curve.append({
                "tick": tick,
                "coverage": len(covered_users) / max(1, len(agents)),
                "new_spreads": len([r for r in rows if str(r["action"]).lower() in ("create_post", "repost")]),
            })
            emotion_curve.append({
                "tick": tick,
                "panic": min(1.0, 0.3 + tick * 0.08),
                "trust": max(0.0, 0.7 - tick * 0.05),
            })

        key_nodes = compute_key_nodes(agents, {}, actions)
        final_metrics = summarize_trace(PropagationTrace(
            trace_id=str(uuid.uuid4()),
            scenario_type=scenario_type,
            ticks=n_ticks,
            agents=agents,
            actions=actions,
            coverage_curve=coverage_curve,
            emotion_curve=emotion_curve,
            key_nodes=key_nodes,
            final_metrics={},
        ))
        final_metrics["total_posts"] = len(post_rows)
        final_metrics["total_actions"] = len(actions)
        final_metrics["oasis_driven"] = True

        return PropagationTrace(
            trace_id=str(uuid.uuid4()),
            scenario_type=scenario_type,
            ticks=n_ticks,
            agents=agents,
            actions=actions,
            coverage_curve=coverage_curve,
            emotion_curve=emotion_curve,
            key_nodes=key_nodes,
            final_metrics=final_metrics,
        )

    def _compare_traces(self, a: PropagationTrace, b: PropagationTrace) -> Dict[str, Any]:
        cov_a = a.coverage_curve[-1]["coverage"] if a.coverage_curve else 0
        cov_b = b.coverage_curve[-1]["coverage"] if b.coverage_curve else 0
        return {
            "coverage_a": round(cov_a, 3),
            "coverage_b": round(cov_b, 3),
            "coverage_reduction": round(cov_a - cov_b, 3),
            "intervention_effectiveness": round(max(0.0, (cov_a - cov_b) / max(cov_a, 0.01)), 3),
            "posts_a": a.final_metrics.get("total_posts", 0),
            "posts_b": b.final_metrics.get("total_posts", 0),
            "trajectory_gap": round(abs(cov_a - cov_b), 3),
        }

    def _write_agent_csv(self, agents: List[PropagationAgent], csv_path: str) -> None:
        """将 PropagationAgent 列表写成 OASIS 要求的 CSV 格式。"""
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["user_char", "username", "description"])
            writer.writeheader()
            for i, agent in enumerate(agents):
                writer.writerow({
                    "user_char": _ROLE_CHARS.get(agent.role, f"你是一名{agent.role}，正在社交平台上浏览内容。"),
                    "username": f"{agent.role}_{i}",
                    "description": f"影响力={agent.influence:.2f} 易感性={agent.susceptibility:.2f} 立场={agent.stance}",
                })

    @staticmethod
    def _build_model(
        api_key: Optional[str],
        base_url: Optional[str],
        model_name: Optional[str],
    ) -> Any:
        """构造 camel-ai OpenAI 兼容模型后端。"""
        from camel.models import OpenAICompatibleModel
        from camel.types import ModelType

        _api_key = api_key or os.environ.get("LLM_API_KEY", "")
        _base_url = base_url or os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1")
        _model_name = model_name or os.environ.get("LLM_MODEL_NAME", "gpt-4o-mini")

        return OpenAICompatibleModel(
            model_type=ModelType.GPT_4O_MINI,
            api_key=_api_key,
            url=_base_url,
            model_config_dict={"model": _model_name, "temperature": 0.7},
        )
