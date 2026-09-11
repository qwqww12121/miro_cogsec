"""Honesty and contradiction regressions for the offline lexical scorer."""

from benchmark.cogsec_benchmark import _semantic_similarity


def test_polarity_flips_do_not_receive_high_similarity():
    pairs = [
        ("更正已覆盖原传播链", "更正未覆盖原传播链"),
        ("无需干预", "需要立即干预"),
        ("信息已经证实", "信息未经证实"),
        ("风险很高", "风险很低"),
    ]
    assert all(_semantic_similarity(left, right) <= 0.25 for left, right in pairs)


def test_noncontradictory_paraphrase_keeps_partial_credit():
    assert _semantic_similarity("官方回应并补充来源", "官方澄清并提供原始来源") > 0.3
