"""Esquema canónico de interacciones, común a todas las plataformas.

Toda la herramienta opera sobre una única tupla:

    (actor, acción, objetivo, autor del objetivo, instante)

Reducirlo todo a esta forma es lo que permite que el motor de coordinación sea
agnóstico de plataforma: la matriz bipartita actor x objetivo se construye igual
con likes de Bluesky que con retweets de X.
"""

from __future__ import annotations

import datetime as dt
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


class Platform(StrEnum):
    BLUESKY = "bluesky"
    X = "x"
    MASTODON = "mastodon"


class Action(StrEnum):
    """Tipos de interacción positiva que amplifican un mensaje.

    Se excluyen deliberadamente las interacciones negativas (bloqueos, mutes):
    no son observables y no amplifican.
    """

    LIKE = "like"
    REPOST = "repost"
    REPLY = "reply"
    QUOTE = "quote"
    FOLLOW = "follow"


class Interaction(BaseModel):
    """Una interacción individual, normalizada."""

    model_config = {"frozen": True}

    platform: Platform
    action: Action

    actor_id: str = Field(description="Identificador estable de quien interactúa")
    actor_handle: str | None = Field(default=None, description="Handle legible, si se conoce")

    target_id: str = Field(description="Identificador estable del objeto amplificado")
    target_author_id: str | None = Field(
        default=None, description="Autor del objeto; None si no se pudo resolver"
    )

    ts: dt.datetime = Field(description="Instante de la interacción, siempre en UTC")
    target_ts: dt.datetime | None = Field(
        default=None,
        description="Instante de publicación del objetivo. Necesario para la latencia.",
    )

    @field_validator("ts", "target_ts")
    @classmethod
    def _require_utc(cls, v: dt.datetime | None) -> dt.datetime | None:
        """Rechaza timestamps naive.

        La sincronía es la señal central de la herramienta; un timestamp sin zona
        horaria corrompe silenciosamente todo el análisis temporal.
        """
        if v is None:
            return None
        if v.tzinfo is None:
            raise ValueError("los timestamps deben llevar zona horaria explícita (UTC)")
        return v.astimezone(dt.UTC)

    @property
    def latency_s(self) -> float | None:
        """Segundos entre la publicación del objetivo y la interacción."""
        if self.target_ts is None:
            return None
        return (self.ts - self.target_ts).total_seconds()


# DDL de la tabla de interacciones. Se mantiene aquí, junto al modelo, para que
# ambos se modifiquen a la vez.
INTERACTIONS_DDL = """
CREATE TABLE IF NOT EXISTS interactions (
    platform          VARCHAR   NOT NULL,
    action            VARCHAR   NOT NULL,
    actor_id          VARCHAR   NOT NULL,
    actor_handle      VARCHAR,
    target_id         VARCHAR   NOT NULL,
    target_author_id  VARCHAR,
    ts                TIMESTAMPTZ NOT NULL,
    target_ts         TIMESTAMPTZ
);
"""

INTERACTION_COLUMNS = (
    "platform",
    "action",
    "actor_id",
    "actor_handle",
    "target_id",
    "target_author_id",
    "ts",
    "target_ts",
)


def to_row(i: Interaction) -> tuple:
    """Aplana una interacción al orden de columnas de `INTERACTION_COLUMNS`."""
    return (
        i.platform.value,
        i.action.value,
        i.actor_id,
        i.actor_handle,
        i.target_id,
        i.target_author_id,
        i.ts,
        i.target_ts,
    )
