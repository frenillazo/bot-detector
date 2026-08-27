"""Similitud de coengagement y umbral derivado de un modelo nulo.

El error más común al construir redes de coordinación es fijar el umbral de
similitud a ojo (0,5; 0,8; el percentil 99...). Ese número arbitrario es
justamente por donde se ataca un informe: "¿por qué 0,8 y no 0,9?".

Aquí el umbral **se deriva de los datos**: se aleatoriza el grafo preservando los
grados, se mide qué similitudes aparecen por puro azar, y se toma un cuantil alto
de esa distribución nula. El umbral resultante significa algo concreto y decible
en voz alta: "solo el 0,1% de los pares de cuentas alcanzaría este solapamiento
por casualidad".
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import scipy.sparse as sp

from botdetector.coordination.bipartite import BipartiteMatrix, randomize

_CHUNK = 2048


@dataclass(frozen=True)
class SimilarityGraph:
    """Grafo de similitud entre actores, ya filtrado por umbral."""

    source: np.ndarray
    dest: np.ndarray
    weight: np.ndarray
    threshold: float
    n_actors: int

    @property
    def n_edges(self) -> int:
        return len(self.weight)

    def __len__(self) -> int:
        return self.n_edges


def _l2_normalize(m: sp.csr_matrix) -> sp.csr_matrix:
    norms = np.sqrt(np.asarray(m.multiply(m).sum(axis=1)).ravel())
    norms[norms == 0] = 1.0
    return sp.diags(1.0 / norms).dot(m).tocsr()


def _idf(m: sp.csr_matrix) -> np.ndarray:
    """Peso informativo de cada objetivo: log(1 + n_actores / n_que_lo_amplificaron).

    Coincidir en un mensaje viral no es evidencia de nada: lo amplificó medio
    país. Coincidir en uno oscuro sí lo es. Sin esta ponderación, dos cuentas
    orgánicas poco activas que solo tocaron los mensajes más populares salen con
    similitud 1,0 y acaban señaladas como granja.

    Este no es un ajuste cosmético: en la audiencia sintética puramente orgánica
    de `tests/test_detection.py`, su ausencia producía falsos positivos.
    """
    n_actors = m.shape[0]
    df = np.maximum(np.asarray(m.sum(axis=0)).ravel(), 1.0)
    return np.log1p(n_actors / df).astype(np.float32)


def cosine_pairs(
    m: sp.csr_matrix, *, floor: float = 0.1, chunk: int = _CHUNK, idf: bool = True
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Pares (i, j) con i < j y similitud coseno >= `floor`.

    Con `idf=True` (por defecto) cada objetivo se pondera por su rareza antes de
    normalizar, de modo que la similitud mide coincidencia *informativa* y no
    mero solapamiento en lo viral.

    Se calcula por bloques de filas y se poda dentro del bucle. Sin la poda, el
    producto completo es O(n^2) en memoria y revienta con cualquier corpus real.
    """
    n = m.shape[0]
    if n < 2:
        empty_i = np.empty(0, dtype=np.int32)
        return empty_i, empty_i.copy(), np.empty(0, dtype=np.float32)

    weighted = m.multiply(_idf(m)).tocsr() if idf else m
    x = _l2_normalize(weighted)
    xt = x.T.tocsc()

    src: list[np.ndarray] = []
    dst: list[np.ndarray] = []
    val: list[np.ndarray] = []

    for start in range(0, n, chunk):
        stop = min(start + chunk, n)
        block = (x[start:stop] @ xt).tocoo()

        rows = block.row + start
        cols = block.col
        keep = (rows < cols) & (block.data >= floor)
        if not keep.any():
            continue

        src.append(rows[keep].astype(np.int32))
        dst.append(cols[keep].astype(np.int32))
        val.append(block.data[keep].astype(np.float32))

    if not val:
        empty_i = np.empty(0, dtype=np.int32)
        return empty_i, empty_i.copy(), np.empty(0, dtype=np.float32)

    return np.concatenate(src), np.concatenate(dst), np.concatenate(val)


def null_threshold(
    bm: BipartiteMatrix,
    *,
    quantile: float = 0.999,
    n_iterations: int = 20,
    floor: float = 0.1,
    seed: int = 0,
    idf: bool = True,
) -> float:
    """Umbral de similitud estimado sobre grafos aleatorizados.

    Devuelve el cuantil `quantile` de las similitudes observadas bajo el modelo
    nulo. Un par real que supere este valor es, por construcción, más sincronizado
    que el `quantile` de lo que produce el azar con esos mismos niveles de
    actividad.

    La ponderación IDF debe ser la misma en el nulo que en los datos reales; de
    lo contrario se comparan dos escalas distintas y el umbral no significa nada.
    """
    if bm.n_actors < 2:
        return 1.0

    rng = np.random.default_rng(seed)
    samples: list[np.ndarray] = []

    for _ in range(n_iterations):
        _, _, vals = cosine_pairs(randomize(bm, rng), floor=floor, idf=idf)
        if len(vals):
            samples.append(vals)

    if not samples:
        # Ningún par aleatorio alcanzó siquiera `floor`: cualquier coincidencia
        # real por encima de ese suelo ya es anómala.
        return float(floor)

    return float(np.quantile(np.concatenate(samples), quantile))


def build_graph(
    bm: BipartiteMatrix,
    *,
    quantile: float = 0.999,
    n_iterations: int = 20,
    floor: float = 0.1,
    seed: int = 0,
    idf: bool = True,
    threshold: float | None = None,
) -> SimilarityGraph:
    """Grafo de coordinación: pares reales por encima del umbral nulo.

    Si se pasa `threshold` explícito se omite la estimación del nulo. Úsalo solo
    para reproducir un análisis anterior, nunca para "ajustar" un resultado.
    """
    if threshold is None:
        threshold = null_threshold(
            bm,
            quantile=quantile,
            n_iterations=n_iterations,
            floor=floor,
            seed=seed,
            idf=idf,
        )

    src, dst, val = cosine_pairs(bm.matrix, floor=max(floor, threshold), idf=idf)
    keep = val >= threshold

    return SimilarityGraph(
        source=src[keep],
        dest=dst[keep],
        weight=val[keep],
        threshold=float(threshold),
        n_actors=bm.n_actors,
    )
