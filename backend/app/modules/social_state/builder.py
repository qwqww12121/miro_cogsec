"""SocialState builder — constructs unified social state from input text,
cognitive profile, RiskGraph, and scenario type.

Builds actors from:
1. Input text extraction (named entities, roles mentioned in the scenario)
2. Cognitive profile mapping
3. RiskGraph node references
4. Synthetic population for network completeness
"""

from __future__ import annotations

import re
from dataclasses import replace
import random
from typing import Any, Dict, List, Optional, Set

from .behavior import (
    apply_actor_cognitive_state,
    assign_communities,
    build_actor_cognitive_state,
    build_scene_cognitive_prior,
)

from .schema import (
    ActorCognitiveFeatures,
    ActorState,
    PROVENANCE_INPUT,
    PROVENANCE_INFERRED,
    PROVENANCE_SYNTHETIC,
    SocialEdge,
    SocialState,
)


# ---------------------------------------------------------------------------
# Role detection from input text
# ---------------------------------------------------------------------------

# Simple keyword-to-role mapping for Chinese social-media scenarios
_ROLE_PATTERNS: List[tuple] = [
    # (regex pattern, role, display_name_template)
    (r"(校方|学校|大学|学院|高校|教务处|校长)", "school_official", "校方"),
    (r"(学生|同学|大学生|在校生)", "ordinary_student", "学生"),
    (r"(老师|教师|教授|导师|辅导员)", "teacher", "教师"),
    (r"(官方|政府|警方|公安|警察|网信办|监管部门|权威部门)", "official_responder", "官方"),
    (r"(媒体|记者|新闻|报社|电视台|报道)", "media_observer", "媒体"),
    (r"(爆料|曝光|发帖人|首发|源头|知情人士)", "original_poster", "爆料者"),
    (r"(群主|管理员|吧主|版主|运营|审核)", "platform_moderator", "平台管理"),
    (r"(受害者|被骗|上当|受害人|事主)", "victim", "受害者"),
    (r"(诈骗|骗子|冒充|假装|假扮|欺诈)", "attacker", "诈骗者"),
    (r"(家长|家属|父亲|母亲|爸爸|妈妈|丈夫|妻子|老公|老婆)", "family_member", "家属"),
    (r"(品牌方|厂商|官方号|公司官方)", "official_responder", "品牌方"),
    (r"(消费者|买家|用户体验)", "ordinary_viewer", "消费者"),
    (r"(网民|网友|评论|用户|吃瓜群众|围观)", "ordinary_viewer", "网民"),
    (r"(银行|客服|金融机构|支付平台)", "police_or_bank", "金融机构"),
    (r"(辟谣|澄清|事实核查|求证|鉴定)", "fact_checker", "事实核查"),
    (r"(匿名|小号|水军|营销号|炒作)", "anonymous_amplifier", "匿名账号"),
]


def extract_actors_from_text(
    text: str,
    max_actors: int = 12,
    scenario_type: str = "",
) -> List[ActorState]:
    """Extract named/implied actors from scenario input text.

    Returns actors with provenance="input".
    Campus-only roles are skipped unless the text is a real school incident.
    """
    actors: List[ActorState] = []
    seen_roles: Set[str] = set()

    campus = uses_campus_cast(scenario_type, text)
    for pattern, role, display_name in _ROLE_PATTERNS:
        if len(actors) >= max_actors:
            break
        if role in seen_roles:
            continue
        if role in _CAMPUS_ONLY_ROLES and not campus:
            continue
        if re.search(pattern, text):
            seen_roles.add(role)
            idx = len(actors)
            actors.append(ActorState(
                actor_id=f"actor_{idx:04d}",
                role=role,
                display_name=display_name,
                provenance=PROVENANCE_INPUT,
                cognitive_features=ActorCognitiveFeatures(),
                source_refs=["input_text"],
            ))

    return actors


# ---------------------------------------------------------------------------
# Cognitive profile → actor features
# ---------------------------------------------------------------------------


