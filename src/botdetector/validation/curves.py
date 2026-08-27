"""Curvas de sensibilidad: qué se puede afirmar con datos parciales.

Un informe que dice "el 34% de la amplificación procede de un cluster coordinado"
sin decir sobre qué fracción de los datos se calculó es indefendible. Este módulo
produce el número que falta.

La pregunta que responde no es "¿cuántos datos tenemos?" sino la única que
importa: **por debajo de qué cobertura este detector deja de ver campañas, y a
partir de qué cobertura lo que dice es fiable.**
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass, replace

import numpy as np

from botdetector.pipeline import AnalysisConfig, detect_edges
from botdetector.validation import sampling
from botdetector.validation.synthetic import SyntheticAudience, generate, score_detection

MINIMUM_COVERAGE = {
    "uniform": 0.70,
    "actor_subset": 0.40,
    "target_subset": 0.30,
    "per_target_cap": 0.55,
}
"""Cobertura mínima por régimen para que el resultado sea publicable.

Derivados de las curvas de `docs/CURVAS.md` con un criterio explícito: la menor
cobertura a la que la precisión sigue en 1,00 **y** el recall se mantiene por
encima de 0,5.

Recalibrados tras sustituir el criterio de coseno por el test hipergeométrico
calibrado por permutación. Los suelos anteriores eran mucho más altos —90% para
`uniform`, 80% para `per_target_cap`— porque describían un detector peor.

El cambio cualitativo importante está en `target_subset`. Con el criterio de
coseno era el único régimen que **fabricaba** clusters: al 20% de cobertura, 1 de
cada 40 audiencias puramente orgánicas producía un falso cluster de 27 cuentas
reales. Con el criterio actual ese modo de fallo desaparece —0 de 40, y precisión
1,00 en toda la curva—, y su suelo pasa a marcar simplemente pérdida de
sensibilidad, como los demás.

Importa porque el régimen de la búsqueda de X —ventana temporal acotada, tope de
publicaciones por consulta— *es* subconjunto de publicaciones.
"""


def is_publishable(regime: str, coverage: float) -> tuple[bool, str]:
    """¿Se puede publicar un resultado obtenido con esta cobertura?

    Devuelve (veredicto, motivo). El motivo está redactado para citarse tal cual
    en un informe o para justificar por qué no se publica.
    """
    floor = MINIMUM_COVERAGE.get(regime)
    if floor is None:
        return False, f"Régimen de observación desconocido: {regime!r}."

    if coverage >= floor:
        return True, (
            f"Cobertura {coverage:.0%} sobre un suelo de {floor:.0%} para el régimen "
            f"'{regime}'. El resultado es interpretable."
        )

    return False, (
        f"Cobertura {coverage:.0%}, por debajo del suelo de {floor:.0%}. El detector "
        "está ciego a este nivel: una ausencia de detección no es evidencia de "
        "ausencia de coordinación."
    )


@dataclass(frozen=True)
class CurvePoint:
    """Un punto de la curva: un régimen, una intensidad, agregado sobre semillas."""

    regime: str
    parameter: float
    retention: float
    precision: float
    recall: float
    detection_rate: float
    """Fracción de ejecuciones en las que se detectó algo. Distingue 'no
    encontró nada' de 'encontró cosas equivocadas', que son fallos distintos."""

    n_runs: int

    def as_row(self) -> dict:
        return asdict(self)


def _evaluate(
    audience: SyntheticAudience,
    observed: list[tuple[str, str]],
    config: AnalysisConfig,
) -> dict[str, float]:
    detection = detect_edges(observed, config)
    return score_detection(detection.coordinated, audience)


def sweep(
    *,
    regime: str,
    parameters: list[float],
    seeds: list[int],
    fidelity: float = 0.9,
    n_coordinated: int = 30,
    config: AnalysisConfig | None = None,
    audience_factory: Callable[[int], SyntheticAudience] | None = None,
) -> list[CurvePoint]:
    """Barre un régimen de muestreo y devuelve la curva.

    Cada punto promedia varias semillas: con una sola, la varianza entre
    audiencias sintéticas es mayor que el efecto que se quiere medir.
    """
    cfg = config or AnalysisConfig()
    factory = audience_factory or (
        lambda s: generate(fidelity=fidelity, n_coordinated=n_coordinated, seed=s)
    )

    points: list[CurvePoint] = []

    for param in parameters:
        precisions: list[float] = []
        recalls: list[float] = []
        retentions: list[float] = []
        detected_any = 0

        for seed in seeds:
            audience = factory(seed)
            rng = np.random.default_rng(seed + 10_000)

            if regime == "per_target_cap":
                observed = sampling.per_target_cap(audience.edges, int(param), rng)
            else:
                observed = sampling.STRATEGIES[regime](audience.edges, param, rng)

            retentions.append(sampling.retention(observed, audience.edges))

            scores = _evaluate(audience, observed, replace(cfg, seed=seed))
            recalls.append(scores["recall"])

            # La precisión solo está definida si hubo alguna detección. Meter un
            # 0 cuando no se detectó nada mezclaría "se equivocó" con "no vio
            # nada", que son fallos distintos y con consecuencias distintas.
            if scores["true_positives"] + scores["false_positives"] > 0:
                detected_any += 1
                precisions.append(scores["precision"])

        points.append(
            CurvePoint(
                regime=regime,
                parameter=float(param),
                retention=float(np.mean(retentions)),
                precision=float(np.mean(precisions)) if precisions else float("nan"),
                recall=float(np.mean(recalls)),
                detection_rate=detected_any / len(seeds),
                n_runs=len(seeds),
            )
        )

    return points


def to_markdown(points: list[CurvePoint], title: str) -> str:
    """Tabla markdown lista para pegar en un informe."""
    lines = [
        f"**{title}**",
        "",
        "| Parámetro | Datos retenidos | Precisión | Recall | Tasa de detección |",
        "|---|---|---|---|---|",
    ]
    for p in points:
        precision = "—" if np.isnan(p.precision) else f"{p.precision:.2f}"
        lines.append(
            f"| {p.parameter:g} | {p.retention:.0%} | {precision} | "
            f"{p.recall:.2f} | {p.detection_rate:.0%} |"
        )
    return "\n".join(lines)
