"""Validación estadística de enlaces por test hipergeométrico.

Sustituye al par coseno + umbral por permutación. El motivo es un fallo concreto
y medido del coseno, no una preferencia estética:

> **El coseno no distingue "2 de 2 compartidos" de "40 de 40 compartidos".
> Ambos valen 1,0.**

Con datos completos eso rara vez importa, porque las cuentas tienen grados altos.
Con observación parcial se vuelve letal. En la validación de `docs/CURVAS.md`,
observando solo el 20% de las publicaciones, 27 cuentas orgánicas con grado
observado **exactamente 2** coincidieron en los mismos 2 posts de 25 y salieron
con similitud 1,000. El detector las marcó como granja. Eran personas.

El test hipergeométrico hace la pregunta correcta: dadas dos cuentas que
amplificaron k_i y k_j publicaciones de un universo de N, ¿qué probabilidad hay
de que compartieran al menos c por azar?

    p = P(X >= c),  X ~ Hipergeométrica(N, k_i, k_j)

Para el caso de arriba —k_i = k_j = 2, N = 25, c = 2— sale p ≈ 3,3e-3, que no
sobrevive a ninguna corrección razonable. Para una granja real —40 de 40 sobre
300 publicaciones— sale p ≈ 1e-50. Cuarenta y tantos órdenes de magnitud separan
lo que el coseno igualaba a 1,0.

El umbral **no** se fija con Bonferroni. El modelo hipergeométrico asume que cada
cuenta elige publicaciones equiprobablemente, cosa falsa en cualquier audiencia
real, y esa mala especificación vuelve los p-valores anticonservadores: con
Bonferroni salían falsos positivos en 25 de 30 audiencias orgánicas. El umbral se
calibra por permutación (`calibrate_alpha`), que reproduce la concentración de
popularidad real sin modelarla, y la calibración se aplica en dos niveles: arista
y cluster. Ver `calibrate_alpha` y `null_evidence_threshold`.

Referencias:
- Tumminello, Miccichè, Lillo, Piilo & Mantegna, "Statistically Validated
  Networks in Bipartite Complex Systems", PLOS ONE 6(3), 2011.
- Westfall & Young, corrección max-T por permutación para contrastes múltiples
  con dependencia.
"""

from __future__ import annotations

import numpy as np
import scipy.sparse as sp
from scipy.stats import hypergeom

from botdetector.coordination.bipartite import BipartiteMatrix, randomize
from botdetector.coordination.similarity import SimilarityGraph

_CHUNK = 2048


