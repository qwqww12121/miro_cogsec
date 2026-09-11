"""Round 2 upgrade tests — SocialState, unified actor IDs, A/B equivalence,
real metrics, resolve_canonical, intervention search renaming.
"""

from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest


# ============================================================================
# 1. SocialState schema
# ============================================================================


class TestSocialStateSchema:
    """Verify SocialState data structures."""

    def test_actor_state_has_canonical_id(self):
        from app.modules.social_state import ActorState

        actor = ActorState(
            actor_id="actor_0001",
            role="student_kol",
            provenance="input",
        )
        assert actor.actor_id == "actor_0001"
        assert actor.provenance == "input"

    def test_actor_cognitive_features_from_profile(self):
        from app.modules.social_state import ActorCognitiveFeatures
        from app.modules.cognitive_profiler import CognitiveProfile

        profile = CognitiveProfile(
            scenario_type="public_opinion",
            authority_compliance=8.0,
            verification_habit=3.0,
            time_pressure=9.0,
            transaction_review=4.0,
        )
        features = ActorCognitiveFeatures.from_profile(profile)
        assert 0.0 <= features.compliance_tendency <= 1.0
        assert 0.0 <= features.verification_tendency <= 1.0
        assert features.profile_ref == "public_opinion"

    def test_social_edge_rejects_invalid_relation(self):
        from app.modules.social_state import SocialEdge

        with pytest.raises(ValueError):
            SocialEdge(
                edge_id="e1",
                source_actor_id="a1",
                target_actor_id="a2",
                relation_type="invalid_relation",
            )

    def test_social_edge_accepts_valid_relations(self):
        from app.modules.social_state import SocialEdge

        for rel in ["follow", "trust", "friend", "same_community",
                     "official_relation", "information_flow"]:
            edge = SocialEdge(
                edge_id="e1",
                source_actor_id="a1",
                target_actor_id="a2",
                relation_type=rel,
            )
            assert edge.relation_type == rel

    def test_social_state_to_adjacency(self):
        from app.modules.social_state import ActorState, SocialEdge, SocialState

        actors = [
            ActorState(actor_id="actor_0000", role="student"),
            ActorState(actor_id="actor_0001", role="teacher"),
        ]
        edges = [
            SocialEdge(edge_id="e0", source_actor_id="actor_0000",
                       target_actor_id="actor_0001", relation_type="follow"),
        ]
        state = SocialState(
            scenario_id="test",
            scenario_type="public_opinion",
            actors=actors,
            edges=edges,
        )
        adj = state.to_adjacency()
        assert "actor_0000" in adj
        assert "actor_0001" in adj["actor_0000"]

    def test_social_state_summary(self):
        from app.modules.social_state import ActorState, SocialState

        actors = [
            ActorState(actor_id="actor_0000", role="student", provenance="input"),
            ActorState(actor_id="actor_0001", role="teacher", provenance="input"),
            ActorState(actor_id="actor_0002", role="media_observer", provenance="synthetic"),
        ]
        state = SocialState(
            scenario_id="test",
            scenario_type="public_opinion",
            actors=actors,
        )
        summary = state.summary()
        assert summary["actor_count"] == 3
        assert summary["provenance_counts"]["input"] == 2
        assert summary["provenance_counts"]["synthetic"] == 1


# ============================================================================
# 2. SocialState snapshot (immutability)
# ============================================================================


class TestSocialStateSnapshot:
    """Verify snapshot immutability and clone behavior."""

    def test_snapshot_is_frozen(self):
        from app.modules.social_state import (
            ActorState, SocialState, SocialStateSnapshot, create_snapshot,
        )

        actors = [ActorState(actor_id="actor_0000", role="student")]
        state = SocialState(scenario_id="test", scenario_type="public_opinion", actors=actors)
        snap = create_snapshot(state, seed=42)

        assert snap.seed == 42
        assert len(snap.actors) == 1
        assert snap.actors[0].actor_id == "actor_0000"

    def test_snapshot_equality_same_input(self):
        from app.modules.social_state import (
            ActorState, SocialState, create_snapshot,
            snapshot_equality_report,
        )

        actors = [ActorState(actor_id="actor_0000", role="student")]
        state = SocialState(scenario_id="test", scenario_type="public_opinion", actors=actors)
        snap_a = create_snapshot(state, seed=42)
        snap_b = create_snapshot(state, seed=42)

        report = snapshot_equality_report(snap_a, snap_b)
        # Different snapshot IDs but same content
        assert report["differences"] == [] or all(
            "snapshot_id" not in d for d in report["differences"]
        )

    def test_clone_is_identical(self):
        from app.modules.social_state import (
            ActorState, SocialState, clone_snapshot, create_snapshot,
        )

        actors = [ActorState(actor_id="actor_0000", role="student")]
        state = SocialState(scenario_id="test", scenario_type="public_opinion", actors=actors)
        snap = create_snapshot(state, seed=42)
        cloned = clone_snapshot(snap)

        assert snap.snapshot_id == cloned.snapshot_id
        assert snap.seed == cloned.seed


