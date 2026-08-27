"""Validación estadística de enlaces por test hipergeométrico.

El test central de este fichero es `test_distinguishes_two_of_two_from_forty_of_forty`:
codifica el fallo concreto del coseno que motivó todo el módulo.
"""

import numpy as np
import pytest

from botdetector.coordination import bipartite, similarity, validated


def test_distinguishes_two_of_two_from_forty_of_forty():
    """El fallo que hundió al coseno: ambos casos le daban 1,0.

    Dos cuentas que comparten sus únicas 2 publicaciones de un universo de 300
    no son sospechosas. Dos que comparten 40 de 40, sí. El coseno no puede
    separarlas; el p-valor hipergeométrico difiere en muchos órdenes de magnitud.
    """
    n_targets = 300

    p_weak = validated._pvalues(np.array([2]), np.array([2]), np.array([2]), n_targets)[0]
    p_strong = validated._pvalues(np.array([40]), np.array([40]), np.array([40]), n_targets)[0]

    assert p_weak > 1e-5
    assert p_strong < 1e-49
    # Cuarenta y tantos órdenes de magnitud separan lo que el coseno igualaba.
    assert p_strong < p_weak / 1e40


def test_cosine_cannot_distinguish_them():
    """Contraprueba explícita de por qué se cambió de estadístico."""
    weak = bipartite.build([("a", "p1"), ("a", "p2"), ("b", "p1"), ("b", "p2")])
    strong = bipartite.build([(actor, f"p{i}") for actor in ("a", "b") for i in range(40)])

    _, _, w = similarity.cosine_pairs(weak.matrix, floor=0.0, idf=False)
    _, _, s = similarity.cosine_pairs(strong.matrix, floor=0.0, idf=False)

    assert float(w[0]) == pytest.approx(1.0)
    assert float(s[0]) == pytest.approx(1.0)


def test_pvalue_shrinks_as_universe_grows():
    """La misma coincidencia es más sospechosa cuanto mayor el universo."""
    small = validated._pvalues(np.array([3]), np.array([3]), np.array([3]), 10)[0]
    large = validated._pvalues(np.array([3]), np.array([3]), np.array([3]), 1000)[0]
    assert large < small


class TestCooccurrence:
    def test_counts_shared_targets(self):
        bm = bipartite.build([("a", "p1"), ("a", "p2"), ("a", "p3"), ("b", "p1"), ("b", "p2")])
        src, dst, shared = validated.cooccurrence(bm.matrix, min_shared=1)
        assert list(shared) == [2]
        assert (bm.actors[src[0]], bm.actors[dst[0]]) == ("a", "b")

    def test_min_shared_prunes(self):
        bm = bipartite.build([("a", "p1"), ("b", "p1"), ("a", "p2")])
        _, _, shared = validated.cooccurrence(bm.matrix, min_shared=2)
        assert len(shared) == 0

    def test_upper_triangle_only(self):
        bm = bipartite.build([(a, "p1") for a in ("a", "b", "c")])
        src, dst, _ = validated.cooccurrence(bm.matrix, min_shared=1)
        assert np.all(src < dst)

    def test_empty_input(self):
        bm = bipartite.build([])
        src, dst, shared = validated.cooccurrence(bm.matrix)
        assert len(src) == len(dst) == len(shared) == 0


class TestCorrections:
    def test_bonferroni_scales_with_test_count(self):
        pvalues = np.array([1e-3] * 10)
        assert validated._bonferroni(pvalues, 0.05).sum() == 10
        assert validated._bonferroni(np.array([1e-3] * 1000), 0.05).sum() == 0

    def test_fdr_is_less_strict_than_bonferroni(self):
        pvalues = np.array([1e-4, 2e-4, 3e-4, 0.5, 0.9])
        assert validated._fdr(pvalues, 0.05).sum() >= validated._bonferroni(pvalues, 0.05).sum()

    def test_fdr_empty(self):
        assert len(validated._fdr(np.array([]), 0.05)) == 0


class TestCalibration:
    def test_calibrated_cutoff_is_a_probability(self):
        rng = np.random.default_rng(0)
        edges = [
            (f"a{i}", f"p{t}") for i in range(60) for t in rng.choice(80, size=6, replace=False)
        ]
        bm = bipartite.build(edges)
        cutoff = validated.calibrate_alpha(bm, n_iterations=5, seed=0)
        assert 0.0 <= cutoff <= 1.0

    def test_calibration_is_reproducible(self):
        rng = np.random.default_rng(1)
        edges = [
            (f"a{i}", f"p{t}") for i in range(40) for t in rng.choice(60, size=5, replace=False)
        ]
        bm = bipartite.build(edges)
        a = validated.calibrate_alpha(bm, n_iterations=4, seed=3)
        b = validated.calibrate_alpha(bm, n_iterations=4, seed=3)
        assert a == b

    def test_degenerate_inputs(self):
        assert validated.calibrate_alpha(bipartite.build([]), n_iterations=3) == 0.0
        graph = validated.validate(bipartite.build([]))
        assert graph.n_edges == 0


class TestScale:
    """Optimizaciones para cuentas grandes. Deben acelerar, no cambiar resultados."""

    def test_deduplicated_pvalues_match_the_direct_computation(self):
        rng = np.random.default_rng(0)
        n = validated._DEDUP_FROM + 1000
        k_i = rng.integers(2, 40, size=n)
        k_j = rng.integers(2, 40, size=n)
        shared = np.minimum(rng.integers(2, 20, size=n), np.minimum(k_i, k_j))

        deduped = validated._pvalues(shared, k_i, k_j, 300)
        direct = validated.hypergeom.sf(shared - 1, 300, k_i, k_j)

        np.testing.assert_allclose(deduped, direct, rtol=1e-12)

    def test_pvalue_is_symmetric_in_the_two_accounts(self):
        """La deduplicación explota esta simetría; si no se cumpliera, rompería."""
        a = validated._pvalues(np.array([3]), np.array([5]), np.array([9]), 100)
        b = validated._pvalues(np.array([3]), np.array([9]), np.array([5]), 100)
        assert a[0] == pytest.approx(b[0])

    def test_iterations_shrink_as_the_projection_densifies(self):
        """Misma cantidad de contrastes nulos, mucho menos cómputo."""
        sparse = validated._adaptive_iterations(40, n_pairs=10_000)
        dense = validated._adaptive_iterations(40, n_pairs=9_400_000)

        assert sparse == 40
        assert dense < sparse
        assert dense >= 5  # nunca menos de cinco muestras

    def test_iterations_never_exceed_the_request(self):
        assert validated._adaptive_iterations(10, n_pairs=1) == 10
        assert validated._adaptive_iterations(40, n_pairs=0) == 40


def test_validate_rejects_unknown_correction():
    bm = bipartite.build([("a", "p1"), ("a", "p2"), ("b", "p1"), ("b", "p2")])
    with pytest.raises(ValueError, match="corrección"):
        validated.validate(bm, correction="inventada")
