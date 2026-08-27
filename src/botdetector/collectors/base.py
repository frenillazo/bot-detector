"""Interfaz común de colectores.

Toda la lógica de análisis vive aguas abajo de esta interfaz. Añadir una
plataforma nueva significa escribir un colector y nada más.
"""

from __future__ import annotations

import abc
import datetime as dt
from collections.abc import AsyncIterator

from botdetector.schema import Interaction, Platform


class Collector(abc.ABC):
    """Fuente de interacciones normalizadas."""

    platform: Platform

    @abc.abstractmethod
    def stream(
        self,
        *,
        until: dt.datetime | None = None,
        limit: int | None = None,
    ) -> AsyncIterator[Interaction]:
        """Emite interacciones hasta agotar la fuente o alcanzar el límite."""
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def coverage(self) -> str:
        """Descripción honesta de qué fracción de la realidad ve este colector.

        No es documentación decorativa: el informe final la cita literalmente.
        Un resultado calculado sobre el 0,25% de los likes debe decirlo en la
        misma página en la que da el número.
        """
        raise NotImplementedError
