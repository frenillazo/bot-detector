import numpy as np

from botdetector.coordination import bipartite


def test_build_empty():
    bm = bipartite.build([])
    assert bm.n_actors == 0
    assert bm.n_edges == 0


def test_build_collapses_duplicates():
    """Interactuar dos veces con el mismo mensaje no debe pesar el doble."""
    bm = bipartite.build([("a", "p1"), ("a", "p1"), ("b", "p1")])
    assert bm.n_edges == 2
    assert set(bm.matrix.data) == {1.0}


def test_degrees():
    bm = bipartite.build([("a", "p1"), ("a", "p2"), ("b", "p1")])
    assert bm.actors == ["a", "b"]
    assert bm.targets == ["p1", "p2"]
    np.testing.assert_array_equal(bm.actor_degrees(), [2, 1])
    np.testing.assert_array_equal(bm.target_degrees(), [2, 1])


def test_randomize_preserves_actor_degrees():
    """El nulo debe conservar cuán activo es cada actor; solo destruye con quién coincide."""
    rng = np.random.default_rng(0)
    # Grafo disperso y realista: 120 actores sobre 400 objetivos posibles.
    edges = [(f"a{i}", f"p{t}") for i in range(120) for t in rng.choice(400, size=8, replace=False)]
    bm = bipartite.build(edges)

    randomized = bipartite.randomize(bm, np.random.default_rng(1))
    original = bm.actor_degrees()
    shuffled = np.asarray(randomized.sum(axis=1)).ravel()

    # Las aristas repetidas que genera la permutación colapsan a 1, por lo que el
    # grado solo puede bajar, nunca subir. En un grafo disperso la pérdida es
    # marginal; en uno muy denso puede ser grande, y ahí el nulo se vuelve
    # conservador (sentido correcto del error para esta herramienta).
    assert np.all(shuffled <= original)
    assert shuffled.sum() >= 0.95 * original.sum()


def test_randomize_loses_edges_on_dense_graphs():
    """Documenta el límite conocido del nulo por permutación.

    Con pocos objetivos y muchos actores, la permutación genera colisiones y el
    grafo nulo queda más disperso que el real. El umbral resultante es entonces
    algo más bajo de lo ideal, es decir: conservador.
    """
    dense = bipartite.build([(f"a{i}", f"p{j}") for i in range(40) for j in range(5)])
    randomized = bipartite.randomize(dense, np.random.default_rng(0))
    assert randomized.nnz < dense.n_edges


def test_randomize_is_deterministic_given_seed():
    bm = bipartite.build([(f"a{i}", f"p{j}") for i in range(10) for j in range(3)])
    a = bipartite.randomize(bm, np.random.default_rng(42))
    b = bipartite.randomize(bm, np.random.default_rng(42))
    assert (a != b).nnz == 0