def map_cognitive_to_actors(
    actors: List[ActorState],
    cognitive_profile: Any,
) -> List[ActorState]:
    """Apply cognitive profile features to actors.

    Input-identified actors receive the full profile mapping. Synthetic actors
    will be handled separately by the agent factory.
    """
    for actor in actors:
        if actor.provenance == PROVENANCE_INPUT:
            # Do not share one mutable feature object across actors.  The
            # profile is a scene prior; actor-specific conditioning happens in
            # ``_initialize_actor_states`` below.
            actor.cognitive_features = replace(
                ActorCognitiveFeatures.from_profile(cognitive_profile)
            )
    return actors


# ---------------------------------------------------------------------------
# Synthetic population
# ---------------------------------------------------------------------------

_CAMPUS_ONLY_ROLES = {"school_official", "ordinary_student", "teacher", "student_kol"}
_CAMPUS_ROLE_REMAP = {
    "student_kol": "repost_kol",
    "ordinary_student": "ordinary_viewer",
    "teacher": "ordinary_viewer",
    "school_official": "official_responder",
}

# Strong campus evidence only. Weak words like 同学/学校 alone are not enough.
_CAMPUS_STRONG = re.compile(
    r"校方|高校|大学校园|校园网|表白墙|辅导员|教务处|班级群|在校生|学生会|宿舍楼|奖学金|校园墙"
)
_CAMPUS_CONTEXT = re.compile(r"大学|学院|学校|校长|食堂|校园|同学|学生")
_SOCIAL_OVERRIDE = re.compile(
    r"品牌|网友|热搜|营销|微博|短视频|消费者|新品发布|明星|艺人|市民|社区|小区|物业|医院|患者|股市"
)

_ROLE_LABEL_ZH = {
    "student_kol": "学生意见领袖",
    "ordinary_student": "普通学生",
    "teacher": "老师",
    "school_official": "校方",
    "media_observer": "媒体观察者",
    "anonymous_amplifier": "匿名放大器",
    "original_poster": "首发者",
    "repost_kol": "转发意见领袖",
    "ordinary_viewer": "普通网民",
    "fact_checker": "事实核查",
    "official_responder": "官方回应",
    "controversy_amplifier": "争议放大器",
    "victim": "受害人",
    "attacker": "施害者",
    "family_member": "家人",
    "platform_moderator": "平台审核",
    "police_or_bank": "警方或银行",
}

_SYNTHETIC_ROLE_POOLS: Dict[str, List[str]] = {
    "public_opinion": [
        "original_poster", "repost_kol", "ordinary_viewer", "media_observer",
        "anonymous_amplifier", "controversy_amplifier", "fact_checker", "official_responder",
    ],
    "public_opinion_campus": [
        "student_kol", "ordinary_student", "teacher", "school_official",
        "media_observer", "anonymous_amplifier",
    ],
    "event_propagation": [
        "original_poster", "repost_kol", "ordinary_viewer", "fact_checker",
        "official_responder", "controversy_amplifier",
    ],
    "fraud_im": [
        "victim", "attacker", "family_member", "platform_moderator", "police_or_bank",
    ],
}

# Default attribute weights per role
_SYNTHETIC_WEIGHTS: Dict[str, Dict[str, float]] = {
    "student_kol": {"influence": 0.75, "susceptibility": 0.40, "activity": 0.65, "trust_in_official": 0.35},
    "ordinary_student": {"influence": 0.35, "susceptibility": 0.65, "activity": 0.50, "trust_in_official": 0.45},
    "teacher": {"influence": 0.60, "susceptibility": 0.40, "activity": 0.45, "trust_in_official": 0.55},
    "school_official": {"influence": 0.70, "susceptibility": 0.25, "activity": 0.50, "trust_in_official": 0.90},
    "media_observer": {"influence": 0.80, "susceptibility": 0.30, "activity": 0.60, "trust_in_official": 0.50},
    "anonymous_amplifier": {"influence": 0.45, "susceptibility": 0.70, "activity": 0.85, "trust_in_official": 0.15},
    "original_poster": {"influence": 0.60, "susceptibility": 0.50, "activity": 0.55, "trust_in_official": 0.40},
    "repost_kol": {"influence": 0.85, "susceptibility": 0.35, "activity": 0.70, "trust_in_official": 0.30},
    "ordinary_viewer": {"influence": 0.30, "susceptibility": 0.60, "activity": 0.40, "trust_in_official": 0.50},
    "fact_checker": {"influence": 0.55, "susceptibility": 0.20, "activity": 0.45, "trust_in_official": 0.65},
    "official_responder": {"influence": 0.70, "susceptibility": 0.25, "activity": 0.50, "trust_in_official": 0.88},
    "controversy_amplifier": {"influence": 0.50, "susceptibility": 0.65, "activity": 0.80, "trust_in_official": 0.12},
    "victim": {"influence": 0.25, "susceptibility": 0.80, "activity": 0.35, "trust_in_official": 0.50},
    "attacker": {"influence": 0.70, "susceptibility": 0.20, "activity": 0.75, "trust_in_official": 0.05},
    "family_member": {"influence": 0.40, "susceptibility": 0.50, "activity": 0.45, "trust_in_official": 0.55},
    "platform_moderator": {"influence": 0.55, "susceptibility": 0.30, "activity": 0.40, "trust_in_official": 0.70},
    "police_or_bank": {"influence": 0.65, "susceptibility": 0.20, "activity": 0.50, "trust_in_official": 0.92},
}

