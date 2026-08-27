"""Construcción de la matriz bipartita actor x objetivo.

Siguiendo a Jahn & Rendsvig (arXiv:2305.07384), el punto de partida es
deliberadamente minimalista: **solo la matriz binaria de quién interactuó con
qué**. Sin contenido, sin metadatos, sin modelos de lenguaje.

Esa austeridad es una decisión de diseño, no una limitación: un resultado que se
deriva únicamente de "estas 1.800 cuentas amplificaron exactamente los mismos
340 mensajes" es mucho más difícil de refutar —y mucho más difícil de acusar de
sesgo ideológico— que uno que dependa de clasificar texto.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import scipy.sparse as sp


@dataclass(frozen=True)
class BipartiteMatrix:
    """Matriz binaria actor x objetivo, con sus índices."""

    matrix: sp.csr_matrix
    actors: list[str]
    targets: list[str]

    @property
    def n_actors(self) -> int:
        return len(self.actors)

    @property
    def n_targets(self) -> int:
        return len(self.targets)

    @property
    def n_edges(self) -> int:
        return int(self.matrix.nnz)

    def actor_degrees(self) -> np.ndarray:
        """Número de objetivos distintos que amplificó cada actor."""
        return np.asarray(self.matrix.sum(axis=1)).ravel()

    def target_degrees(self) -> np.ndarray:
        """Número de actores distintos que amplificaron cada objetivo."""
        return np.asarray(self.matrix.sum(axis=0)).ravel()


def build(edges: list[tuple[str, str]]) -> BipartiteMatrix:
    """Construye la matriz a partir de aristas (actor_id, target_id).

    Las aristas duplicadas colapsan a 1: nos interesa *si* un actor amplificó un
    mensaje, no cuántas veces. Contar repeticiones daría un peso desproporcionado
    a las cuentas más activas, que es exactamente el sesgo que queremos evitar.
    """
    if not edges:
        return BipartiteMatrix(sp.csr_matrix((0, 0), dtype=np.float32), [], [])

    actors = sorted({a for a, _ in edges})
    targets = sorted({t for _, t in edges})
    a_idx = {a: i for i, a in enumerate(actors)}
    t_idx = {t: i for i, t in enumerate(targets)}

    rows = np.fromiter((a_idx[a] for a, _ in edges), dtype=np.int32, count=len(edges))
    cols = np.fromiter((t_idx[t] for _, t in edges), dtype=np.int32, count=len(edges))
    data = np.ones(len(edges), dtype=np.float32)

    m = sp.coo_matrix(
        (data, (rows, cols)), shape=(len(actors), len(targets)), dtype=np.float32
    ).tocsr()
    m.data[:] = 1.0  # colapsa duplicados sumados por coo_matrix
    m.eliminate_zeros()

    return BipartiteMatrix(m, actors, targets)


def randomize(m: BipartiteMatrix, rng: np.random.Generator) -> sp.csr_matrix:
    """Modelo nulo: permuta las aristas preservando ambas secuencias de grado.

    Permutar la columna de objetivos del listado de aristas conserva de forma
    exacta tanto el grado de cada actor como el de cada objetivo. Es decir: el
    grafo aleatorio tiene actores igual de activos y mensajes igual de populares
    que el real, y lo único que se destruye es *con quién coincide cada uno*.

    Por eso el umbral derivado de este nulo responde a la pregunta correcta: no
    "¿esta cuenta es muy activa?" —lo cual no prueba nada— sino "¿este nivel de
    solapamiento es esperable en cuentas así de activas por puro azar?".

    Nota: la permutación puede generar aristas repetidas, que colapsan a 1. Esto
    reduce ligeramente la densidad del grafo nulo y hace el umbral algo
    conservador, lo cual es el sentido correcto del error para esta herramienta.
    """
    coo = m.matrix.tocoo()
    shuffled_cols = rng.permutation(coo.col)
    out = sp.coo_matrix(
        (np.ones(len(coo.row), dtype=np.float32), (coo.row, shuffled_cols)),
        shape=m.matrix.shape,
        dtype=np.float32,
    ).tocsr()
    out.data[:] = 1.0
    out.eliminate_zeros()
    return out
