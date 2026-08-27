"""Prueba de extremo a extremo: ¿recupera el motor una campaña inyectada?

Este es el test que justifica la existencia de la herramienta. Si falla, ningún
número que produzca el resto del código es publicable.
"""

import pytest

from botdetector.coordination import bipartite, clustering, similarity
from botdetector.validation import generate, score_detection


def _detect(audience, *, seed=0) -> set[str]:
    """Detección completa, con el listón de evidencia calibrado contra el nulo."""
    bm = bipartite.build(audience.edges)
    graph = similarity.build_graph(bm, n_iterations=10, floor=0.15, seed=seed)
    result = clustering.detect(graph, seed=seed)
    min_evidence = clustering.null_evidence_threshold(
        bm, threshold=graph.threshold, n_iterations=8, floor=0.15, seed=seed
    )
    return {bm.actors[i] for c in result.above(min_evidence) for i in c.actor_indices}


def test_recovers_high_fidelity_campaign():
    """Una granja torpe (fidelidad 0,95) debe salir casi entera y sin arrastrar orgánicas."""
    audience = generate(fidelity=0.95, n_coordinated=30, seed=1)
    scores = score_detection(_detect(audience), audience)

    assert scores["recall"] >= 0.8
    assert scores["precision"] >= 0.9


def test_no_false_positives_on_purely_organic_audience():
    """Sin campaña inyectada, no debe inventarse ninguna.

    Es el test más importante del repositorio: un falso positivo aquí es una
    acusación falsa contra personas reales.
    """
    audience = generate(n_coordinated=0, n_organic=250, seed=2)
    detected = _detect(audience)
    assert detected == set(), f"falsos positivos: {sorted(detected)[:10]}"


@pytest.mark.parametrize("fidelity", [0.4, 0.6, 0.8, 1.0])
def test_precision_holds_across_fidelity(fidelity):
    """El recall puede caer cuando el operador añade ruido; la precisión no debe.

    Es el sentido correcto del error para esta herramienta: preferimos no
    detectar una campaña antes que señalar a alguien por error.
    """
    audience = generate(fidelity=fidelity, n_coordinated=30, seed=3)
    scores = score_detection(_detect(audience), audience)

    if scores["true_positives"] + scores["false_positives"] > 0:
        assert scores["precision"] >= 0.85


def test_recall_degrades_monotonically_with_evasion():
    """Documenta la curva de sensibilidad: menos fidelidad, menos detección."""
    high = score_detection(_detect(generate(fidelity=1.0, seed=4)), generate(fidelity=1.0, seed=4))
    low = score_detection(_detect(generate(fidelity=0.3, seed=4)), generate(fidelity=0.3, seed=4))
    assert high["recall"] >= low["recall"]


def test_larger_campaigns_are_easier_to_see():
    small = generate(fidelity=0.9, n_coordinated=8, seed=5)
    large = generate(fidelity=0.9, n_coordinated=60, seed=5)
    assert (
        score_detection(_detect(large), large)["recall"]
        >= score_detection(_detect(small), small)["recall"]
    )