def looks_like_campus_scene(text: str) -> bool:
    """Only treat as campus when the input is clearly a school incident."""
    raw = str(text or "")
    if not raw.strip():
        return False
    strong = len(_CAMPUS_STRONG.findall(raw))
    context = len(_CAMPUS_CONTEXT.findall(raw))
    social = len(_SOCIAL_OVERRIDE.findall(raw))
    if social and strong == 0:
        return False
    if strong >= 1 and context >= 1:
        return True
    if strong >= 2:
        return True
    if context >= 3 and social == 0:
        return True
    return False


def uses_campus_cast(scenario_type: str = "", scenario_text: str = "") -> bool:
    """Campus roles only belong to public-opinion school incidents."""
    if scenario_type and scenario_type != "public_opinion":
        return False
    return looks_like_campus_scene(scenario_text)


def remap_role_for_scene(
    role: str,
    scenario_text: str = "",
    scenario_type: str = "public_opinion",
) -> str:
    key = str(role or "").strip()
    if uses_campus_cast(scenario_type, scenario_text):
        return key
    return _CAMPUS_ROLE_REMAP.get(key, key)


def role_label_zh(role: str) -> str:
    return _ROLE_LABEL_ZH.get(str(role or ""), "")


def role_pool_for(scenario_type: str, scenario_text: str = "") -> List[str]:
    if uses_campus_cast(scenario_type, scenario_text):
        return list(_SYNTHETIC_ROLE_POOLS["public_opinion_campus"])
    return list(_SYNTHETIC_ROLE_POOLS.get(scenario_type, _SYNTHETIC_ROLE_POOLS["fraud_im"]))


_CAMPUS_DISPLAY_LABELS = {"校方", "老师", "教师", "学生", "普通学生", "学生意见领袖"}


def stamp_scene_roles(
    actors: List[ActorState],
    scenario_type: str,
    scenario_text: str = "",
) -> List[ActorState]:
    """Drop leftover campus roles/labels when the scene is social."""
    campus = uses_campus_cast(scenario_type, scenario_text)
    for actor in actors:
        new_role = remap_role_for_scene(actor.role, scenario_text, scenario_type)
        if new_role != actor.role:
            actor.role = new_role
        zh = role_label_zh(actor.role)
        raw = str(actor.display_name or "").strip()
        english_like = bool(re.fullmatch(r"[A-Za-z0-9_ \-]+", raw)) if raw else True
        if zh and (not raw or english_like or (not campus and raw in _CAMPUS_DISPLAY_LABELS)):
            actor.display_name = zh
    return actors


