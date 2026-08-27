"""Colector de X (Twitter).

RESTRICCIÓN CENTRAL, y la razón de que este módulo no recolecte likes
--------------------------------------------------------------------
El endpoint `GET /2/tweets/:id/liking_users` devuelve **como máximo 100 usuarios
por publicación, para siempre**. No hay paginación más allá de ese tope, y los
100 no son una muestra aleatoria. Lo mismo aplica históricamente a
`/retweeted_by`.

Consecuencia: **el "% de likes que son bots" no es medible en X**. Un tweet con
40.000 likes expone 100. Cualquier herramienta que publique ese porcentaje sobre
la API oficial está extrapolando desde una muestra sesgada sin decirlo.

Lo que sí es enumerable, y sobre lo que se construye aquí:

  - retweets como publicaciones      -> búsqueda con `is:retweet`
  - quote tweets                     -> búsqueda por URL del tweet original
  - respuestas                       -> búsqueda por `conversation_id`
  - seguidores                       -> paginable

Estas tres primeras vías, además, traen marca temporal por interacción, que es
exactamente lo que necesita el análisis de sincronía. Los likes no la traen.

Coste (modelo de pago por uso vigente desde el 20 de abril de 2026): del orden de
0,005 USD por lectura de publicación y 0,010 por lectura de usuario, sin tramo
gratuito para nuevas altas. Presupuestar antes de lanzar una recolección amplia.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import AsyncIterator

from botdetector.collectors.base import Collector
from botdetector.schema import Interaction, Platform

API_BASE = "https://api.x.com/2"

# Tope documentado del endpoint de likes. Se mantiene como constante para que
# cualquier intento futuro de recolectar likes tropiece con él de forma explícita.
LIKING_USERS_HARD_CAP = 100


class XCollector(Collector):
    """Recolección vía búsqueda de retweets, quotes y respuestas.

    Pendiente de implementar: requiere credenciales de pago y un presupuesto
    acotado. El esqueleto fija la interfaz y deja documentados los límites para
    que la implementación no derive hacia los likes por comodidad.
    """

    platform = Platform.X

    def __init__(self, bearer_token: str, *, budget_usd: float = 0.0) -> None:
        self.bearer_token = bearer_token
        self.budget_usd = budget_usd
        self._spent_usd = 0.0

    @property
    def coverage(self) -> str:
        return (
            "Cobertura PARCIAL. Likes y retweeters directos están limitados a 100 "
            "usuarios por publicación (tope duro de la API, sin paginación), por lo "
            "que no se recolectan. Se recolectan retweets, quotes y respuestas vía "
            "búsqueda, sujetos a la ventana temporal del nivel de acceso contratado. "
            "Todo resultado debe reportarse como estimación sobre muestra parcial."
        )

    async def stream(
        self,
        *,
        until: dt.datetime | None = None,
        limit: int | None = None,
    ) -> AsyncIterator[Interaction]:
        raise NotImplementedError(
            "XCollector requiere credenciales de pago. Ver docs/ROADMAP.md, fase 3. "
            "Valida primero el motor sobre Bluesky, donde la cobertura es completa."
        )
        yield  # pragma: no cover -- mantiene la firma de generador asíncrono
