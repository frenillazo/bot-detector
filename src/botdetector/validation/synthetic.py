"""Generación de audiencias sintéticas con coordinación inyectada.

Sin esto, la herramienta es opinión con gráficos. La única forma de poder afirmar
"detectamos coordinación" es haber medido antes, sobre datos donde se conoce la
respuesta, cuánta coordinación hace falta para que el motor la vea y con cuántos
falsos positivos.

El generador produce dos poblaciones:

  - **Orgánica**: cada cuenta amplifica una selección propia de mensajes, con
    popularidad desigual (ley de potencias). Genera solapamiento real —los
    mensajes populares los amplifica mucha gente— pero no sincronía.
  - **Coordinada**: un grupo que amplifica el mismo repertorio de mensajes con
    probabilidad `fidelity`. Con fidelity=1.0 es una granja torpe; a 0,5 imita a
    un operador que introduce ruido para evadir detección.

Barrer `fidelity` y `size` da la curva de sensibilidad que debe acompañar a
cualquier informe publicado.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class SyntheticAudience:
    """Audiencia sintética con verdad terreno conocida."""

    edges: list[tuple[str, str]]
    coordinated_actors: set[str]
    organic_actors: set[str]

    @property
    def n_actors(self) -> int:
        return len(self.coordinated_actors) + len(self.organic_actors)


def generate(
    *,
    n_organic: int = 200,
    n_coordinated: int = 30,
    n_targets: int = 300,
    organic_activity: int = 6,
    campaign_size: int = 40,
    fidelity: float = 0.9,
    popularity_alpha: float = 1.5,
    seed: int = 0,
) -> SyntheticAudience:
    """Construye una audiencia sintética.

    `fidelity` es el parámetro que importa: la probabilidad de que una cuenta
    coordinada amplifique cada mensaje de su repertorio. Es el mando que simula
    lo bien que un operador oculta su campaña.
    """
    rng = np.random.default_rng(seed)
    targets = [f"post:{i}" for i in range(n_targets)]

    # Popularidad desigual: sin esto, la población orgánica tendría solapamiento
    # uniformemente bajo y el problema sería artificialmente fácil.
    weights = 1.0 / np.power(np.arange(1, n_targets + 1), popularity_alpha)
    weights /= weights.sum()

    edges: list[tuple[str, str]] = []

    organic = set()
    for i in range(n_organic):
        actor = f"organic:{i}"
        organic.add(actor)
        k = max(1, int(rng.poisson(organic_activity)))
        chosen = rng.choice(n_targets, size=min(k, n_targets), replace=False, p=weights)
        edges.extend((actor, targets[t]) for t in chosen)

    coordinated = set()
    if n_coordinated > 0:
        campaign = rng.choice(n_targets, size=min(campaign_size, n_targets), replace=False)
        for i in range(n_coordinated):
            actor = f"coord:{i}"
            coordinated.add(actor)
            mask = rng.random(len(campaign)) < fidelity
            edges.extend((actor, targets[t]) for t in campaign[mask])

    rng.shuffle(edges)  # type: ignore[arg-type]
    return SyntheticAudience(edges=edges, coordinated_actors=coordinated, organic_actors=organic)


def score_detection(detected: set[str], truth: SyntheticAudience) -> dict[str, float]:
    """Precisión, recall y F1 de una detección contra la verdad terreno."""
    tp = len(detected & truth.coordinated_actors)
    fp = len(detected & truth.organic_actors)
    fn = len(truth.coordinated_actors - detected)

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
    }