def build_synthetic_actors(
    scenario_type: str,
    existing_actors: List[ActorState],
    target_count: int = 12,
    seed: int = 42,
    synthetic_id_prefix: str = "actor",
    scenario_text: str = "",
) -> List[ActorState]:
    """Build synthetic actors to fill out the social network.

    Does NOT duplicate roles already present in *existing_actors*.
    """
    import random as _random
    rng = _random.Random(seed)

    pool = role_pool_for(scenario_type, scenario_text)
    existing_roles = {a.role for a in existing_actors}
    available = [r for r in pool if r not in existing_roles]

    start_idx = len(existing_actors)
    needed = max(0, target_count - len(existing_actors))
    synthetic: List[ActorState] = []

    for i in range(needed):
        role = available[i % len(available)] if available else pool[i % len(pool)]
        base = _SYNTHETIC_WEIGHTS.get(role, {"influence": 0.5, "susceptibility": 0.5, "activity": 0.5, "trust_in_official": 0.5})
        actor_id = (
            f"SYNTH_{i + 1:03d}"
            if synthetic_id_prefix.upper() == "SYNTH"
            else f"actor_{(start_idx + i):04d}"
        )
        synthetic.append(ActorState(
            actor_id=actor_id,
            role=role,
            display_name=role_label_zh(role) or f"{role}_{i}",
            provenance=PROVENANCE_SYNTHETIC,
            influence=round(_clamp(base["influence"] + rng.uniform(-0.15, 0.15), 0.01, 1.0), 3),
            susceptibility=round(_clamp(base["susceptibility"] + rng.uniform(-0.15, 0.15), 0.01, 1.0), 3),
            activity=round(_clamp(base["activity"] + rng.uniform(-0.15, 0.15), 0.01, 1.0), 3),
            trust_in_official=round(_clamp(base["trust_in_official"] + rng.uniform(-0.10, 0.10), 0.01, 1.0), 3),
            cognitive_features=ActorCognitiveFeatures(),
        ))
    return synthetic


# ---------------------------------------------------------------------------
# Edge builder
# ---------------------------------------------------------------------------


def build_edges(
    actors: List[ActorState],
    scenario_type: str,
    seed: int = 42,
    scenario_text: str = "",
) -> List[SocialEdge]:
    """Build a social graph using the documented topology generators."""
    from ..propagation.topology import build_topology

    if any(not actor.community_id for actor in actors):
        assign_communities(actors, scenario_type, seed=seed)

    class _TopoAgent:
        def __init__(self, actor: ActorState):
            self.agent_id = actor.actor_id
            self.influence = float(getattr(actor, "influence", 0.5) or 0.5)
            self.role = actor.role
            self.community_id = actor.community_id or ""
            self.metadata = {
                **(actor.metadata or {}),
                "community_id": actor.community_id or "",
            }

    topology_type = demo_topology_type(scenario_type, scenario_text)
    adjacency = build_topology(
        [_TopoAgent(actor) for actor in actors],
        topology_type=topology_type,
        seed=seed,
    )
    edges: List[SocialEdge] = []
    for source_id, neighbours in adjacency.items():
        for target_id in neighbours:
            if not target_id or target_id == source_id:
                continue
            edges.append(SocialEdge(
                edge_id=f"edge_{len(edges):04d}",
                source_actor_id=source_id,
                target_actor_id=target_id,
                relation_type="information_flow",
                weight=0.6,
                provenance=PROVENANCE_SYNTHETIC,
                metadata={"topology_type": topology_type},
            ))
    return edges


# ---------------------------------------------------------------------------
# Full social state builder
# ---------------------------------------------------------------------------


def demo_agent_count(scenario_type: str) -> int:
    """Interactive demo population: opinion 50, event 60, otherwise 12."""
    if scenario_type == "public_opinion":
        return 50
    if scenario_type == "event_propagation":
        return 60
    return 12


def demo_topology_type(scenario_type: str, scenario_text: str = "") -> str:
    if scenario_type == "public_opinion":
        return "campus_local" if looks_like_campus_scene(scenario_text) else "scale_free_like"
    if scenario_type == "event_propagation":
        return "scale_free_like"
    return "small_world"


