import datetime as dt

import pytest
from pydantic import ValidationError

from botdetector.schema import Action, Interaction, Platform


def _interaction(**kw) -> Interaction:
    base = {
        "platform": Platform.BLUESKY,
        "action": Action.LIKE,
        "actor_id": "did:plc:abc",
        "target_id": "at://did:plc:xyz/app.bsky.feed.post/1",
        "target_author_id": "did:plc:xyz",
        "ts": dt.datetime(2026, 8, 27, 12, 0, tzinfo=dt.UTC),
    }
    return Interaction(**(base | kw))


def test_rejects_naive_timestamps():
    """Un timestamp sin zona corrompe silenciosamente todo el análisis de sincronía."""
    with pytest.raises(ValidationError):
        _interaction(ts=dt.datetime(2026, 8, 27, 12, 0))


def test_normalizes_to_utc():
    madrid = dt.timezone(dt.timedelta(hours=2))
    i = _interaction(ts=dt.datetime(2026, 8, 27, 14, 0, tzinfo=madrid))
    assert i.ts == dt.datetime(2026, 8, 27, 12, 0, tzinfo=dt.UTC)


def test_latency_requires_target_timestamp():
    assert _interaction().latency_s is None

    i = _interaction(target_ts=dt.datetime(2026, 8, 27, 11, 59, tzinfo=dt.UTC))
    assert i.latency_s == 60.0


def test_is_immutable():
    i = _interaction()
    with pytest.raises(ValidationError):
        i.actor_id = "otro"
