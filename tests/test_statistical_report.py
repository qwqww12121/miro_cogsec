from benchmark.statistical_report import paired_summary, summarize_by_scenario


def test_paired_summary_reports_delta_and_ci():
    summary = paired_summary([0.8, 0.7, 0.9], [0.6, 0.8, 0.7], bootstrap_samples=100)
    assert summary["n"] == 3
    assert summary["paired_delta"] > 0
    assert len(summary["paired_delta_ci95"]) == 2


def test_scenario_summary_keeps_groups_separate():
    result = summarize_by_scenario([
        {"scenario": "fraud_im", "miro": 0.8, "baseline": 0.7},
        {"scenario": "public_opinion", "miro": 0.5, "baseline": 0.6},
    ])
    assert set(result) == {"fraud_im", "public_opinion"}
