"""Detección de comunidades sobre el grafo de coordinación, y su calibración.

Se usa Leiden en lugar de Louvain porque Louvain produce con cierta frecuencia
comunidades internamente desconectadas, un artefacto que aquí sería grave: un
cluster desconectado equivale a agrupar cuentas que no comparten ninguna
evidencia de sincronía entre sí.

El estadístico que decide qué cluster se marca no es el tamaño ni la densidad,
sino la **masa de evidencia**: la suma de los pesos de las aristas internas. La
razón está en `null_evidence_threshold`.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from botdetector.coordination.bipartite import BipartiteMatrix, randomize
from botdetector.coordination.similarity import SimilarityGraph, cosine_pairs

SAFETY_FACTOR = 10.0
"""Cuánto debe superar un cluster real a la estructura más fuerte del azar.

Es una elección deliberadamente conservadora, no una constante ajustada para que
cuadren los tests: sesga el error hacia el falso negativo, que es la dirección
correcta cuando el resultado puede acabar señalando a personas. Ver ETHICS.md.
"""

MIN_DENSITY = 0.5
"""Fracción mínima de pares internos que deben ser anómalos.

Criterio sustantivo, no umbral de conveniencia: un grupo coordinado *actúa
junto*, de modo que la mayoría de sus parejas internas deberían mostrar sincronía
inverosímil. Si menos de la mitad la muestra, lo que hay es una comunidad
temática —gente que comparte intereses— y no una campaña.

