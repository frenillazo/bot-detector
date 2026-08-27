"""Colector de Bluesky vía Jetstream (AT Protocol).

Jetstream es un WebSocket **sin autenticación y gratuito** que emite todos los
likes y reposts de la red en tiempo real por unos 850 MB/día.

Esto lo convierte en el banco de pruebas de la herramienta: es el único sitio
donde se observa el 100% de las interacciones. Ahí se valida el motor con verdad
terreno completa y se mide cuánto se degrada al muestrear, que es lo que después
justifica qué se puede y qué no se puede afirmar con los datos parciales de X.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
from collections.abc import AsyncIterator

import websockets

from botdetector.collectors.base import Collector
from botdetector.schema import Action, Interaction, Platform

JETSTREAM_HOSTS = (
    "wss://jetstream2.us-east.bsky.network/subscribe",
    "wss://jetstream1.us-west.bsky.network/subscribe",
)

_COLLECTIONS = {
    "app.bsky.feed.like": Action.LIKE,
    "app.bsky.feed.repost": Action.REPOST,
}


def _author_from_uri(uri: str) -> str | None:
    """Extrae el DID del autor de un AT-URI.

    Formato: at://did:plc:xxxx/app.bsky.feed.post/rkey
    """
    if not uri.startswith("at://"):
        return None
    rest = uri.removeprefix("at://")
    did = rest.split("/", 1)[0]
    return did or None


class BlueskyCollector(Collector):
    platform = Platform.BLUESKY

    def __init__(
        self,
        *,
        host: str = JETSTREAM_HOSTS[0],
        max_reconnects: int = 100,
        ping_timeout: float = 60.0,
    ) -> None:
        self.host = host
        self.max_reconnects = max_reconnects
        self.ping_timeout = ping_timeout
        self.reconnects = 0
        self.last_cursor: int | None = None

    @property
    def coverage(self) -> str:
        base = (
            "Cobertura completa: Jetstream emite el 100% de los likes y reposts "
            "de la red en tiempo real. No hay muestreo ni topes por publicación."
        )
        if self.reconnects:
            base += (
                f" La conexión se reanudó {self.reconnects} vez/veces reanudando "
                "desde el cursor; puede haber huecos si el relay no conservaba "
                "ese punto."
            )
        return base

    def _url(self) -> str:
        params = [f"wantedCollections={c}" for c in _COLLECTIONS]
        if self.last_cursor is not None:
            # Reanudar desde el último evento visto evita huecos en la serie, que
            # en un análisis de sincronía serían indistinguibles de una pausa real
            # de la campaña.
            params.append(f"cursor={self.last_cursor}")
        return f"{self.host}?{'&'.join(params)}"

    async def stream(
        self,
        *,
        until: dt.datetime | None = None,
        limit: int | None = None,
    ) -> AsyncIterator[Interaction]:
        """Emite interacciones, reconectando si el relay corta.

        Una desconexión no debe terminar la recolección. El firehose corta por
        mantenimiento, por picos de tráfico o por considerarnos consumidor lento,
        y una escucha de varias horas los encontrará todos.
        """
        emitted = 0

        while True:
            if until is not None and dt.datetime.now(dt.UTC) >= until:
                return
            if limit is not None and emitted >= limit:
                return

            try:
                async with websockets.connect(
                    self._url(), max_size=None, ping_timeout=self.ping_timeout
                ) as ws:
                    async for raw in ws:
                        if until is not None and dt.datetime.now(dt.UTC) >= until:
                            return
                        if limit is not None and emitted >= limit:
                            return

                        cursor, interaction = self._parse_with_cursor(raw)
                        if cursor is not None:
                            self.last_cursor = cursor
                        if interaction is None:
                            continue

                        emitted += 1
                        yield interaction

            except (websockets.exceptions.WebSocketException, OSError):
                self.reconnects += 1
                if self.reconnects > self.max_reconnects:
                    raise
                # Espera creciente y acotada, para no martillear un relay caído.
                await asyncio.sleep(min(2 ** min(self.reconnects, 5), 30))

    def _parse(self, raw: str | bytes) -> Interaction | None:
        """Convierte un evento de Jetstream en una interacción, o None si no aplica."""
        return self._parse_with_cursor(raw)[1]

    def _parse_with_cursor(self, raw: str | bytes) -> tuple[int | None, Interaction | None]:
        """Como `_parse`, pero devolviendo también el cursor del evento.

        El cursor se actualiza incluso con eventos que se descartan: si sólo
        avanzara con los eventos útiles, una reconexión tras un tramo largo de
        eventos irrelevantes reanudaría demasiado atrás.
        """
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            return None, None

        cursor = event.get("time_us") if isinstance(event, dict) else None

        if not isinstance(event, dict) or event.get("kind") != "commit":
            return cursor, None

        commit = event.get("commit") or {}
        if commit.get("operation") != "create":
            return cursor, None

        action = _COLLECTIONS.get(commit.get("collection", ""))
        if action is None:
            return cursor, None

        record = commit.get("record") or {}
        subject_uri = (record.get("subject") or {}).get("uri")
        actor_did = event.get("did")
        if not subject_uri or not actor_did:
            return cursor, None

        # time_us es el reloj del relay, no el del cliente. Se prefiere porque
        # createdAt lo fija el propio cliente y una granja puede falsearlo.
        ts = (
            dt.datetime.fromtimestamp(cursor / 1_000_000, tz=dt.UTC)
            if cursor
            else dt.datetime.now(dt.UTC)
        )

        return cursor, Interaction(
            platform=self.platform,
            action=action,
            actor_id=actor_did,
            target_id=subject_uri,
            target_author_id=_author_from_uri(subject_uri),
            ts=ts,
        )
