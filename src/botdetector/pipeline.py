"""Orquestación: del almacén al perfil de audiencia.

aristas -> matriz bipartita -> umbral nulo -> grafo -> clusters -> IIA
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from botdetector.coordination import bipartite, clustering, similarity, validated
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
    resolution: float = 1.0
    seed: int = 0

    min_actor_activity: int = 2
    """Interacciones mínimas para incluir una cuenta.

    Inofensivo y útil: una cuenta con una sola interacción nunca puede alcanzar
    `min_shared`, así que descartarla no pierde señal y reduce la matriz.
    """

    min_target_engagement: int = 1
    """Interactuantes mínimos para incluir una publicación. **Dejar en 1.**

    Fue 2 mientras el criterio era el coseno, donde las publicaciones con un
    único interactuante eran ruido. Con el test hipergeométrico son parte del
    universo N, y N es justo lo que distingue "2 de 2 compartidas sobre 300
    publicaciones" —irrelevante— de "2 de 2 sobre 25" —sospechoso—.

    Medido: subirlo a 2 elimina 55 aristas de 2.398 y hunde la precisión de
    1,00 a 0,88. Un prefiltro heredado del método anterior que degradaba el
    nuevo en silencio.
    """

    method: str = "hypergeometric"
    """`hypergeometric` (recomendado) o `permutation` (histórico).

    El coseno con umbral por permutación no distingue "2 de 2 compartidos" de
    "40 de 40": ambos dan 1,0. Con observación parcial eso fabrica clusters de
    cuentas reales. Ver `coordination/validated.py`.
    """

    alpha: float = 0.01
    """Nivel de significación del test hipergeométrico, antes de corregir."""

    correction: str = "permutation"
    """`permutation` (max-T de Westfall-Young), `bonferroni` o `fdr`.

    Por defecto `permutation`: el modelo hipergeométrico asume objetivos
    equiprobables, cosa falsa en cualquier audiencia real, y Bonferroni no
    corrige esa mala especificación. Ver `coordination/validated.py`.
    """

    min_shared: int = 2
    """Coincidencias mínimas para siquiera contrastar un par."""

    calibration_iterations: int = 40
    """Permutaciones para calibrar el umbral de p-valor y la masa de evidencia.

    Elegido por criterio explícito, no por comodidad: es el menor número que
    anula los falsos positivos sobre audiencias puramente orgánicas (0/30 y
    0/40 en los dos controles negativos) manteniendo recall 1,00. Con 20 queda
    1/30; con 80 el recall empieza a caer a 0,98 por exceso de rigor.
    """

    # --- solo para method="permutation" ---
    null_quantile: float = 0.999
    null_iterations: int = 20
    similarity_floor: float = 0.1
    safety_factor: float = clustering.SAFETY_FACTOR

    min_cluster_size: int = 5
    """Suelo absoluto de tamaño de cluster.

    Subido de 3 a 5 por una razón empírica muy concreta: los falsos positivos
    residuales que quedan tienen **todos** exactamente 3 cuentas. En 500
    ejecuciones sobre audiencias puramente orgánicas con cobertura parcial de
    publicaciones aparecieron 6 falsos clusters, y los 6 eran de tamaño 3, el
    mínimo que el detector podía emitir.

    Coste: las campañas de 3 y 4 cuentas dejan de ser detectables. Era una
    capacidad poco fiable de todos modos —recall 0,48 con detección en el 48% de
    los casos— y perderla a cambio de eliminar el señalamiento de personas reales
    es exactamente el intercambio que impone la tercera regla del proyecto.

    Las campañas de 5 cuentas siguen detectándose (recall 0,72, precisión 0,98).
    """

    min_density: float = clustering.MIN_DENSITY
    """Fracción mínima de pares internos que deben ser significativos."""


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


@dataclass(frozen=True)
class Detection:
    """Salida del motor de coordinación sobre un conjunto de aristas."""

    coordinated: set[str]
    clusters: list[clustering.Cluster]
    graph: similarity.SimilarityGraph
    matrix: bipartite.BipartiteMatrix
    min_evidence: float


def detect_edges(edges: list[tuple[str, str]], config: AnalysisConfig | None = None) -> Detection:
    """Ejecuta el motor completo sobre aristas (actor, objetivo).

    Es el único punto donde vive la secuencia matriz -> umbral nulo -> grafo ->
    clusters -> calibración. Tanto `analyze()` como las curvas de validación
    pasan por aquí a propósito: una curva de sensibilidad medida sobre una
    reimplementación del detector no describe al detector, y sería peor que no
    tener curva, porque daría falsa confianza.
    """
    cfg = config or AnalysisConfig()
    bm = bipartite.build(edges)

    if cfg.method == "hypergeometric":
        iterations = cfg.calibration_iterations

        # Nivel 1: qué p-valor supera lo que produce el azar (max-T).
        cutoff = validated.calibrate_alpha(
            bm, n_iterations=iterations, min_shared=cfg.min_shared, seed=cfg.seed
        )
        graph = validated.validate(
            bm,
            correction=cfg.correction,
            alpha=cfg.alpha,
            min_shared=cfg.min_shared,
            cutoff=cutoff,
            seed=cfg.seed,
        )
        result = clustering.detect(graph, resolution=cfg.resolution, seed=cfg.seed)

        # Nivel 2: qué masa de evidencia llega a ensamblar el azar con ese mismo
        # umbral. Sin esta capa, aristas fortuitas forman clusters de 3 a 5.
        min_evidence = validated.null_evidence_threshold(
            bm,
            cutoff=cutoff,
            min_shared=cfg.min_shared,
            n_iterations=iterations,
            resolution=cfg.resolution,
            seed=cfg.seed,
            safety_factor=cfg.safety_factor,
        )

    elif cfg.method == "permutation":
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

    else:
        raise ValueError(f"método desconocido: {cfg.method!r}")

    flagged = result.above(min_evidence, cfg.min_cluster_size, cfg.min_density)

    return Detection(
        coordinated={bm.actors[i] for c in flagged for i in c.actor_indices},
        clusters=flagged,
        graph=graph,
        matrix=bm,
        min_evidence=min_evidence,
    )


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
    detection = detect_edges(edges, cfg)
    bm, graph, flagged = detection.matrix, detection.graph, detection.clusters
    coordinated = detection.coordinated

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