def build_social_state(
    scenario_text: str,
    scenario_type: str,
    cognitive_profile: Any = None,
    risk_graph: Any = None,
    n_agents: int = 12,
    seed: int = 42,
    canonical_case: Any = None,
) -> SocialState:
    """Build a complete SocialState from input and analysis results.

    This is the main entry point for constructing the unified social graph.
    """
    import uuid

    # 1. Prefer stable observed actors already normalized into CanonicalCase.
    # Legacy direct callers retain the original text-extraction path.
    if canonical_case is not None and getattr(canonical_case, "actors", None):
        input_actors = _actors_from_canonical_case(canonical_case)
    else:
        input_actors = extract_actors_from_text(
            scenario_text,
            max_actors=n_agents // 2,
            scenario_type=scenario_type,
        )

    # 2. Map cognitive features
    if cognitive_profile is not None:
        input_actors = map_cognitive_to_actors(input_actors, cognitive_profile)

    # 3. Add RiskGraph-derived actors (if RiskGraph nodes have identifiable actors)
    if risk_graph is not None:
        try:
            from .mapping import extract_actors_from_risk_graph
            rg_actors = extract_actors_from_risk_graph(
                risk_graph,
                start_idx=len(input_actors),
                id_prefix="INFERRED" if canonical_case is not None else "actor",
            )
            input_actors.extend(rg_actors)
        except Exception:
            pass

    # 4. Fill remaining population with synthetic actors
    target_count = max(n_agents, len(input_actors))
    synthetic = build_synthetic_actors(
        scenario_type,
        input_actors,
        target_count=target_count,
        seed=seed,
        synthetic_id_prefix="SYNTH" if canonical_case is not None else "actor",
        scenario_text=scenario_text,
    )
    all_actors = stamp_scene_roles(input_actors + synthetic, scenario_type, scenario_text)

    # 5. Scene prior -> role-conditioned -> actor-specific state.  The scene
    # profile is never copied directly to every actor.
    scene_prior = build_scene_cognitive_prior(
        cognitive_profile,
        scenario_type=scenario_type,
        scenario_text=scenario_text,
    )
    state_rng = random.Random(seed)
    for actor in all_actors:
        role_base = _SYNTHETIC_WEIGHTS.get(actor.role, {})
        metadata = dict(actor.metadata)
        metadata.setdefault("activity", actor.activity)
        # Input-derived actors usually start with neutral legacy defaults;
        # give them the same bounded role baseline as synthetic actors before
        # adding actor-level heterogeneity.
        if actor.provenance == PROVENANCE_INPUT:
            for key in ("influence", "susceptibility", "activity", "trust_in_official"):
                if key in role_base and getattr(actor, key) == 0.5:
                    setattr(actor, key, round(_clamp(
                        role_base[key] + state_rng.uniform(-0.10, 0.10), 0.01, 1.0
                    ), 3))
            metadata["activity"] = actor.activity
        metadata.setdefault("institutional_trust", actor.trust_in_official)
        actor_state = build_actor_cognitive_state(
            scene_prior,
            actor.role,
            actor_metadata=metadata,
            rng=state_rng,
        )
        apply_actor_cognitive_state(actor, actor_state)

    assign_communities(all_actors, scenario_type, seed=seed)

    # 6. Build edges
    edges = build_edges(all_actors, scenario_type, seed=seed, scenario_text=scenario_text)
    if canonical_case is not None:
        actor_ids = {actor.actor_id for actor in all_actors}
        existing_pairs = {(edge.source_actor_id, edge.target_actor_id) for edge in edges}
        for relation in list(getattr(canonical_case, "relations", []) or []):
            source_id = getattr(relation, "source_actor_id", None)
            target_id = getattr(relation, "target_actor_id", None)
            if isinstance(relation, dict):
                source_id = relation.get("source_actor_id")
                target_id = relation.get("target_actor_id")
            if (
                source_id in actor_ids
                and target_id in actor_ids
                and (source_id, target_id) not in existing_pairs
            ):
                edges.append(SocialEdge(
                    edge_id=f"canonical_relation_{len(edges):04d}",
                    source_actor_id=source_id,
                    target_actor_id=target_id,
                    relation_type="information_flow",
                    provenance=PROVENANCE_INFERRED,
                    metadata={"canonical_relation": True},
                ))
                existing_pairs.add((source_id, target_id))

    # 7. Build claims (from evidence / input)
    claims = _extract_claims(scenario_text, scenario_type)

    # 8. Build evidence list
    evidence = []
    if risk_graph is not None:
        try:
            evidence = list(getattr(risk_graph, "evidence_items", []) or [])
        except Exception:
            pass

    # 9. Initial event
    initial_event = {
        "scenario_type": scenario_type,
        "seed_text": scenario_text[:2000],
        "risk_dimensions": _risk_dimensions_for(scenario_type),
    }

    state = SocialState(
        scenario_id=(getattr(canonical_case, "case_id", None) or str(uuid.uuid4())),
        scenario_type=scenario_type,
        actors=all_actors,
        edges=edges,
        claims=claims,
        evidence=evidence,
        initial_event=initial_event,
        metadata={
            "scene_cognitive_prior": scene_prior,
            "initial_state_source": "canonical_social_state" if canonical_case is not None else "legacy_social_state_builder",
            "shared_initial_world": canonical_case is not None,
            "canonical_case_id": getattr(canonical_case, "case_id", None),
            "topology_type": demo_topology_type(scenario_type, scenario_text),
            "agent_count": len(all_actors),
        },
    )
    state.provenance.update({
        "initial_state_source": state.metadata["initial_state_source"],
        "shared_initial_world": bool(canonical_case is not None),
        "observed_actor_count": sum(1 for actor in all_actors if actor.provenance == PROVENANCE_INPUT),
        "inferred_actor_count": sum(1 for actor in all_actors if actor.provenance == PROVENANCE_INFERRED),
        "synthetic_actor_count": sum(1 for actor in all_actors if actor.provenance == PROVENANCE_SYNTHETIC),
    })
    if canonical_case is not None:
        canonical_case.simulation_state_id = state.simulation_state_id
        canonical_case.provenance.update({
            "shared_simulation_state": True,
            "simulation_state_id": state.simulation_state_id,
            "synthetic_actor_count": state.provenance["synthetic_actor_count"],
            "inferred_actor_count": state.provenance["inferred_actor_count"],
        })
    return state


