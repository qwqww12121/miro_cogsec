"""Fork strategies — Branch-A (no intervention) and Branch-B (intervention)."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Protocol

from ..social_state.behavior import update_institutional_trust
from .schema import PropagationAgent


class PropagationForkStrategy(Protocol):
    name: str

    def should_apply(self, tick: int) -> bool:
        ...

    def apply(
        self,
        agents: list[PropagationAgent],
        adjacency: dict[str, list[str]],
        key_nodes: list[dict],
    ) -> tuple[list[PropagationAgent], dict[str, list[str]], dict]:
        ...


# ---------------------------------------------------------------------------
# NoInterventionFork
# ---------------------------------------------------------------------------


class NoInterventionFork:
    name = "no_intervention"

    def should_apply(self, tick: int) -> bool:
        return False

    def apply(
        self,
        agents: list[PropagationAgent],
        adjacency: dict[str, list[str]],
        key_nodes: list[dict],
    ) -> tuple[list[PropagationAgent], dict[str, list[str]], dict]:
        return deepcopy(agents), deepcopy(adjacency), {}


# ---------------------------------------------------------------------------
# RemoveKeyNodeFork
# ---------------------------------------------------------------------------


class RemoveKeyNodeFork:
    name = "remove_key_node"

    def __init__(self, application_tick: int = 10):
        self.application_tick = application_tick

    def should_apply(self, tick: int) -> bool:
        return tick == self.application_tick

    def apply(
        self,
        agents: list[PropagationAgent],
        adjacency: dict[str, list[str]],
        key_nodes: list[dict],
    ) -> tuple[list[PropagationAgent], dict[str, list[str]], dict]:
        new_adj = deepcopy(adjacency)
        if not key_nodes:
            return deepcopy(agents), new_adj, {"removed_agent_id": None}

        target_id = key_nodes[0]["agent_id"]
        # remove all outgoing edges from target
        new_adj[target_id] = []
        # remove target from all other agents' neighbour lists
        for aid in new_adj:
            new_adj[aid] = [n for n in new_adj[aid] if n != target_id]

        return deepcopy(agents), new_adj, {"removed_agent_id": target_id}


# ---------------------------------------------------------------------------
# OfficialClarificationFork
# ---------------------------------------------------------------------------


_OFFICIAL_ROLES = {"school_official", "official_responder", "police_or_bank"}
_AMPLIFIER_ROLES = {"anonymous_amplifier", "controversy_amplifier"}


class OfficialClarificationFork:
    name = "official_clarification"

    def __init__(self, application_tick: int = 10):
        self.application_tick = application_tick

    def should_apply(self, tick: int) -> bool:
        return tick == self.application_tick

    def apply(
        self,
        agents: list[PropagationAgent],
        adjacency: dict[str, list[str]],
        key_nodes: list[dict],
    ) -> tuple[list[PropagationAgent], dict[str, list[str]], dict]:
        new_agents = deepcopy(agents)
        affected = 0

        for agent in new_agents:
            update_institutional_trust(
                agent,
                tick=self.application_tick,
                verified=True,
                source_role="official_responder",
                # This is only the minimum supported official-clarification
                # trigger; Phase 2 can add evidence quality/transparency.
                information_signal=0.25,
            )
            if agent.role in _OFFICIAL_ROLES:
                agent.activity = min(1.0, agent.activity + 0.25)
                affected += 1
            elif agent.role in _AMPLIFIER_ROLES:
                agent.influence = max(0.01, agent.influence - 0.30)
                affected += 1

        return new_agents, deepcopy(adjacency), {"affected_agents": affected}
