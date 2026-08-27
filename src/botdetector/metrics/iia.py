"""Índice de Inautenticidad de Audiencia (IIA).

Tres decisiones de diseño que conviene no revertir sin pensarlo dos veces:

1. **Nada se reporta en absoluto.** Todo valor va acompañado de su intervalo de
   confianza y, cuando hay controles, de la razón frente a la mediana de cuentas
   comparables. "60% bots" no es una afirmación defendible; "4,2x más
   coengagement sincronizado que cuentas comparables (IC95 3,1-5,6)" sí.

2. **Ningún componente clasifica cuentas individuales.** La unidad de análisis es
   la audiencia agregada. Esto no es solo prudencia jurídica: es que el error de
   un clasificador individual se promedia en el agregado, mientras que en un
   señalamiento individual se convierte en una acusación falsa.

3. **El sesgo se inclina hacia el falso negativo.** Umbrales conservadores, nulos
   que sobreestiman ligeramente el azar. Es mejor no detectar una campaña que
   marcar a una persona real.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np


@dataclass(frozen=True)
class Estimate:
    """Un valor puntual con su intervalo de confianza por bootstrap."""

    value: float
    ci_low: float
    ci_high: float
    n: int

    def __str__(self) -> str:
        return f"{self.value:.3f} (IC95 {self.ci_low:.3f}-{self.ci_high:.3f}, n={self.n})"


def bootstrap_ratio(
    numerator: np.ndarray,
    denominator: np.ndarray,
    *,
    n_resamples: int = 2_000,
    confidence: float = 0.95,
    seed: int = 0,
) -> Estimate:
    """IC de un cociente sum(num)/sum(den) remuestreando la unidad de análisis.

    La unidad remuestreada es el **actor**, no la interacción: las interacciones
    de una misma cuenta están fuertemente correlacionadas entre sí, y tratarlas
    como independientes produce intervalos artificialmente estrechos —justo el
    error que haría parecer muy precisa una estimación que no lo es.

    El remuestreo se hace en bucle en lugar de materializar una matriz
    `n_resamples x n`, que con audiencias de seis cifras no cabe en memoria.
    """
    numerator = np.asarray(numerator, dtype=np.float64)
    denominator = np.asarray(denominator, dtype=np.float64)
    n = len(denominator)

    if n == 0 or denominator.sum() == 0:
        return Estimate(float("nan"), float("nan"), float("nan"), 0)

    point = float(numerator.sum() / denominator.sum())
    if n == 1:
        return Estimate(point, point, point, 1)

    rng = np.random.default_rng(seed)
    dist = np.empty(n_resamples, dtype=np.float64)
    for k in range(n_resamples):
        idx = rng.integers(0, n, size=n)
        den = denominator[idx].sum()
        dist[k] = numerator[idx].sum() / den if den else 0.0

    alpha = (1 - confidence) / 2
    return Estimate(
        value=point,
        ci_low=float(np.quantile(dist, alpha)),
        ci_high=float(np.quantile(dist, 1 - alpha)),
        n=n,
    )


def gini(counts: np.ndarray) -> float:
    """Concentración de la audiencia en [0, 1].

    0 = todas las cuentas interactúan por igual (audiencia amplia y difusa).
    1 = casi todas las interacciones vienen de un puñado de cuentas.

    Una audiencia orgánica grande tiende a valores medios; una audiencia cautiva
    operada desde un panel se delata con valores altos y estables en el tiempo.
    """
    counts = np.sort(np.asarray(counts, dtype=np.float64))
    n = len(counts)
    if n == 0 or counts.sum() == 0:
        return 0.0
    index = np.arange(1, n + 1)
    return float((2 * (index * counts).sum()) / (n * counts.sum()) - (n + 1) / n)


def top_share(counts: np.ndarray, fraction: float = 0.01) -> float:
    """Proporción de interacciones aportada por el `fraction` de cuentas más activas."""
    counts = np.asarray(counts, dtype=np.float64)
    total = counts.sum()
    if total == 0:
        return 0.0
    k = max(1, int(np.ceil(len(counts) * fraction)))
    return float(np.sort(counts)[-k:].sum() / total)


@dataclass(frozen=True)
class AudienceProfile:
    """Perfil completo de la audiencia de una cuenta objetivo."""

    target: str
    n_interactions: int
    n_unique_actors: int

    coordination_share: Estimate
    """Fracción de interacciones procedentes de clusters coordinados."""

    recurrence_top1pct: float
    """Fracción de interacciones aportada por el 1% de cuentas más recurrentes."""

    audience_gini: float
    """Concentración de la audiencia."""

    median_latency_s: float | None
    """Mediana de segundos entre publicación e interacción."""

    fast_reaction_share: float | None
    """Fracción de interacciones en los primeros 60 s. Colas imposibles = enjambre."""

    largest_cluster_size: int
    n_clusters: int
    similarity_threshold: float

    def to_dict(self) -> dict:
        d = asdict(self)
        d["coordination_share"] = asdict(self.coordination_share)
        return d


def profile_audience(
    target: str,
    *,
    actor_interaction_counts: dict[str, int],
    coordinated_actors: set[str],
    latencies_s: np.ndarray | None = None,
    largest_cluster_size: int = 0,
    n_clusters: int = 0,
    similarity_threshold: float = float("nan"),
    fast_reaction_s: float = 60.0,
    seed: int = 0,
) -> AudienceProfile:
    """Calcula el perfil agregado a partir de los recuentos por actor.

    `actor_interaction_counts` mapea actor -> número de interacciones aportadas.
    `coordinated_actors` es el subconjunto que quedó dentro de algún cluster que
    superó el umbral de coordinación.
    """
    actors = list(actor_interaction_counts)
    counts = np.array([actor_interaction_counts[a] for a in actors], dtype=np.float64)
    total = float(counts.sum())

    # Se pondera por interacciones, no por cuentas: una granja de 50 cuentas que
    # aporta el 40% de los retweets importa más que 50 cuentas que aportan uno.
    contribution = np.where(
        np.array([a in coordinated_actors for a in actors], dtype=bool), counts, 0.0
    )
    coord = bootstrap_ratio(contribution, counts, seed=seed)

    median_lat = None
    fast_share = None
    if latencies_s is not None and len(latencies_s):
        lat = np.asarray(latencies_s, dtype=np.float64)
        lat = lat[lat >= 0]
        if lat.size:
            median_lat = float(np.median(lat))
            fast_share = float((lat <= fast_reaction_s).mean())

    return AudienceProfile(
        target=target,
        n_interactions=int(total),
        n_unique_actors=len(actors),
        coordination_share=coord,
        recurrence_top1pct=top_share(counts, 0.01),
        audience_gini=gini(counts),
        median_latency_s=median_lat,
        fast_reaction_share=fast_share,
        largest_cluster_size=largest_cluster_size,
        n_clusters=n_clusters,
        similarity_threshold=similarity_threshold,
    )


def relative_to_baseline(
    target: AudienceProfile, controls: list[AudienceProfile]
) -> dict[str, float]:
    """Razones frente a la mediana de las cuentas de control.

    Este es el número que se publica. Sin controles emparejados, el IIA absoluto
    no significa nada: cualquier clasificador con un 5% de falsos positivos
    devuelve "5% de bots" sobre una audiencia perfectamente limpia.
    """
    if not controls:
        raise ValueError("se requieren cuentas de control: el IIA absoluto no es interpretable")

    def ratio(getter) -> float:
        base = float(np.median([getter(c) for c in controls]))
        if base == 0:
            return float("inf") if getter(target) > 0 else 1.0
        return float(getter(target) / base)

    return {
        "coordination_ratio": ratio(lambda p: p.coordination_share.value),
        "recurrence_ratio": ratio(lambda p: p.recurrence_top1pct),
        "gini_ratio": ratio(lambda p: p.audience_gini),
        "n_controls": len(controls),
    }