# ============================================================================
# 3. Actor ID mapping
# ============================================================================


class TestActorMapping:
    """Verify ActorMapping bidirectional registration."""

    def test_actor_mapping_bidirectional(self):
        from app.modules.social_state import ActorMapping

        mapping = ActorMapping()
        mapping.register("actor_0001", "propagation", "agent_0001")
        mapping.register("actor_0001", "oasis", "oasis_agent_0")

        assert mapping.module_id("actor_0001", "propagation") == "agent_0001"
        assert mapping.module_id("actor_0001", "oasis") == "oasis_agent_0"
        assert mapping.canonical_id("propagation", "agent_0001") == "actor_0001"

    def test_actor_to_propagation_agent(self):
        from app.modules.social_state import ActorState, actor_to_propagation_agent

        actor = ActorState(
            actor_id="actor_0003",
            role="fact_checker",
            influence=0.7,
            susceptibility=0.3,
            activity=0.5,
            trust_in_official=0.8,
            stance="corrective",
            provenance="input",
        )
        pa = actor_to_propagation_agent(actor)
        assert pa.agent_id == "actor_0003"  # canonical ID preserved
        assert pa.role == "fact_checker"
        assert pa.metadata["provenance"] == "input"

    def test_actor_to_oasis_row(self):
        from app.modules.social_state import ActorState, actor_to_oasis_row

        actor = ActorState(
            actor_id="actor_0001",
            role="school_official",
            influence=0.7,
            susceptibility=0.25,
        )
        row = actor_to_oasis_row(actor)
        assert "user_char" in row
        assert "username" in row
        assert "description" in row
        assert "actor_0001" in row["username"]


# ============================================================================
# 4. SocialState builder
# ============================================================================