def _actors_from_canonical_case(canonical_case: Any) -> List[ActorState]:
    """Convert only canonical identity/provenance into dynamic ActorState."""
    actors: List[ActorState] = []
    provenance_map = {
        "observed": PROVENANCE_INPUT,
        "inferred": PROVENANCE_INFERRED,
        "synthetic": PROVENANCE_SYNTHETIC,
    }
    for item in list(getattr(canonical_case, "actors", []) or []):
        def value(key: str, default: Any = None) -> Any:
            if isinstance(item, dict):
                return item.get(key, default)
            return getattr(item, key, default)

        actor_id = value("actor_id", "")
        role = remap_role_for_scene(
            str(value("role", "unknown")),
            str(getattr(canonical_case, "summary", "") or ""),
            str(getattr(canonical_case, "scenario_type", "") or ""),
        )
        display_name = value("display_name", "")
        provenance = value("provenance", "observed")
        evidence_refs = value("evidence_refs", [])
        metadata = value("metadata", {})
        actors.append(ActorState(
            actor_id=str(actor_id),
            role=str(role),
            display_name=str(role_label_zh(role) or display_name),
            provenance=provenance_map.get(str(provenance), PROVENANCE_INFERRED),
            evidence_refs=list(evidence_refs),
            metadata=dict(metadata),
        ))
    return actors


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_claims(text: str, scenario_type: str) -> List[Dict[str, Any]]:
    """Extract simple claims/key assertions from scenario text."""
    claims: List[Dict[str, Any]] = []
    # Simple heuristic: split on common claim markers
    markers = ["称", "表示", "指出", "声称", "发布", "宣称", "曝光"]
    for marker in markers:
        if marker in text:
            idx = text.find(marker)
            snippet = text[max(0, idx - 30):idx + 80]
            claims.append({
                "claim_id": f"claim_{len(claims):04d}",
                "text": snippet.strip(),
                "marker": marker,
                "provenance": PROVENANCE_INPUT,
            })
    if not claims and text:
        claims.append({
            "claim_id": "claim_0000",
            "text": text[:120] + ("..." if len(text) > 120 else ""),
            "marker": "full_input",
            "provenance": PROVENANCE_INPUT,
        })
    return claims[:5]


def _risk_dimensions_for(scenario_type: str) -> List[str]:
    if scenario_type == "public_opinion":
        return ["narrative_intensity", "propagation_velocity", "polarization_index", "information_health"]
    if scenario_type == "event_propagation":
        return ["propagation_speed", "distortion_index", "engagement_depth", "containment_feasibility"]
    return ["risk"]


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))
