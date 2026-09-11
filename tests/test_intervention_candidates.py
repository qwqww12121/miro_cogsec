"""Intervention wording should bind to the current case, not a fixed answer."""

from app.modules.propagation.intervention_search import _candidate_cue, _evidence_basis


def test_candidate_cue_uses_observed_case_clause():
    first = _evidence_basis("校园通知被截断后传播。后续说法丢失时间。", {})
    second = _evidence_basis("事故图片被移花接木。后续出现地点误传。", {})
    assert first[0] == "校园通知被截断后传播"
    assert second[0] == "事故图片被移花接木"
    assert _candidate_cue(first) != _candidate_cue(second)
