"""Regression tests for candidate-level OASIS negative veto selection."""

from unittest.mock import MagicMock, patch

import pytest


def _agent(agent_id="agent-1"):
    from modules.propagation.schema import PropagationAgent

    return PropagationAgent(
        agent_id=agent_id,
        role="ordinary_viewer",
        stance="neutral",
        influence=0.5,
        susceptibility=0.5,
        activity=0.5,
        trust_in_official=0.5,
    )


def _candidate(candidate_id, intervention_type, score, target_nodes=None):
    return {
        "candidate_id": candidate_id,
        "intervention_type": intervention_type,
        "target_nodes": list(target_nodes or []),
        "intervention_tick": 1,
        "message": candidate_id,
        "total_score": score,
    }


def _proxy(selected, ranked):
    return {
        "selected_best_branch": selected,
        "branch_comparison": {"ranked_branches": ranked},
    }


def _fake_oasis_result(intervention_coverage):
    result = MagicMock()
    result.branch_a.final_metrics = {"cumulative_coverage": 0.80}
    result.branch_b.final_metrics = {"cumulative_coverage": intervention_coverage}
    return result


def _run_oasis(proxy_result, intervention_coverage):
    from modules.propagation.oasis_verification import run_topk_oasis_verification

    with patch("modules.propagation.oasis_adapter._OASIS_AVAILABLE", True), \
         patch.dict("os.environ", {
             "MIRO_COGSEC_OASIS_API_KEY": "test-key",
             "MIRO_COGSEC_OASIS_BASE_URL": "https://oasis.test/v1",
             "MIRO_COGSEC_OASIS_MODEL": "oasis-test",
         }), \
         patch(
             "modules.propagation.oasis_adapter.OasisPropagationAdapter.run",
             return_value=_fake_oasis_result(intervention_coverage),
         ):
        return run_topk_oasis_verification(
            scenario_type="public_opinion",
            seed_text="test",
            agents=[_agent()],
            proxy_result=proxy_result,
            quick_mode=True,
            k=1,
        )


def test_harmful_proxy_winner_is_vetoed_and_fallback_uses_next_candidate():
    from modules.propagation.intervention_search import resolve_effective_intervention

    official = _candidate("official", "official_response", 0.90)
    friction = _candidate("friction", "friction_prompt", 0.80)
    proxy = _proxy(official, [official, friction])
    result = _run_oasis(proxy, intervention_coverage=0.90)

    assert result["oasis_verified_branches"][0]["effectiveness_status"] == "harmful"
    assert result["negative_veto_applied"] is True
    assert result["selected"]["candidate_id"] == "friction"
    assert [item["candidate_id"] for item in result["final_ranking"]] == ["friction"]
    search = {
        **proxy,
        "proxy_ranked_candidates": result["proxy_ranked_candidates"],
        "oasis_verification": result,
    }
    assert resolve_effective_intervention(search)["candidate_id"] == "friction"


def test_effective_oasis_candidate_still_promotes_over_proxy():
    from modules.propagation.intervention_search import resolve_effective_intervention

    friction = _candidate("friction", "friction_prompt", 0.90)
    official = _candidate("official", "official_response", 0.80)
    proxy = _proxy(friction, [friction, official])
    result = _run_oasis(proxy, intervention_coverage=0.50)

    assert result["selected"]["candidate_id"] == "official"
    assert result["selection_source"] == "oasis"
    search = {
        **proxy,
        "proxy_ranked_candidates": result["proxy_ranked_candidates"],
        "oasis_verification": result,
    }
    assert resolve_effective_intervention(search)["candidate_id"] == "official"


@pytest.mark.parametrize(
    ("verification_status", "effectiveness_status"),
    [
        ("unsupported", "unknown"),
        ("failed", "unknown"),
        ("not_run", "unknown"),
        ("executed", "neutral"),
    ],
)
def test_non_harmful_oasis_status_does_not_veto_proxy_candidate(
    verification_status, effectiveness_status
):
    from modules.propagation.intervention_search import resolve_effective_intervention

    official = _candidate("official", "official_response", 0.90)
    search = {
        "selected_best_branch": official,
        "proxy_ranked_candidates": [official],
        "oasis_verification": {
            "selected": official,
            "oasis_verified_branches": [
                {
                    **official,
                    "verification_status": verification_status,
                    "effectiveness_status": effectiveness_status,
                }
            ],
        },
    }

    assert resolve_effective_intervention(search)["candidate_id"] == "official"


def test_candidate_identity_vetoes_only_matching_candidate_id():
    from modules.propagation.intervention_search import resolve_effective_intervention

    candidate_a = _candidate("official-a", "official_response", 0.90, ["target-a"])
    candidate_b = _candidate("official-b", "official_response", 0.80, ["target-b"])
    search = {
        "selected_best_branch": candidate_a,
        "proxy_ranked_candidates": [candidate_a, candidate_b],
        "oasis_verification": {
            "oasis_verified_branches": [
                {
                    **candidate_a,
                    "verification_status": "executed",
                    "effectiveness_status": "harmful",
                }
            ],
        },
    }

    assert resolve_effective_intervention(search)["candidate_id"] == "official-b"


def test_all_proxy_candidates_vetoed_returns_no_effective_intervention():
    from modules.propagation.intervention_search import resolve_effective_intervention

    official = _candidate("official", "official_response", 0.90)
    search = {
        "selected_best_branch": official,
        "proxy_ranked_candidates": [official],
        "oasis_verification": {
            "oasis_verified_branches": [
                {
                    **official,
                    "verification_status": "executed",
                    "effectiveness_status": "harmful",
                }
            ],
        },
    }

    assert resolve_effective_intervention(search) == {}
