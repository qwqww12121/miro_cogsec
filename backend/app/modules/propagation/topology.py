"""Topology builder — deterministic adjacency lists WITHOUT networkx."""

from __future__ import annotations

import random as _random
from typing import Dict, List, Optional

from .schema import PropagationAgent


def build_topology(
    agents: list[PropagationAgent],
    topology_type: str = "small_world",
    seed: int = 42,
) -> dict[str, list[str]]:
    """Build an adjacency dict for *agents* using *topology_type*.

    Returns ``{agent_id: [neighbour_id, ...]}``.  Every agent appears as a key.
    No self-loops.  Neighbours are deduplicated.
    """
    if topology_type == "small_world":
        return _small_world(agents, seed)
    if topology_type == "scale_free_like":
        return _scale_free_like(agents, seed)
    if topology_type == "campus_local":
        return _campus_local(agents, seed)
    return _small_world(agents, seed)


def _ensure_all_keys(agents: list[PropagationAgent], adj: dict[str, list[str]]) -> dict[str, list[str]]:
    for a in agents:
        adj.setdefault(a.agent_id, [])
    return adj


# ---------------------------------------------------------------------------
# small_world
# ---------------------------------------------------------------------------


def _small_world(agents: list[PropagationAgent], seed: int) -> dict[str, list[str]]:
    rng = _random.Random(seed)
    n = len(agents)
    ids = [a.agent_id for a in agents]
    adj: dict[str, list[str]] = {a.agent_id: [] for a in agents}

    left_neighbours = 2
    for i in range(n):
        for offset in range(1, left_neighbours + 1):
            adj[ids[i]].append(ids[(i + offset) % n])
            adj[ids[(i + offset) % n]].append(ids[i])

    # long-range rewiring
    extra_edges = max(1, n // 5)
    for _ in range(extra_edges):
        u = rng.choice(ids)
        v = rng.choice(ids)
        if u != v and v not in adj[u]:
            adj[u].append(v)

    return _dedup(_ensure_all_keys(agents, adj))


# ---------------------------------------------------------------------------
# scale_free_like
# ---------------------------------------------------------------------------


def _scale_free_like(agents: list[PropagationAgent], seed: int) -> dict[str, list[str]]:
    rng = _random.Random(seed)
    n = len(agents)
    ids = [a.agent_id for a in agents]
    id_to_agent = {a.agent_id: a for a in agents}
    adj: dict[str, list[str]] = {aid: [] for aid in ids}

    hub_count = max(1, n // 5)
    sorted_by_influence = sorted(agents, key=lambda a: a.influence, reverse=True)
    hubs = {a.agent_id for a in sorted_by_influence[:hub_count]}

    for agent in agents:
        degree = rng.randint(1, max(2, n // 8))
        for _ in range(degree):
            if rng.random() < 0.75 and hubs:
                target_id = rng.choice(list(hubs))
            else:
                target_id = rng.choice(ids)
            if target_id != agent.agent_id and target_id not in adj[agent.agent_id]:
                adj[agent.agent_id].append(target_id)

    return _dedup(_ensure_all_keys(agents, adj))


# ---------------------------------------------------------------------------
# campus_local
# ---------------------------------------------------------------------------


def _campus_local(agents: list[PropagationAgent], seed: int) -> dict[str, list[str]]:
    rng = _random.Random(seed)
    adj: dict[str, list[str]] = {a.agent_id: [] for a in agents}

    groups: dict[str, list[str]] = {}
    for a in agents:
        groups.setdefault(a.role, []).append(a.agent_id)

    group_list = list(groups.values())
    ids = [a.agent_id for a in agents]

    for g in group_list:
        # dense intra-group
        for i, aid in enumerate(g):
            for offset in range(1, min(4, len(g))):
                neighbour = g[(i + offset) % len(g)]
                if neighbour != aid:
                    adj[aid].append(neighbour)

    # sparse inter-group
    inter_edges = len(agents) // 4
    for _ in range(inter_edges):
        u = rng.choice(ids)
        v = rng.choice(ids)
        if u != v and v not in adj[u]:
            adj[u].append(v)

    return _dedup(_ensure_all_keys(agents, adj))


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _dedup(adj: dict[str, list[str]]) -> dict[str, list[str]]:
    return {k: list(set(v)) for k, v in adj.items()}