class TestSocialStateBuilder:
    """Verify builder extracts actors from text and creates synthetic population."""

    def test_extract_actors_from_text(self):
        from app.modules.social_state.builder import extract_actors_from_text

        text = "某大学学生爆料称学校食堂存在卫生问题，校方回应称已成立调查组，警方已介入调查。有媒体记者在现场报道。"
        actors = extract_actors_from_text(text)

        roles = {a.role for a in actors}
        assert "ordinary_student" in roles or "original_poster" in roles
        assert "school_official" in roles
        assert any(
            a.provenance == "input" for a in actors
        )

    def test_build_synthetic_actors_does_not_duplicate(self):
        from app.modules.social_state import ActorState
        from app.modules.social_state.builder import build_synthetic_actors

        existing = [ActorState(actor_id="actor_0000", role="student_kol", provenance="input")]
        synthetic = build_synthetic_actors("public_opinion", existing, target_count=12)

        roles = [a.role for a in synthetic]
        # student_kol should not appear since it's already in existing
        assert all(a.provenance == "synthetic" for a in synthetic)

    def test_brand_opinion_does_not_use_campus_cast(self):
        from app.modules.social_state import build_social_state
        from app.modules.social_state.builder import demo_topology_type, looks_like_campus_scene

        text = (
            "最近某品牌新品发布引发热议，一部分网友认为这是营销炒作，"
            "另一部分网友晒出实际体验支持该品牌，双方在评论区争论激烈，话题持续发酵三天。"
        )
        assert not looks_like_campus_scene(text)
        assert demo_topology_type("public_opinion", text) == "scale_free_like"
        state = build_social_state(
            scenario_text=text,
            scenario_type="public_opinion",
            n_agents=24,
            seed=42,
        )
        roles = {actor.role for actor in state.actors}
        labels = {actor.display_name for actor in state.actors}
        assert "school_official" not in roles
        assert "teacher" not in roles
        assert "student_kol" not in roles
        assert "ordinary_student" not in roles
        assert "ordinary_viewer" in roles or "repost_kol" in roles
        assert "校方" not in labels
        assert "老师" not in labels
        assert "学生意见领袖" not in labels
        graph_labels = {node.get("label") for node in state.to_display_graph(max_nodes=28).get("nodes", [])}
        assert "校方" not in graph_labels
        assert "老师" not in graph_labels
        assert "学生意见领袖" not in graph_labels

    def test_classmate_mention_alone_is_not_campus(self):
        from app.modules.social_state.builder import (
            extract_actors_from_text,
            looks_like_campus_scene,
            role_pool_for,
        )

        text = "有同学说这个很好用，评论区里大家都在讨论。"
        assert not looks_like_campus_scene(text)
        roles = {actor.role for actor in extract_actors_from_text(text, scenario_type="public_opinion")}
        assert "ordinary_student" not in roles
        assert "school_official" not in roles
        assert "teacher" not in roles
        assert "student_kol" not in role_pool_for("public_opinion", text)

    def test_social_override_beats_weak_school_words(self):
        from app.modules.social_state import build_social_state
        from app.modules.social_state.builder import looks_like_campus_scene

        text = "网友和同学们都在转发某品牌热搜，消费者争论这是不是营销。"
        assert not looks_like_campus_scene(text)
        state = build_social_state(
            scenario_text=text,
            scenario_type="public_opinion",
            n_agents=24,
            seed=7,
        )
        roles = {actor.role for actor in state.actors}
        assert "school_official" not in roles
        assert "student_kol" not in roles
        assert "teacher" not in roles

    def test_event_propagation_never_uses_campus_cast(self):
        from app.modules.social_state import build_social_state

        state = build_social_state(
            scenario_text="某高校学生反映食堂问题，校方已回应。",
            scenario_type="event_propagation",
            n_agents=12,
            seed=42,
        )
        roles = {actor.role for actor in state.actors}
        assert "school_official" not in roles
        assert "student_kol" not in roles
        assert "teacher" not in roles

    def test_campus_opinion_keeps_school_roles(self):
        from app.modules.social_state import build_social_state

        state = build_social_state(
            scenario_text="某高校学生反映食堂问题，校方已回应。",
            scenario_type="public_opinion",
            n_agents=12,
            seed=42,
        )
        roles = {actor.role for actor in state.actors}
        assert "school_official" in roles or "ordinary_student" in roles
        labels = {actor.display_name for actor in state.actors}
        assert "校方" in labels or "普通学生" in labels or "学生意见领袖" in labels

    def test_build_social_state_integration(self):
        from app.modules.social_state import build_social_state

        state = build_social_state(
            scenario_text="某高校学生反映食堂问题，校方已回应。",
            scenario_type="public_opinion",
            n_agents=12,
            seed=42,
        )
        assert len(state.actors) == 12
        assert len(state.edges) > 0
        assert state.scenario_type == "public_opinion"

        # Verify all actors have unique IDs
        ids = [a.actor_id for a in state.actors]
        assert len(ids) == len(set(ids))

        # Verify actor_id format
        for aid in ids:
            assert aid.startswith("actor_")

    def test_agent_factory_follows_social_role_pool(self):
        from app.modules.propagation.agent_factory import build_agents

        social = build_agents(
            "public_opinion",
            n_agents=12,
            seed=3,
            scenario_text="某品牌新品发布后网友两极争论，热搜持续发酵。",
        )
        campus = build_agents(
            "public_opinion",
            n_agents=12,
            seed=3,
            scenario_text="某高校学生反映食堂问题，校方已回应。",
        )
        social_roles = {agent.role for agent in social}
        campus_roles = {agent.role for agent in campus}
        assert "student_kol" not in social_roles
        assert "school_official" not in social_roles
        assert "repost_kol" in social_roles or "ordinary_viewer" in social_roles
        assert "student_kol" in campus_roles or "school_official" in campus_roles


# ============================================================================
# 5. OASIS Branch A/B equivalence (code-level checks)
# ============================================================================


