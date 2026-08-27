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


class TestRecencyBias:
    """El régimen real de X: se conservan los interactuantes más recientes."""

    def test_keeps_the_latest_not_a_random_sample(self):
        edges = [(f"a{i}", "p") for i in range(10)]
        latency = [i / 10 for i in range(10)]  # a0 el más temprano, a9 el más tardío
        kept = sampling.recency_cap(edges, 3, latency, np.random.default_rng(0))
        assert {a for a, _ in kept} == {"a7", "a8", "a9"}

    def test_erases_a_fast_campaign_entirely(self):
        """El hallazgo de docs/ESCALA.md, como test de regresión.

        Una granja rápida sobre una publicación con muchos más interactuantes
        que el tope desaparece por completo, mientras que un tope aleatorio del
        mismo tamaño conservaría una fracción representativa.
        """
        farm = [(f"bot{i}", "viral") for i in range(30)]
        crowd = [(f"human{i}", "viral") for i in range(400)]
        edges = farm + crowd
        latency = [0.01] * len(farm) + list(np.linspace(0.1, 1.0, len(crowd)))

        recency = sampling.recency_cap(edges, 100, latency, np.random.default_rng(0))
        random_cap = sampling.per_target_cap(edges, 100, np.random.default_rng(0))

        surviving_bots_recency = sum(1 for a, _ in recency if a.startswith("bot"))
        surviving_bots_random = sum(1 for a, _ in random_cap if a.startswith("bot"))

        assert surviving_bots_recency == 0
        assert surviving_bots_random > 0

    def test_does_not_truncate_below_the_cap(self):
        edges = [(f"a{i}", "p") for i in range(5)]
        kept = sampling.recency_cap(edges, 100, [0.5] * 5, np.random.default_rng(0))
        assert len(kept) == 5

    def test_rejects_misaligned_latency(self):
        with pytest.raises(ValueError, match="alineado"):
            sampling.recency_cap([("a", "p")], 10, [0.1, 0.2], np.random.default_rng(0))


def test_generator_makes_the_campaign_act_faster_than_the_crowd():
    """Sin esta diferencia de latencia no se puede simular el sesgo de recencia."""
    from botdetector.validation import generate

    aud = generate(fidelity=1.0, n_coordinated=30, seed=0)
    lat = np.array(aud.latency)
    is_coord = np.array([a in aud.coordinated_actors for a, _ in aud.edges])

    assert lat[is_coord].max() < lat[~is_coord].mean()


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

    def test_below_floor_means_blind_not_wrong(self):
        """Con el criterio hipergeométrico, quedarse corto de datos ciega, no miente.

        Con el criterio de coseno anterior, `target_subset` llegaba a fabricar
        clusters de cuentas reales. Ese modo de fallo ya no existe, y el motivo
        que devuelve la función lo refleja.
        """
        _, reason = is_publishable("target_subset", 0.1)
        assert "ciego" in reason
        assert "ausencia de coordinación" in reason
        assert "fabricar" not in reason

    def test_unknown_regime_is_refused(self):
        ok, reason = is_publishable("inventado", 1.0)
        assert not ok
        assert "desconocido" in reason

    def test_uniform_is_the_strictest_regime(self):
        """El muestreo uniforme rompe los pares, así que exige más cobertura.

        La señal vive en pares de interacciones: bajo muestreo uniforme a tasa p
        cada par sobrevive con probabilidad p². Los regímenes que preservan
        cuentas o publicaciones enteras conservan los pares y aguantan mucho más.
        """
        assert MINIMUM_COVERAGE["uniform"] > MINIMUM_COVERAGE["actor_subset"]
        assert MINIMUM_COVERAGE["uniform"] > MINIMUM_COVERAGE["target_subset"]