def cooccurrence(
    m: sp.csr_matrix, *, min_shared: int = 2, chunk: int = _CHUNK
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Pares (i, j), i < j, con al menos `min_shared` objetivos en común.

    Devuelve recuentos crudos, no similitudes: el test hipergeométrico opera
    sobre el número de coincidencias, no sobre una razón normalizada. Ahí está
    justamente la información que el coseno tira.

    `min_shared=2` por defecto porque una única coincidencia nunca es evidencia
    de nada y descartarla de entrada ahorra la mayor parte del cómputo.
    """
    n = m.shape[0]
    if n < 2:
        empty = np.empty(0, dtype=np.int32)
        return empty, empty.copy(), empty.copy()

    binary = m.copy()
    binary.data[:] = 1.0
    mt = binary.T.tocsc()

    src: list[np.ndarray] = []
    dst: list[np.ndarray] = []
    cnt: list[np.ndarray] = []

    for start in range(0, n, chunk):
        stop = min(start + chunk, n)
        block = (binary[start:stop] @ mt).tocoo()

        rows = block.row + start
        cols = block.col
        keep = (rows < cols) & (block.data >= min_shared)
        if not keep.any():
            continue

        src.append(rows[keep].astype(np.int32))
        dst.append(cols[keep].astype(np.int32))
        cnt.append(block.data[keep].astype(np.int32))

    if not cnt:
        empty = np.empty(0, dtype=np.int32)
        return empty, empty.copy(), empty.copy()

    return np.concatenate(src), np.concatenate(dst), np.concatenate(cnt)


def _bonferroni(pvalues: np.ndarray, alpha: float) -> np.ndarray:
    """Controla la probabilidad de **cualquier** falso enlace en toda la red."""
    n_tests = max(len(pvalues), 1)
    return pvalues <= alpha / n_tests


def _fdr(pvalues: np.ndarray, alpha: float) -> np.ndarray:
    """Benjamini-Hochberg: controla la proporción esperada de falsos enlaces.

    Menos conservador que Bonferroni. Para esta herramienta el criterio por
    defecto sigue siendo Bonferroni: preferimos perder una campaña a inventarla.
    """
    n = len(pvalues)
    if n == 0:
        return np.zeros(0, dtype=bool)

    order = np.argsort(pvalues)
    ranked = pvalues[order]
    thresholds = alpha * np.arange(1, n + 1) / n
    passing = np.nonzero(ranked <= thresholds)[0]

    keep = np.zeros(n, dtype=bool)
    if len(passing):
        keep[order[: passing[-1] + 1]] = True
    return keep


_DEDUP_FROM = 50_000


def _pvalues(shared: np.ndarray, k_i: np.ndarray, k_j: np.ndarray, n_targets: int) -> np.ndarray:
    """P(X >= c) bajo Hipergeométrica(n_targets, k_i, k_j), vectorizado.

    Con audiencias grandes la proyección se vuelve densa: 3.000 cuentas sobre 60
    publicaciones generan 9,4 millones de pares, y evaluar la hipergeométrica en
    cada uno dominaba el coste total (107 s por detección, medido).

    Pero el p-valor depende **solo** de la terna (c, k_i, k_j), y el test es
    simétrico en las dos cuentas. Con pocas publicaciones hay muy pocas ternas
    distintas: se calcula una vez por terna y se reparte. La ganancia crece justo
    donde hace falta, porque cuanto más densa la proyección, mayor la proporción
    de ternas repetidas.
    """
    if len(shared) < _DEDUP_FROM:
        return hypergeom.sf(shared - 1, n_targets, k_i, k_j)

    lo = np.minimum(k_i, k_j).astype(np.int64)
    hi = np.maximum(k_i, k_j).astype(np.int64)
    base = np.int64(max(int(hi.max()), int(shared.max())) + 1)

    key = (shared.astype(np.int64) * base + lo) * base + hi
    unique_keys, inverse = np.unique(key, return_inverse=True)

    u_hi = unique_keys % base
    u_lo = (unique_keys // base) % base
    u_shared = unique_keys // (base * base)

    return hypergeom.sf(u_shared - 1, n_targets, u_lo, u_hi)[inverse]


def _adaptive_iterations(requested: int, n_pairs: int, budget: int = 20_000_000) -> int:
    """Permutaciones necesarias según el tamaño de la proyección.

    La calidad del umbral max-T depende del número total de contrastes nulos
    observados, que es `permutaciones x pares`. En una audiencia pequeña hacen
    falta muchas permutaciones para acumular suficientes; en una densa, una sola
    ya aporta millones.

    Mantener 40 permutaciones fijas en una proyección de 9,4 millones de pares es
    gastar cien veces el cómputo necesario para el mismo rigor. Se fija un
    presupuesto de contrastes y se deriva el número de permutaciones, con un
    suelo de 5 para que la estimación nunca dependa de un puñado de muestras.
    """
    if n_pairs <= 0:
        return requested
    return int(np.clip(budget // n_pairs, 5, requested))


def calibrate_alpha(
    bm: BipartiteMatrix,
    *,
    n_iterations: int = 10,
    min_shared: int = 2,
    seed: int = 0,
) -> float:
    """Umbral de p-valor calibrado por permutación (corrección max-T).

    Resuelve dos problemas a la vez, y por eso sustituye a Bonferroni.

    **1. El modelo hipergeométrico está mal especificado.** Asume que cada cuenta
    elige sus publicaciones uniformemente al azar entre las N disponibles. Falso:
    la popularidad sigue una ley de potencias. En la validación, publicaciones
    con grado 234 sobre 250 cuentas —lo que tocó casi todo el mundo— generaban
    coincidencias que el modelo uniforme declaraba imposibles. Resultado: falsos
    positivos en 25 de 30 audiencias puramente orgánicas.

    Un modelo analítico de popularidad tampoco sirve, porque la propia campaña
    infla el grado de sus objetivos: se estimaría el nulo con datos que contienen
    la señal, y el nulo declararía esperable justo lo que se busca.

    La permutación preserva **ambas** secuencias de grado, así que reproduce la
    concentración de popularidad real sin necesidad de modelarla.

    **2. Comparaciones múltiples con dependencia.** Los p-valores de pares que
    comparten una cuenta no son independientes, y Bonferroni supone que sí.
    Tomar el mínimo p-valor que produce cada permutación es la corrección max-T
    de Westfall-Young, que controla la tasa de error por familia respetando la
    estructura de dependencia real.

    Devuelve el menor p-valor observado bajo permutación: un par real solo se
    valida si es **más improbable que cualquier cosa que produzca el azar**.
    """
    if bm.n_actors < 2 or bm.n_edges == 0:
        return 0.0

    rng = np.random.default_rng(seed)
    best = 1.0
    budget = n_iterations

    for it in range(n_iterations):
        if it >= budget:
            break

        randomized = randomize(bm, rng)
        src, dst, shared = cooccurrence(randomized, min_shared=min_shared)
        if len(shared) == 0:
            continue

        # La primera permutación revela cuán densa es la proyección, y con ella
        # cuántas permutaciones más hacen falta para el mismo rigor.
        if it == 0:
            budget = _adaptive_iterations(n_iterations, len(shared))

        degrees = np.asarray(randomized.sum(axis=1)).ravel()
        pvals = _pvalues(shared, degrees[src], degrees[dst], bm.n_targets)
        if len(pvals):
            best = min(best, float(pvals.min()))

    return best


def null_evidence_threshold(
    bm: BipartiteMatrix,
    *,
    cutoff: float,
    min_shared: int = 2,
    n_iterations: int = 10,
    resolution: float = 1.0,
    seed: int = 0,
    safety_factor: float = 1.0,
) -> float:
    """Masa de evidencia que el azar alcanza, pasando el nulo por TODO el motor.

    Validar aristas no basta. La validación controla el error **por arista**,
    pero un puñado de aristas fortuitas todavía se ensambla en clusters de tres a
    cinco cuentas con aspecto de campaña: sin esta segunda capa, el criterio
    hipergeométrico calibrado producía falsos positivos en 9 de 30 audiencias
    puramente orgánicas.

    Aquí se aleatoriza la matriz, se le aplica **el mismo umbral de validación**
    y **el mismo clustering** que a los datos reales, y se mide qué masa de
    evidencia llega a producir. Un cluster real debe superarla.

    Es la misma estructura de dos niveles que ya funcionaba con el método por
    permutación; lo que cambia es el criterio de arista, no la arquitectura.
    """
    from botdetector.coordination import clustering

    if bm.n_actors < 2 or bm.n_edges == 0:
        return float("inf")

    rng = np.random.default_rng(seed + 1)
    best = 0.0
    budget = n_iterations

    for it in range(n_iterations):
        if it >= budget:
            break

        randomized = randomize(bm, rng)
        src, dst, shared = cooccurrence(randomized, min_shared=min_shared)
        if len(shared) == 0:
            continue
        if it == 0:
            budget = _adaptive_iterations(n_iterations, len(shared))

        degrees = np.asarray(randomized.sum(axis=1)).ravel()
        pvals = _pvalues(shared, degrees[src], degrees[dst], bm.n_targets)
        keep = pvals < cutoff
        if not keep.any():
            continue

        weights = shared[keep] / np.sqrt(degrees[src][keep] * degrees[dst][keep])
        null_graph = SimilarityGraph(
            source=src[keep],
            dest=dst[keep],
            weight=weights.astype(np.float32),
            threshold=cutoff,
            n_actors=bm.n_actors,
        )
        result = clustering.detect(null_graph, resolution=resolution, seed=it)
        best = max(best, max((c.evidence for c in result.clusters), default=0.0))

    return best * safety_factor


def expected_shared(
    k_i: np.ndarray, k_j: np.ndarray, target_degrees: np.ndarray, n_edges: int
) -> np.ndarray:
    """Coincidencias esperadas por azar, **teniendo en cuenta la popularidad**.

    El test hipergeométrico puro asume que cada cuenta elige sus publicaciones
    uniformemente al azar entre las N disponibles. Es falso en cualquier
    audiencia real: la popularidad sigue una ley de potencias y todo el mundo se
    amontona en lo mismo. Coincidir en el post viral del día no es sorprendente,
    pero el modelo uniforme cree que sí, y marca a personas por ello.

    Medido: con datos completos sobre audiencias 100% orgánicas, el
    hipergeométrico puro produjo falsos positivos en 25 de 30 ejecuciones.

    Bajo un modelo de configuración bipartito, la probabilidad de que la cuenta
    i toque la publicación t es p_it ≈ k_i·d_t/M. Las coincidencias esperadas
    del par (i, j) son entonces:

        λ_ij = Σ_t p_it·p_jt = (k_i·k_j/M²)·Σ_t d_t²

    El sumatorio Σ_t d_t² es una **constante global**: se calcula una vez y el
    coste por par sigue siendo O(1).

    Comprobación de coherencia: si todas las publicaciones tuvieran la misma
    popularidad d_t = M/N, entonces Σ_t d_t² = M²/N y λ_ij = k_i·k_j/N, que es
    exactamente la media de la hipergeométrica. La corrección generaliza el test
    anterior en vez de sustituirlo por otra cosa.
    """
    if n_edges == 0:
        return np.zeros(len(k_i), dtype=np.float64)
    concentration = float(np.square(target_degrees.astype(np.float64)).sum())
    return k_i.astype(np.float64) * k_j.astype(np.float64) * concentration / (n_edges**2)


def validate(
    bm: BipartiteMatrix,
    *,
    alpha: float = 0.01,
    correction: str = "permutation",
    min_shared: int = 2,
    n_iterations: int = 10,
    seed: int = 0,
    cutoff: float | None = None,
) -> SimilarityGraph:
    """Red de coordinación validada estadísticamente.

    La *pertenencia* de un enlace la decide el test hipergeométrico corregido;
    el *peso* del enlace es el coseno, que sigue describiendo bien la intensidad
    de la sincronía una vez que ya sabemos que no es azar.

    `threshold` guarda el alfa efectivo tras la corrección, para que quede
    registrado en el informe qué listón se aplicó.
    """
    if bm.n_actors < 2 or bm.n_targets < 1:
        empty_i = np.empty(0, dtype=np.int32)
        return SimilarityGraph(
            source=empty_i,
            dest=empty_i.copy(),
            weight=np.empty(0, dtype=np.float32),
            threshold=alpha,
            n_actors=bm.n_actors,
        )

    src, dst, shared = cooccurrence(bm.matrix, min_shared=min_shared)
    if len(shared) == 0:
        empty_i = np.empty(0, dtype=np.int32)
        return SimilarityGraph(
            source=empty_i,
            dest=empty_i.copy(),
            weight=np.empty(0, dtype=np.float32),
            threshold=alpha,
            n_actors=bm.n_actors,
        )

    degrees = bm.actor_degrees()
    k_i = degrees[src]
    k_j = degrees[dst]
    pvalues = _pvalues(shared, k_i, k_j, bm.n_targets)

    if correction == "permutation":
        if cutoff is None:
            cutoff = calibrate_alpha(
                bm, n_iterations=n_iterations, min_shared=min_shared, seed=seed
            )
        keep = pvalues < cutoff
    elif correction == "bonferroni":
        cutoff = alpha / max(len(pvalues), 1)
        keep = _bonferroni(pvalues, alpha)
    elif correction == "fdr":
        cutoff = alpha
        keep = _fdr(pvalues, alpha)
    else:
        raise ValueError(f"corrección desconocida: {correction!r}")

    if not keep.any():
        empty_i = np.empty(0, dtype=np.int32)
        return SimilarityGraph(
            source=empty_i,
            dest=empty_i.copy(),
            weight=np.empty(0, dtype=np.float32),
            threshold=float(cutoff),
            n_actors=bm.n_actors,
        )

    cosine = shared[keep] / np.sqrt(k_i[keep] * k_j[keep])

    return SimilarityGraph(
        source=src[keep],
        dest=dst[keep],
        weight=cosine.astype(np.float32),
        threshold=float(cutoff),
        n_actors=bm.n_actors,
    )
