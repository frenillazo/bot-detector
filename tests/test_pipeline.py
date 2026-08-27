"""Pipeline completo, desde el almacén hasta el perfil.

Estos tests existen porque su ausencia dejó pasar un fallo real: el pipeline
leía las interacciones vía Arrow, lo que exigía `pyarrow` en tiempo de ejecución
sin declararlo, y devolver columnas TIMESTAMPTZ a Python arrastraba además una
dependencia de `pytz`. Los tests unitarios de cada módulo pasaban; `analyze()`
reventaba. De ahí que se recorra el camino entero contra un almacén real.
"""

import datetime as dt

import pytest

from botdetector.pipeline import AnalysisConfig, analyze
from botdetector.schema import Action, Interaction, Platform
from botdetector.store import Store
from botdetector.validation import generate

BASE = dt.datetime(2026, 8, 27, 12, 0, tzinfo=dt.UTC)


def _store_from(audience, *, with_target_ts: bool = False) -> Store:
    store = Store()
    posted = {}
    interactions = []
    for k, (actor, target) in enumerate(audience.edges):
        posted.setdefault(target, BASE + dt.timedelta(minutes=len(posted)))
        interactions.append(
            Interaction(
                platform=Platform.BLUESKY,
                action=Action.REPOST,
                actor_id=actor,
                target_id=target,
                target_author_id="objetivo",
                ts=posted[target] + dt.timedelta(seconds=10 + k % 300),
                target_ts=posted[target] if with_target_ts else None,
            )
        )
    store.insert(interactions)
    return store


def test_analyze_runs_end_to_end_and_finds_campaign():
    audience = generate(fidelity=0.95, n_coordinated=30, seed=1)
    with _store_from(audience) as store:
        result = analyze(store, "objetivo", AnalysisConfig(actions=("repost",), seed=1))

    assert result.profile.n_unique_actors > 0
    assert result.profile.n_clusters >= 1
    assert result.profile.largest_cluster_size >= 20

    # Toda la campaña señalada debe ser campaña de verdad.
    flagged = set(result.coordinated_actor_ids())
    assert flagged and flagged <= audience.coordinated_actors


def test_analyze_reports_nothing_on_organic_audience():
    audience = generate(n_coordinated=0, n_organic=250, seed=2)
    with _store_from(audience) as store:
        result = analyze(store, "objetivo", AnalysisConfig(actions=("repost",), seed=2))

    assert result.profile.n_clusters == 0
    assert result.profile.coordination_share.value == pytest.approx(0.0)


def test_analyze_computes_latency_without_pytz_or_pyarrow():
    """La latencia se calcula en SQL con epoch(); no debe importar nada extra."""
    audience = generate(fidelity=0.95, n_coordinated=20, seed=3)
    with _store_from(audience, with_target_ts=True) as store:
        result = analyze(store, "objetivo", AnalysisConfig(actions=("repost",), seed=3))

    assert result.profile.median_latency_s is not None
    assert result.profile.median_latency_s > 0
    assert 0.0 <= result.profile.fast_reaction_share <= 1.0


def test_analyze_on_empty_store():
    with Store() as store:
        result = analyze(store, "nadie", AnalysisConfig(actions=("repost",)))

    assert result.profile.n_interactions == 0
    assert result.profile.n_clusters == 0
    assert result.coordinated_actor_ids() == []


def test_config_is_recorded_in_result():
    """Un resultado sin sus parámetros no es reproducible."""
    cfg = AnalysisConfig(actions=("repost",), seed=7, safety_factor=12.0)
    with Store() as store:
        result = analyze(store, "nadie", cfg)
    assert result.config is cfg
