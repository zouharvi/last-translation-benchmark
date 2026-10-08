from last_translation_benchmark.routers import _calculate_human_score


def test_calculate_human_score_uses_verifier_pass_rate():
    submissions = [
        {"translations": [{"model": "human", "verified": [True, True]}]},
        {"translations": [{"model": "human", "verified": [True, False]}]},
        {"translations": [{"model": "human", "verified": []}]},
        {"translations": [{"model": "model-a", "verified": [True]}]},
    ]

    assert _calculate_human_score(submissions) == 0.25


def test_calculate_human_score_returns_none_for_empty_subset():
    assert _calculate_human_score([]) is None
