"""Orquestación: del almacén al perfil de audiencia.

aristas -> matriz bipartita -> umbral nulo -> grafo -> clusters -> IIA
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from botdetector.coordination import bipartite, clustering, similarity
from botdetector.metrics.iia import AudienceProfile, profile_audience
from botdetector.store.duck import Store


@dataclass(frozen=True)
class AnalysisConfig:
    """Parámetros del análisis.

    Se agrupan en un objeto explícito para que queden registrados en el informe:
    un resultado sin sus parámetros no es reproducible, y una herramienta cuyos
    resultados no son reproducibles no sirve como evidencia.
    """

    actions: tuple[str, ...] = ("repost", "quote")
    min_actor_activity: int = 2
    min_target_engagement: int = 2
    null_quantile: float = 0.999
    null_iterations: int = 20
    similarity_floor: float = 0.1
    resolution: float = 1.0
    seed: int = 0

    min_cluster_size: int = 3
    """Suelo absoluto de tamaño. La decisión real la toma la masa de evidencia."""

    safety_factor: float = clustering.SAFETY_FACTOR
    """Margen exigido sobre la estructura más fuerte que produce el azar."""


@dataclass(frozen=True)
class AnalysisResult:
    profile: AudienceProfile
    clusters: list[clustering.Cluster]
    graph: similarity.SimilarityGraph
    matrix: bipartite.BipartiteMatrix
    config: AnalysisConfig

    def coordinated_actor_ids(self) -> list[str]:
        """Handles/IDs de los actores en clusters marcados.

        Existe para auditoría interna y para que un tercero pueda reproducir el
        resultado. NO es para publicación: señalar cuentas individuales es
        justamente lo que ETHICS.md prohíbe.
        """
        flagged = {i for c in self.clusters for i in c.actor_indices}
        return [self.matrix.actors[i] for i in sorted(flagged)]


def analyze(
    store: Store, target_author_id: str, config: AnalysisConfig | None = None
) -> AnalysisResult:
    """Perfila la audiencia que amplifica a `target_author_id`."""
    cfg = config or AnalysisConfig()

    edges = store.edges(
        target_author_id=target_author_id,
        actions=cfg.actions,
        min_actor_activity=cfg.min_actor_activity,
        min_target_engagement=cfg.min_target_engagement,
    )
    bm = bipartite.build(edges)

    graph = similarity.build_graph(
        bm,
        quantile=cfg.null_quantile,
        n_iterations=cfg.null_iterations,
        floor=cfg.similarity_floor,
        seed=cfg.seed,
    )
    result = clustering.detect(graph, resolution=cfg.resolution, seed=cfg.seed)

    min_evidence = clustering.null_evidence_threshold(
        bm,
        threshold=graph.threshold,
        n_iterations=cfg.null_iterations // 2 or 1,
        floor=cfg.similarity_floor,
        resolution=cfg.resolution,
        seed=cfg.seed,
        safety_factor=cfg.safety_factor,
    )
    flagged = result.above(min_evidence, cfg.min_cluster_size)

    coordinated = {bm.actors[i] for c in flagged for i in c.actor_indices}

    counts = store.actor_counts(target_author_id, actions=cfg.actions)
    raw_latencies = store.latencies(target_author_id, actions=cfg.actions)
    latencies = np.array(raw_latencies, dtype=np.float64) if raw_latencies else None

    profile = profile_audience(
        target_author_id,
        actor_interaction_counts=counts,
        coordinated_actors=coordinated,
        latencies_s=latencies,
        largest_cluster_size=max((c.size for c in flagged), default=0),
        n_clusters=len(flagged),
        similarity_threshold=graph.threshold,
        seed=cfg.seed,
    )

    return AnalysisResult(profile=profile, clusters=flagged, graph=graph, matrix=bm, config=cfg)
