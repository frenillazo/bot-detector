import numpy as np
import pytest

from botdetector.coordination import bipartite, similarity


def test_cosine_matches_hand_computation():
    # a y b comparten p1 y p2 de tres; c no comparte nada con ellos.
    # Sin IDF, para poder comprobar el coseno binario a mano.
    bm = bipartite.build(
        [
            ("a", "p1"),
            ("a", "p2"),
            ("a", "p3"),
            ("b", "p1"),
            ("b", "p2"),
            ("b", "p4"),
            ("c", "p5"),
            ("c", "p6"),
            ("c", "p7"),
        ]
    )
    src, dst, val = similarity.cosine_pairs(bm.matrix, floor=0.0, idf=False)
    pairs = {(bm.actors[i], bm.actors[j]): float(v) for i, j, v in zip(src, dst, val, strict=True)}

    # 2 compartidos / sqrt(3*3) = 0.666...
    assert pairs[("a", "b")] == pytest.approx(2 / 3, rel=1e-5)
    assert pairs.get(("a", "c"), 0.0) == 0.0


def test_idf_discounts_coincidence_on_viral_content():
    """Coincidir solo en lo viral debe puntuar mucho menos que coincidir en lo oscuro.

    Es la propiedad que evita señalar como granja a dos cuentas orgánicas poco
    activas que únicamente tocaron los mensajes más populares.
    """
    viral = [(f"crowd{i}", "viral") for i in range(50)]
    edges = [
        *viral,
        ("x", "viral"),
        ("x", "raro1"),
        ("y", "viral"),
        ("y", "raro1"),
    ]
    bm = bipartite.build(edges)

    def sim(idf: bool) -> float:
        src, dst, val = similarity.cosine_pairs(bm.matrix, floor=0.0, idf=idf)
        lookup = {
            (bm.actors[i], bm.actors[j]): float(v) for i, j, v in zip(src, dst, val, strict=True)
        }
        return lookup[("x", "y")]

    # x e y coinciden en ambos mensajes, pero el peso se desplaza hacia el raro.
    assert sim(idf=True) == pytest.approx(1.0, rel=1e-5)

    def crowd_sim(idf: bool) -> float:
        src, dst, val = similarity.cosine_pairs(bm.matrix, floor=0.0, idf=idf)
        lookup = {
            (bm.actors[i], bm.actors[j]): float(v) for i, j, v in zip(src, dst, val, strict=True)
        }
        return lookup[("crowd0", "x")]

    # crowd0 solo comparte lo viral con x: con IDF ese vínculo se debilita.
    assert crowd_sim(idf=True) < crowd_sim(idf=False)


def test_cosine_upper_triangle_only():
    bm = bipartite.build([("a", "p1"), ("b", "p1"), ("c", "p1")])
    src, dst, _ = similarity.cosine_pairs(bm.matrix, floor=0.0)
    assert np.all(src < dst)
    assert len(src) == 3  # 3 pares, no 6


def test_chunking_does_not_change_result():
    """El troceado es una optimización de memoria: no puede alterar el resultado."""
    audience = _audience()
    bm = bipartite.build(audience)

    full = similarity.cosine_pairs(bm.matrix, floor=0.2, chunk=10_000)
    chunked = similarity.cosine_pairs(bm.matrix, floor=0.2, chunk=7)

    for a, b in zip(full, chunked, strict=True):
        np.testing.assert_allclose(np.sort(a), np.sort(b), rtol=1e-6)


def test_null_threshold_is_below_one_and_positive():
    bm = bipartite.build(_audience())
    t = similarity.null_threshold(bm, n_iterations=5, seed=0)
    assert 0.0 < t <= 1.0


def test_null_threshold_rises_with_denser_overlap():
    """Si el azar ya produce mucho solapamiento, el listón debe subir."""
    sparse = bipartite.build([(f"a{i}", f"p{i * 3 + j}") for i in range(60) for j in range(3)])
    dense = bipartite.build([(f"a{i}", f"p{j}") for i in range(60) for j in range(10)])

    t_sparse = similarity.null_threshold(sparse, n_iterations=5, floor=0.0, seed=0)
    t_dense = similarity.null_threshold(dense, n_iterations=5, floor=0.0, seed=0)
    assert t_dense > t_sparse


def test_build_graph_respects_explicit_threshold():
    bm = bipartite.build(_audience())
    g = similarity.build_graph(bm, threshold=0.95, floor=0.1)
    assert g.threshold == 0.95
    assert np.all(g.weight >= 0.95)


def _audience() -> list[tuple[str, str]]:
    rng = np.random.default_rng(0)
    edges = []
    for i in range(50):
        for t in rng.choice(40, size=6, replace=False):
            edges.append((f"a{i}", f"p{t}"))
    return edges
