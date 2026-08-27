import numpy as np
import pytest

from botdetector.validation import sampling
from botdetector.validation.curves import MINIMUM_COVERAGE, is_publishable


def _edges(n_actors=20, n_targets=10):
    return [(f"a{i}", f"p{j}") for i in range(n_actors) for j in range(n_targets)]


def test_uniform_keeps_roughly_the_fraction():
    edges = _edges(100, 20)
    kept = sampling.uniform(edges, 0.5, np.random.default_rng(0))
    assert 0.45 < len(kept) / len(edges) < 0.55


def test_uniform_full_is_identity():
    edges = _edges()
    assert sampling.uniform(edges, 1.0, np.random.default_rng(0)) == edges


def test_per_target_cap_never_exceeds_cap():
    edges = _edges(50, 5)
    kept = sampling.per_target_cap(edges, 7, np.random.default_rng(0))
    per_target: dict[str, int] = {}
    for _, t in kept:
        per_target[t] = per_target.get(t, 0) + 1
    assert max(per_target.values()) == 7


def test_per_target_cap_leaves_small_targets_intact():
    """El tope de X solo trunca lo viral; lo poco popular se observa entero."""
    edges = [("a", "raro"), ("b", "raro")] + [(f"x{i}", "viral") for i in range(50)]
    kept = sampling.per_target_cap(edges, 10, np.random.default_rng(0))
    assert sum(1 for _, t in kept if t == "raro") == 2
    assert sum(1 for _, t in kept if t == "viral") == 10


def test_actor_subset_keeps_full_activity_of_kept_actors():
    """Si una cuenta entra en la muestra, entra con toda su actividad."""
    edges = _edges(30, 8)
    kept = sampling.actor_subset(edges, 0.5, np.random.default_rng(1))
    kept_actors = {a for a, _ in kept}
    for actor in kept_actors:
        assert sum(1 for a, _ in kept if a == actor) == 8


def test_target_subset_keeps_full_engagement_of_kept_targets():
    edges = _edges(12, 20)
    kept = sampling.target_subset(edges, 0.5, np.random.default_rng(2))
    kept_targets = {t for _, t in kept}
    for target in kept_targets:
        assert sum(1 for _, t in kept if t == target) == 12


def test_retention():
    edges = _edges(10, 10)
    assert sampling.retention(edges[:25], edges) == pytest.approx(0.25)
    assert sampling.retention([], edges) == 0.0


def test_every_strategy_is_reproducible_given_seed():
    edges = _edges(40, 10)
    for name, fn in sampling.STRATEGIES.items():
        a = fn(edges, 0.5, np.random.default_rng(7))
        b = fn(edges, 0.5, np.random.default_rng(7))
        assert a == b, name


def test_sweep_produces_a_monotone_ish_curve():
    """La curva debe degradarse al perder datos, y la retencion debe reflejarlo."""
    from botdetector.validation import sweep

    points = sweep(
        regime="uniform",
        parameters=[1.0, 0.3],
        seeds=[1, 2],
        fidelity=0.95,
        n_coordinated=30,
    )
    full, sparse = points

    assert full.retention == pytest.approx(1.0)
    assert sparse.retention < 0.4
    assert full.recall >= sparse.recall
    assert full.n_runs == 2


def test_sweep_marks_precision_undefined_when_nothing_detected():
    """No detectar nada y detectar mal son fallos distintos; no deben mezclarse."""
    from botdetector.validation import sweep

    (point,) = sweep(
        regime="uniform",
        parameters=[0.05],
        seeds=[1, 2],
        fidelity=0.95,
        n_coordinated=30,
    )
    assert point.detection_rate == 0.0
    assert np.isnan(point.precision)
    assert point.recall == 0.0


class TestCoverageFloors:
    def test_above_floor_is_publishable(self):
        ok, reason = is_publishable("uniform", 0.95)
        assert ok
        assert "interpretable" in reason

    def test_below_floor_blocks_publication(self):
        ok, _ = is_publishable("uniform", 0.5)
        assert not ok

    def test_blindness_and_falsification_are_distinguished(self):
        """Quedarse ciego y equivocarse son fallos distintos; el motivo lo dice."""
        _, blind = is_publishable("uniform", 0.5)
        _, false = is_publishable("target_subset", 0.2)

        assert "ciego" in blind
        assert "ausencia de coordinación" in blind
        assert "fabricar" in false
        assert "NO publicar" in false

    def test_unknown_regime_is_refused(self):
        ok, reason = is_publishable("inventado", 1.0)
        assert not ok
        assert "desconocido" in reason

    def test_target_subset_floor_is_the_strictest_among_fraction_regimes(self):
        """El regimen que puede fabricar clusters exige mas que los que solo ciegan."""
        assert MINIMUM_COVERAGE["target_subset"] > MINIMUM_COVERAGE["actor_subset"]
