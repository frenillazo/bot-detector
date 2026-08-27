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
    "uniform": 0.90,
    "actor_subset": 0.20,
    "target_subset": 0.40,
    "per_target_cap": 0.80,
}
"""Cobertura mínima por régimen para que el resultado sea publicable.

Derivados de las curvas de `docs/CURVAS.md`, no elegidos a ojo. Dos criterios
distintos según el régimen:

- Para `uniform`, `actor_subset` y `per_target_cap` el suelo marca dónde el
  recall deja de ser utilizable. Por debajo, el detector queda **ciego**: no
  miente, simplemente no ve. Un resultado negativo ahí no significa nada.

- Para `target_subset` el suelo es de otra naturaleza y más serio. Es el único
  régimen donde el muestreo parcial llega a **fabricar** clusters: con el 20% de
  las publicaciones observadas, 1 de cada 40 audiencias puramente orgánicas
  produjo un falso cluster de 27 cuentas. Por debajo del 40% el resultado no es
  incompleto, es potencialmente falso.

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

    if regime == "target_subset":
        return False, (
            f"Cobertura {coverage:.0%}, por debajo del suelo de {floor:.0%}. En este "
            "régimen el muestreo parcial puede fabricar clusters inexistentes: NO "
            "publicar, ni siquiera con advertencias."
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
