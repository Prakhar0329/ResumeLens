import math

import numpy as np
import pytest

from app.services.scorer import (
    SkillPriorityWeights,
    Weights,
    best_match_mean,
    combine,
    rescale,
    skill_coverage,
    verdict_for,
)


def test_weights_normalise_to_one():
    w = Weights(5, 3.5, 1.5).normalised()
    assert math.isclose(w.skill + w.semantic + w.keyword, 1.0)
    assert math.isclose(w.skill, 0.5)


def test_zero_weights_rejected():
    with pytest.raises(ValueError):
        Weights(0, 0, 0).normalised()


def test_combined_weights_sum_to_one():
    result = combine(80, 60, 40, Weights(0.5, 0.35, 0.15))
    w = result.weights
    assert math.isclose(w.skill + w.semantic + w.keyword, 1.0, abs_tol=1e-3)
    assert result.overall == pytest.approx(0.5 * 80 + 0.35 * 60 + 0.15 * 40, abs=0.05)
    assert not result.skill_weight_redistributed


@pytest.mark.parametrize("value,expected", [(0.10, 0.0), (0.20, 0.0), (0.475, 50.0), (0.75, 100.0), (0.95, 100.0)])
def test_rescale_clips_to_band(value, expected):
    assert rescale(value, 0.20, 0.75) == pytest.approx(expected)


def test_rescale_rejects_bad_band():
    with pytest.raises(ValueError):
        rescale(0.5, 0.7, 0.2)


@pytest.mark.parametrize(
    "score,verdict",
    [
        (0, "Weak match"),
        (39.9, "Weak match"),
        (40, "Partial match"),
        (64.9, "Partial match"),
        (65, "Strong match"),
        (84.9, "Strong match"),
        (85, "Excellent match"),
        (100, "Excellent match"),
    ],
)
def test_verdict_thresholds(score, verdict):
    assert verdict_for(score) == verdict


def test_skill_coverage_weighted_by_requirement_type():
    jd = {"Python": "required", "SQL": "unspecified", "Kafka": "preferred"}
    # found: Python (2.0) + Kafka (0.5) out of 3.5
    assert skill_coverage(jd, {"Python", "Kafka"}) == pytest.approx(100 * 2.5 / 3.5)
    assert skill_coverage(jd, set()) == 0
    assert skill_coverage(jd, {"Python", "SQL", "Kafka"}) == pytest.approx(100)


def test_skill_coverage_custom_priorities_and_empty_jd():
    jd = {"A": "required", "B": "preferred"}
    assert skill_coverage(jd, {"B"}, SkillPriorityWeights(1, 1, 1)) == pytest.approx(50)
    assert skill_coverage({}, {"A"}) is None
    assert skill_coverage(jd, {"A"}, SkillPriorityWeights(0, 0, 0)) is None


def test_zero_skill_jd_redistributes_weight_proportionally():
    result = combine(None, 60, 40, Weights(0.5, 0.35, 0.15))
    assert result.skill_weight_redistributed
    assert result.weights.skill == 0
    assert result.weights.semantic == pytest.approx(0.7)
    assert result.weights.keyword == pytest.approx(0.3)
    assert result.overall == pytest.approx(0.7 * 60 + 0.3 * 40, abs=0.05)
    assert result.skill_coverage == 0


def test_redistribution_when_only_skill_weight_configured():
    result = combine(None, 60, 40, Weights(1, 0, 0))
    assert result.weights.semantic == 0.5 and result.weights.keyword == 0.5
    assert result.overall == 50.0


def test_overall_rounded_to_one_decimal():
    result = combine(33.333, 66.666, 11.111, Weights(1, 1, 1))
    assert result.overall == round(result.overall, 1)


def test_best_match_mean():
    sim = np.array([[0.1, 0.9], [0.5, 0.3]])
    assert best_match_mean(sim) == pytest.approx(0.7)
    assert best_match_mean(np.zeros((0, 0))) == 0.0
