"""Parseo de eventos de Jetstream. Sin red: se alimentan payloads literales."""

import datetime as dt
import json

from botdetector.collectors.bluesky import BlueskyCollector, _author_from_uri
from botdetector.schema import Action

COLLECTOR = BlueskyCollector()

LIKE_EVENT = {
    "did": "did:plc:actor123",
    "time_us": 1_756_300_000_000_000,
    "kind": "commit",
    "commit": {
        "operation": "create",
        "collection": "app.bsky.feed.like",
        "rkey": "3k",
        "record": {
            "$type": "app.bsky.feed.like",
            "createdAt": "2026-08-27T12:00:00.000Z",
            "subject": {
                "cid": "bafy",
                "uri": "at://did:plc:author456/app.bsky.feed.post/3l",
            },
        },
    },
}


def test_parses_like():
    i = COLLECTOR._parse(json.dumps(LIKE_EVENT))
    assert i is not None
    assert i.action is Action.LIKE
    assert i.actor_id == "did:plc:actor123"
    assert i.target_author_id == "did:plc:author456"
    assert i.ts.tzinfo is dt.UTC


def test_parses_repost():
    event = json.loads(json.dumps(LIKE_EVENT))
    event["commit"]["collection"] = "app.bsky.feed.repost"
    assert COLLECTOR._parse(json.dumps(event)).action is Action.REPOST


def test_uses_relay_clock_not_client_clock():
    """createdAt lo fija el cliente y una granja puede falsearlo; time_us no."""
    i = COLLECTOR._parse(json.dumps(LIKE_EVENT))
    expected = dt.datetime.fromtimestamp(1_756_300_000, tz=dt.UTC)
    assert i.ts == expected


def test_ignores_deletes_and_other_collections():
    for mutate in (
        lambda e: e["commit"].update(operation="delete"),
        lambda e: e["commit"].update(collection="app.bsky.feed.post"),
        lambda e: e.update(kind="identity"),
    ):
        event = json.loads(json.dumps(LIKE_EVENT))
        mutate(event)
        assert COLLECTOR._parse(json.dumps(event)) is None


def test_survives_malformed_input():
    """El firehose es una fuente hostil: nunca debe tumbar la recolección."""
    for payload in ("no es json", "{}", '{"kind":"commit"}', '{"kind":"commit","commit":{}}'):
        assert COLLECTOR._parse(payload) is None


def test_author_extraction():
    assert _author_from_uri("at://did:plc:x/app.bsky.feed.post/1") == "did:plc:x"
    assert _author_from_uri("https://example.com") is None
    assert _author_from_uri("at://") is None


def test_coverage_is_documented():
    """El informe cita literalmente esta cadena; no puede quedar vacía."""
    assert "100%" in COLLECTOR.coverage


def test_coverage_discloses_reconnections():
    """Una reconexión puede dejar huecos; el informe tiene que decirlo."""
    c = BlueskyCollector()
    assert "reanud" not in c.coverage
    c.reconnects = 3
    assert "3" in c.coverage and "huecos" in c.coverage


def test_cursor_advances_on_discarded_events():
    """Si el cursor solo avanzara con eventos útiles, una reconexión retrocedería
    hasta el último like, reprocesando todo el tramo intermedio."""
    event = json.loads(json.dumps(LIKE_EVENT))
    event["kind"] = "identity"

    cursor, interaction = COLLECTOR._parse_with_cursor(json.dumps(event))
    assert interaction is None
    assert cursor == LIKE_EVENT["time_us"]


def test_cursor_is_none_for_unparseable_payloads():
    assert COLLECTOR._parse_with_cursor("no es json") == (None, None)


def test_url_includes_cursor_only_after_first_event():
    c = BlueskyCollector()
    assert "cursor=" not in c._url()
    c.last_cursor = 1_756_300_000_000_000
    assert "cursor=1756300000000000" in c._url()
    assert "wantedCollections=app.bsky.feed.like" in c._url()