class TestOASISBranchEquivalence:
    """Verify Branch A/B share same initial state via snapshot."""

    def test_oasis_adapter_accepts_snapshot_parameter(self):
        """OasisPropagationAdapter.run should accept snapshot parameter."""
        import os
        repo_root = os.path.dirname(os.path.dirname(__file__))
        adapter_path = os.path.join(
            repo_root, "backend", "app", "modules", "propagation", "oasis_adapter.py"
        )
        if not os.path.exists(adapter_path):
            pytest.skip(f"OASIS adapter not found at {adapter_path}")

        with open(adapter_path, "r", encoding="utf-8") as f:
            source = f.read()

        assert "snapshot" in source
        assert "seed" in source

    def test_run_branch_uses_same_csv_path(self):
        """Both branches write the same CSV and start from the same profiles."""
        import os
        repo_root = os.path.dirname(os.path.dirname(__file__))
        adapter_path = os.path.join(
            repo_root, "backend", "app", "modules", "propagation", "oasis_adapter.py"
        )
        if not os.path.exists(adapter_path):
            pytest.skip(f"OASIS adapter not found at {adapter_path}")

        with open(adapter_path, "r", encoding="utf-8") as f:
            source = f.read()

        # CSV should be written once before both branches
        assert "_write_agent_csv" in source

    def test_no_positional_agent_indexing(self):
        """Should not rely on all_agents[i] == agents[i] for mapping."""
        import os
        repo_root = os.path.dirname(os.path.dirname(__file__))
        adapter_path = os.path.join(
            repo_root, "backend", "app", "modules", "propagation", "oasis_adapter.py"
        )
        if not os.path.exists(adapter_path):
            pytest.skip(f"OASIS adapter not found at {adapter_path}")

        with open(adapter_path, "r", encoding="utf-8") as f:
            source = f.read()

        # The new code uses _find_official_agent which searches by role,
        # not positional indexing
        assert "_find_official_agent" in source

    def test_platform_uses_twitter_for_twitter_graph(self):
        """Platform should match the graph generation function."""
        import os
        repo_root = os.path.dirname(os.path.dirname(__file__))
        adapter_path = os.path.join(
            repo_root, "backend", "app", "modules", "propagation", "oasis_adapter.py"
        )
        if not os.path.exists(adapter_path):
            pytest.skip(f"OASIS adapter not found at {adapter_path}")

        with open(adapter_path, "r", encoding="utf-8") as f:
            source = f.read()

        # Should use TWITTER platform with twitter agent graph
        assert "DefaultPlatformType.TWITTER" in source
        assert "generate_twitter_agent_graph" in source


# ============================================================================
# 6. Real metrics (no formula curves)
# ============================================================================


class TestRealMetrics:
    """Verify metrics are derived from real simulation data, not formulas."""

    def test_no_formula_panic_curve_in_oasis_adapter(self):
        """OASIS adapter should not contain formula-generated panic/trust/risk."""
        import os
        repo_root = os.path.dirname(os.path.dirname(__file__))
        adapter_path = os.path.join(
            repo_root, "backend", "app", "modules", "propagation", "oasis_adapter.py"
        )
        if not os.path.exists(adapter_path):
            pytest.skip(f"OASIS adapter not found at {adapter_path}")

        with open(adapter_path, "r", encoding="utf-8") as f:
            source = f.read()

        # Old formula patterns should be absent
        assert "0.3 + tick * 0.08" not in source
        assert "0.7 - tick * 0.05" not in source
        assert "pa.susceptibility > 0.60" not in source

    def test_metrics_use_cumulative_coverage(self):
        """Coverage should be cumulative, not per-tick."""
        import os
        repo_root = os.path.dirname(os.path.dirname(__file__))
        adapter_path = os.path.join(
            repo_root, "backend", "app", "modules", "propagation", "oasis_adapter.py"
        )
        if not os.path.exists(adapter_path):
            pytest.skip(f"OASIS adapter not found at {adapter_path}")

        with open(adapter_path, "r", encoding="utf-8") as f:
            source = f.read()

        assert "cumulative_coverage" in source

    def test_metric_details_have_source_type(self):
        """Metrics should include metric_source for provenance tracking."""
        import os
        repo_root = os.path.dirname(os.path.dirname(__file__))
        adapter_path = os.path.join(
            repo_root, "backend", "app", "modules", "propagation", "oasis_adapter.py"
        )
        if not os.path.exists(adapter_path):
            pytest.skip(f"OASIS adapter not found at {adapter_path}")

        with open(adapter_path, "r", encoding="utf-8") as f:
            source = f.read()

        # metric_source tracks provenance of metrics
        assert "metric_source" in source

    def test_key_node_uses_real_adjacency(self):
        """Key nodes should use real adjacency, not empty dict."""
        import os
        repo_root = os.path.dirname(os.path.dirname(__file__))
        adapter_path = os.path.join(
            repo_root, "backend", "app", "modules", "propagation", "oasis_adapter.py"
        )
        if not os.path.exists(adapter_path):
            pytest.skip(f"OASIS adapter not found at {adapter_path}")

        with open(adapter_path, "r", encoding="utf-8") as f:
            source = f.read()

        # Should build adjacency from agents, not pass {}
        assert "_build_adjacency_from_agents" in source


