import numpy as np
import pytest

from botdetector.metrics.iia import (
    bootstrap_ratio,
    gini,
    profile_audience,
    relative_to_baseline,
    top_share,
)


def test_gini_extremes():
    assert gini(np.ones(100)) == pytest.approx(0.0, abs=0.02)
    concentrated = np.array([0.0] * 99 + [100.0])
    assert gini(concentrated) > 0.95


def test_gini_handles_empty_and_zero():
    assert gini(np.array([])) == 0.0
    assert gini(np.zeros(10)) == 0.0


def test_top_share():
    counts = np.array([1.0] * 99 + [901.0])
    assert top_share(counts, 0.01) == pytest.approx(0.901)


def test_bootstrap_ratio_point_estimate():
    num = np.array([3.0, 0.0, 5.0])
    den = np.array([3.0, 4.0, 5.0])
    est = bootstrap_ratio(num, den, n_resamples=200, seed=0)
    assert est.value == pytest.approx(8 / 12)
    assert est.ci_low <= est.value <= est.ci_high


def test_bootstrap_ratio_empty():
    est = bootstrap_ratio(np.array([]), np.array([]))
    assert np.isnan(est.value)
    assert est.n == 0


def test_coordination_share_weights_by_interactions():
    """50 cuentas que aportan el 40% pesan más que 50 que aportan una cada una."""
    counts = {"farm": 400, **{f"human:{i}": 10 for i in range(60)}}
    p = profile_audience("target", actor_interaction_counts=counts, coordinated_actors={"farm"})
    assert p.coordination_share.value == pytest.approx(400 / 1000)


def test_relative_to_baseline_requires_controls():
    """El IIA absoluto no es interpretable; el código lo impone, no lo sugiere."""
    p = profile_audience("t", actor_interaction_counts={"a": 1}, coordinated_actors=set())
    with pytest.raises(ValueError, match="control"):
        relative_to_baseline(p, [])


def test_relative_to_baseline_ratio():
    target = profile_audience(
        "t", actor_interaction_counts={"x": 60, "y": 40}, coordinated_actors={"x"}
    )
    controls = [
        profile_audience(
            f"c{i}", actor_interaction_counts={"x": 20, "y": 80}, coordinated_actors={"x"}
        )
        for i in range(3)
    ]
    ratios = relative_to_baseline(target, controls)
    assert ratios["coordination_ratio"] == pytest.approx(3.0)
    assert ratios["n_controls"] == 3