Sin este criterio, una comunidad orgánica grande y laxa acumula masa de evidencia
suficiente para ser marcada solo en virtud de su tamaño: en validación sintética,
un grupo de 26 cuentas con densidad 0,24 pasaba el filtro de evidencia.
"""


@dataclass(frozen=True)
class Cluster:
    """Grupo de actores con sincronía mutua inverosímil."""

    cluster_id: int
    actor_indices: list[int]
    internal_edges: int
    internal_weight: float

    @property
    def size(self) -> int:
        return len(self.actor_indices)

    @property
    def density(self) -> float:
        """Fracción de los pares internos posibles que superan el umbral."""
        n = self.size
        if n < 2:
            return 0.0
        return self.internal_edges / (n * (n - 1) / 2)

    @property
    def mean_weight(self) -> float:
        if self.internal_edges == 0:
            return 0.0
        return self.internal_weight / self.internal_edges

    @property
    def coordination_score(self) -> float:
        """Densidad ponderada por similitud media, en [0, 1]. Solo para informar.

        Un cluster grande y disperso puntúa bajo; uno pequeño de sincronía casi
        perfecta puntúa alto. Es útil para describir un cluster, pero NO sirve
        para decidir si marcarlo: cuatro cuentas orgánicas que coinciden por azar
        alcanzan 1,0 igual que una granja.
        """
        return float(self.density * self.mean_weight)

    @property
    def evidence(self) -> float:
        """Masa total de evidencia: suma de pesos de las aristas internas.

        Este es el estadístico que decide. Crece cuadráticamente con el tamaño
        del grupo y linealmente con la fuerza de la sincronía, de modo que separa
        una granja de 30 cuentas (~435 pares anómalos) de un coágulo fortuito de
        9 (~18) por dos órdenes de magnitud.
        """
        return self.internal_weight


@dataclass(frozen=True)
class ClusterResult:
    clusters: list[Cluster]
    actor_to_cluster: dict[int, int]

    @property
    def n_clustered_actors(self) -> int:
        return len(self.actor_to_cluster)

    def above(
        self, min_evidence: float, min_size: int = 3, min_density: float = MIN_DENSITY
    ) -> list[Cluster]:
        """Clusters que superan masa de evidencia, tamaño y cohesión mínimos.

        Los tres criterios son necesarios y ninguno es redundante: la evidencia
        descarta coágulos pequeños, el tamaño descarta parejas, y la densidad
        descarta comunidades grandes pero laxas, cuya evidencia es alta solo
        porque tienen muchos miembros.
        """
        return [
            c
            for c in self.clusters
            if c.evidence >= min_evidence and c.size >= min_size and c.density >= min_density
        ]


def _cluster_stats(
    labels: np.ndarray, n_clusters: int, graph: SimilarityGraph
) -> tuple[np.ndarray, np.ndarray]:
    """Aristas internas y suma de pesos por cluster, vectorizado.

    `labels` asigna a cada actor su cluster, o -1 si no pertenece a ninguno.
    """
    src_label = labels[graph.source]
    dst_label = labels[graph.dest]
    internal = (src_label == dst_label) & (src_label >= 0)

    counts = np.bincount(src_label[internal], minlength=n_clusters)
    weights = np.bincount(
        src_label[internal],
        weights=graph.weight[internal].astype(np.float64),
        minlength=n_clusters,
    )
    return counts, weights


def detect(graph: SimilarityGraph, *, resolution: float = 1.0, seed: int = 0) -> ClusterResult:
    """Agrupa el grafo de similitud en clusters de coordinación."""
    if graph.n_edges == 0:
        return ClusterResult(clusters=[], actor_to_cluster={})

    import igraph as ig
    import leidenalg

    # Los actores aislados no aportan nada al clustering y solo inflan el grafo.
    present = np.unique(np.concatenate([graph.source, graph.dest]))
    remap = np.full(int(present.max()) + 1, -1, dtype=np.int64)
    remap[present] = np.arange(len(present))

    g = ig.Graph(
        n=len(present),
        edges=list(zip(remap[graph.source].tolist(), remap[graph.dest].tolist(), strict=True)),
        edge_attrs={"weight": graph.weight.tolist()},
    )

    partition = leidenalg.find_partition(
        g,
        leidenalg.RBConfigurationVertexPartition,
        weights="weight",
        resolution_parameter=resolution,
        seed=seed,
    )

    # Etiquetas en el espacio de índices global, para cruzarlas con las aristas.
    labels = np.full(graph.n_actors, -1, dtype=np.int64)
    kept: list[list[int]] = []
    for members_local in partition:
        if len(members_local) < 2:
            continue
        members_global = [int(present[i]) for i in members_local]
        labels[members_global] = len(kept)
        kept.append(sorted(members_global))

    if not kept:
        return ClusterResult(clusters=[], actor_to_cluster={})

    counts, weights = _cluster_stats(labels, len(kept), graph)

    clusters = [
        Cluster(
            cluster_id=cid,
            actor_indices=members,
            internal_edges=int(counts[cid]),
            internal_weight=float(weights[cid]),
        )
        for cid, members in enumerate(kept)
    ]
    clusters.sort(key=lambda c: c.evidence, reverse=True)

    actor_to_cluster = {a: c.cluster_id for c in clusters for a in c.actor_indices}
    return ClusterResult(clusters=clusters, actor_to_cluster=actor_to_cluster)


def null_evidence_threshold(
    bm: BipartiteMatrix,
    *,
    threshold: float,
    n_iterations: int = 10,
    floor: float = 0.1,
    idf: bool = True,
    resolution: float = 1.0,
    seed: int = 0,
    safety_factor: float = SAFETY_FACTOR,
) -> float:
    """Masa de evidencia que el azar nunca alcanza, multiplicada por un margen.

    Corrige un problema de comparaciones múltiples fácil de pasar por alto: el
    umbral de similitud controla la tasa de error **por par**, pero una audiencia
    de 250 cuentas tiene unos 31.000 pares. Al cuantil 0,999, decenas de parejas
    lo superan por puro azar y el clustering las ensambla en coágulos de 4 a 9
    cuentas con toda la apariencia de una campaña.

    En validación sintética esos coágulos hundían la precisión al 0,53 con el
    recall intacto en 1,00: la campaña real siempre aparecía como un cluster
    grande y limpio, y todo el error venía de esos grupitos.

    Ni el tamaño ni la densidad los separan —un grupo fortuito de cuatro cuentas
    alcanza densidad 1,0 igual que una granja—. Lo que sí separa es la masa de
    evidencia, que crece con el cuadrado del tamaño del grupo.

    Se pasa el modelo nulo por el pipeline completo de clustering, se toma el
    máximo de evidencia que produce, y se exige superarlo por `safety_factor`.
    """
    if bm.n_actors < 2:
        return float("inf")

    rng = np.random.default_rng(seed)
    best = 0.0

    for it in range(n_iterations):
        src, dst, val = cosine_pairs(randomize(bm, rng), floor=max(floor, threshold), idf=idf)
        keep = val >= threshold
        if not keep.any():
            continue

        null_graph = SimilarityGraph(
            source=src[keep],
            dest=dst[keep],
            weight=val[keep],
            threshold=threshold,
            n_actors=bm.n_actors,
        )
        result = detect(null_graph, resolution=resolution, seed=it)
        best = max(best, max((c.evidence for c in result.clusters), default=0.0))

    return best * safety_factor