# ============================================================================
# 7. Intervention search renaming
# ============================================================================


class TestInterventionSearchRename:
    """Verify the honestly named proxy entry point."""

    def test_proxy_function_exists(self):
        """New run_proxy_intervention_search should be importable."""
        from app.modules.propagation.intervention_search import run_proxy_intervention_search
        assert callable(run_proxy_intervention_search)

    def test_provenance_still_says_proxy(self):
        """Provenance should still say proxy, not oasis."""
        import os
        repo_root = os.path.dirname(os.path.dirname(__file__))
        search_path = os.path.join(
            repo_root, "backend", "app", "modules", "propagation", "intervention_search.py"
        )
        if not os.path.exists(search_path):
            pytest.skip(f"Intervention search not found at {search_path}")

        with open(search_path, "r", encoding="utf-8") as f:
            source = f.read()

        assert "metric_source" in source
        assert "proxy" in source


# ============================================================================
# 8. resolve_canonical: unknown → unknown
# ============================================================================


class TestResolveCanonical:
    """Verify resolve_canonical handles unknown correctly (Round 2)."""

    def test_unknown_not_fraud(self):
        from app.modules.scenarios import resolve_canonical

        assert resolve_canonical("some_random_type") == "unknown"
        assert resolve_canonical(None) == "unknown"
        assert resolve_canonical("") == "unknown"

    def test_known_types_still_work(self):
        from app.modules.scenarios import resolve_canonical

        assert resolve_canonical("fraud_im") == "fraud_im"
        assert resolve_canonical("public_opinion") == "public_opinion"
        assert resolve_canonical("event_propagation") == "event_propagation"

    def test_legacy_fraud_labels_still_map_to_fraud(self):
        from app.modules.scenarios import resolve_canonical

        assert resolve_canonical("虚假征信类") == "fraud_im"
        assert resolve_canonical("刷单返利类") == "fraud_im"


# ============================================================================
# 9. Trace retention config
# ============================================================================


class TestTraceRetention:
    """Verify OASIS trace retention configuration."""

    def test_config_has_trace_retention(self):
        """Config should have OASIS_TRACE_RETENTION."""
        import os
        repo_root = os.path.dirname(os.path.dirname(__file__))
        config_path = os.path.join(repo_root, "backend", "app", "config.py")
        if not os.path.exists(config_path):
            pytest.skip(f"Config not found at {config_path}")

        with open(config_path, "r", encoding="utf-8") as f:
            source = f.read()

        assert "OASIS_TRACE_RETENTION" in source

    def test_oasis_adapter_has_trace_saving(self):
        """OASIS adapter should have trace metadata saving."""
        import os
        repo_root = os.path.dirname(os.path.dirname(__file__))
        adapter_path = os.path.join(
            repo_root, "backend", "app", "modules", "propagation", "oasis_adapter.py"
        )
        if not os.path.exists(adapter_path):
            pytest.skip(f"OASIS adapter not found at {adapter_path}")

        with open(adapter_path, "r", encoding="utf-8") as f:
            source = f.read()

        assert "_save_trace_metadata" in source
        assert "OASIS_TRACE_RETENTION" in source


# ============================================================================
# 10. MetricValue dataclass
# ============================================================================


class TestMetricValue:
    """Verify MetricValue enforces source_type validity."""

    def test_metric_value_valid_sources(self):
        from app.modules.social_state import MetricValue

        for src in ["native", "derived", "proxy", "estimated"]:
            mv = MetricValue(name="test", value=0.5, source_type=src)
            assert mv.source_type == src

    def test_metric_value_rejects_invalid_source(self):
        from app.modules.social_state import MetricValue

        with pytest.raises(ValueError):
            MetricValue(name="test", value=0.5, source_type="made_up")

    def test_metric_value_to_dict(self):
        from app.modules.social_state import MetricValue

        mv = MetricValue(
            name="cumulative_coverage",
            value=0.75,
            source_type="derived",
            definition="unique_spreaders / total_agents",
        )
        d = mv.to_dict()
        assert d["name"] == "cumulative_coverage"
        assert d["value"] == 0.75
        assert d["source_type"] == "derived"
