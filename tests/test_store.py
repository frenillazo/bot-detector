import datetime as dt

from botdetector.schema import Action, Interaction, Platform
from botdetector.store import Store


def _mk(actor: str, target: str, author: str = "victim", minutes: int = 0) -> Interaction:
    return Interaction(
        platform=Platform.BLUESKY,
        action=Action.REPOST,
        actor_id=actor,
        target_id=target,
        target_author_id=author,
        ts=dt.datetime(2026, 8, 27, 12, 0, tzinfo=dt.UTC) + dt.timedelta(minutes=minutes),
    )


def test_insert_and_count():
    with Store() as s:
        assert s.insert([_mk("a", "p1"), _mk("b", "p1")]) == 2
        assert s.count() == 2


def test_edges_filters_by_minimum_activity():
    """Un actor con una sola interacción no puede aportar evidencia de sincronía."""
    interactions = [
        _mk("a", "p1"),
        _mk("a", "p2"),
        _mk("b", "p1"),
        _mk("b", "p2"),
        _mk("solo", "p1"),
    ]
    with Store() as s:
        s.insert(interactions)
        edges = s.edges(target_author_id="victim", min_actor_activity=2)
        assert {a for a, _ in edges} == {"a", "b"}


def test_edges_filters_by_target_engagement():
    interactions = [_mk("a", "p1"), _mk("b", "p1"), _mk("a", "orphan")]
    with Store() as s:
        s.insert(interactions)
        edges = s.edges(target_author_id="victim", min_actor_activity=1, min_target_engagement=2)
        assert {t for _, t in edges} == {"p1"}


def test_edges_scoped_to_target_author():
    with Store() as s:
        s.insert([_mk("a", "p1", "victim"), _mk("a", "p2", "otro")])
        edges = s.edges(target_author_id="victim", min_actor_activity=1, min_target_engagement=1)
        assert edges == [("a", "p1")]


def test_snapshot_roundtrip_and_hash(tmp_path):
    with Store() as s:
        s.insert([_mk("a", "p1"), _mk("b", "p1")])
        path, digest = s.export_snapshot(tmp_path)

    assert path.exists()
    assert len(digest) == 64
    assert (tmp_path / "SNAPSHOT_SHA256").read_text().startswith(digest)

    with Store() as restored:
        assert restored.load_snapshot(path) == 2


def test_snapshot_hash_is_stable(tmp_path):
    """El mismo contenido debe dar el mismo hash: es lo que ancla el informe."""
    digests = []
    for name in ("a", "b"):
        with Store() as s:
            s.insert([_mk("x", "p1"), _mk("y", "p1")])
            _, d = s.export_snapshot(tmp_path / name)
            digests.append(d)
    assert digests[0] == digests[1]
