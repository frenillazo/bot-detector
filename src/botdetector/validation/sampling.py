"""Regímenes de observación parcial.

Ninguna recolección real ve el 100% de las interacciones. Lo que casi nunca se
dice es que **la forma de perder datos importa más que la cantidad**, y que dos
recolecciones que retienen la misma fracción pueden dar resultados opuestos.

La intuición central: la señal de coordinación no vive en las aristas, vive en
los **pares de aristas** que comparten objetivo. Para observar un coengagement
entre dos cuentas hay que capturar las dos puntas. Bajo muestreo uniforme a tasa
p, cada par sobrevive con probabilidad p², así que la evidencia se desploma
cuadráticamente mientras el volumen de datos solo cae linealmente.

De ahí que un "tenemos el 50% de los datos" suene tranquilizador y signifique en
realidad el 25% de la evidencia.

Los cuatro regímenes implementados corresponden a formas reales de perder datos:

- `uniform`          muestreo aleatorio de interacciones
- `per_target_cap`   tope de N interactuantes por publicación — **el caso de X**
- `actor_subset`     solo se observan algunas cuentas, pero enteras
- `target_subset`    solo se observan algunas publicaciones, pero enteras
"""

from __future__ import annotations

from collections import defaultdict

import numpy as np

Edges = list[tuple[str, str]]


def uniform(edges: Edges, fraction: float, rng: np.random.Generator) -> Edges:
    """Cada interacción se observa con probabilidad `fraction`.

    El caso benigno de referencia. Es el único régimen sin sesgo sistemático:
    pierde señal, pero no la deforma.
    """
    if fraction >= 1.0:
        return list(edges)
    keep = rng.random(len(edges)) < fraction
    return [e for e, k in zip(edges, keep, strict=True) if k]


def per_target_cap(edges: Edges, cap: int, rng: np.random.Generator) -> Edges:
    """Como mucho `cap` interactuantes por publicación.

    **Este es el régimen de X.** El endpoint `liking_users` devuelve un máximo de
    100 usuarios por publicación, para siempre y sin paginación.

    No es muestreo uniforme, y la diferencia es lo que hace que este régimen
    merezca su propia curva: las publicaciones poco populares se observan
    íntegras y las virales se truncan. Como las publicaciones virales son
    precisamente las que más pares de coengagement generan, el truncado se ceba
    con la parte del grafo que más evidencia aporta.
    """
    by_target: dict[str, list[str]] = defaultdict(list)
    for actor, target in edges:
        by_target[target].append(actor)

    out: Edges = []
    for target, actors in by_target.items():
        if len(actors) <= cap:
            out.extend((a, target) for a in actors)
        else:
            chosen = rng.choice(len(actors), size=cap, replace=False)
            out.extend((actors[i], target) for i in chosen)
    return out


def actor_subset(edges: Edges, fraction: float, rng: np.random.Generator) -> Edges:
    """Se observa una fracción de las cuentas, pero su actividad completa.

    Corresponde a partir de un censo de cuentas conocidas —seguidores
    enumerados, una lista previa— y recolectar todo lo suyo.

    Es el régimen más benigno para la coordinación: si las dos cuentas de un par
    están en la muestra, el par se observa entero. La pega es de otro tipo, y
    seria: si el censo se construyó a partir de sospechas previas, el muestreo
    ya viene contaminado por la hipótesis que se quiere contrastar.
    """
    actors = sorted({a for a, _ in edges})
    if fraction >= 1.0:
        return list(edges)
    keep = {a for a, k in zip(actors, rng.random(len(actors)) < fraction, strict=True) if k}
    return [(a, t) for a, t in edges if a in keep]


def target_subset(edges: Edges, fraction: float, rng: np.random.Generator) -> Edges:
    """Se observa una fracción de las publicaciones, pero enteras.

    Corresponde a los límites de la búsqueda: ventana temporal acotada, tope de
    publicaciones recuperables por consulta, presupuesto de API agotado.
    """
    targets = sorted({t for _, t in edges})
    if fraction >= 1.0:
        return list(edges)
    keep = {t for t, k in zip(targets, rng.random(len(targets)) < fraction, strict=True) if k}
    return [(a, t) for a, t in edges if t in keep]


STRATEGIES = {
    "uniform": uniform,
    "actor_subset": actor_subset,
    "target_subset": target_subset,
}
"""Regímenes parametrizados por fracción. `per_target_cap` va aparte: su
parámetro es un tope absoluto, no una fracción."""


def retention(observed: Edges, original: Edges) -> float:
    """Fracción de interacciones efectivamente observadas.

    Se reporta siempre junto al resultado para que los cuatro regímenes se puedan
    comparar sobre un eje común. Sin esto, `cap=30` y `fraction=0.5` no son
    comparables y la curva no dice nada.
    """
    return len(observed) / len(original) if original else 0.0
