# Curvas de degradación por muestreo

**Qué se puede afirmar con datos parciales, y a partir de qué punto no se puede afirmar nada.**

Reproducible con `botdetector curve --regime <régimen>`. Las cifras de abajo: 10 audiencias sintéticas por punto, fidelidad 0,9, campaña de 30 cuentas sobre 200 orgánicas y 300 publicaciones. Semillas 20–29, no usadas en el desarrollo del motor.

---

## El resultado que cambia el diseño de la recolección

> **A igual cantidad de datos retenidos (~80%), el recall varía entre 0,45 y 0,87 según *cómo* se hayan perdido.**

La forma de perder los datos importa más que la cantidad. La razón es geométrica: la señal de coordinación no vive en las interacciones, vive en los **pares de interacciones que comparten publicación**. Para observar un coengagement hay que capturar las dos puntas. Bajo muestreo uniforme a tasa *p*, cada par sobrevive con probabilidad *p²*: el volumen de datos cae linealmente, la evidencia cae al cuadrado.

Por eso "tenemos el 50% de los datos" suena tranquilizador y significa en realidad el 25% de la evidencia.

---

## Régimen 1 · Muestreo uniforme

Cada interacción se observa con probabilidad *p*. El caso de referencia: pierde señal pero no la deforma.

| Retención | Precisión | Recall | Tasa de detección |
|---|---|---|---|
| 100% | 1,00 | 1,00 | 100% |
| 90% | 1,00 | 1,00 | 100% |
| 80% | 1,00 | 0,45 | 50% |
| 70% | — | 0,00 | 0% |
| ≤60% | — | 0,00 | 0% |

**Acantilado entre el 90% y el 70%.** Es mucho más abrupto de lo que la intuición sugiere, y es la consecuencia directa del efecto *p²*.

---

## Régimen 2 · Subconjunto de cuentas, actividad completa

Se observa una fracción de las cuentas, pero todo lo que hacen. Corresponde a partir de un censo —seguidores enumerados, una lista previa— y recolectarlo entero.

| Retención | Precisión | Recall | Tasa de detección |
|---|---|---|---|
| 100% | 1,00 | 1,00 | 100% |
| 79% | 1,00 | 0,79 | 100% |
| 60% | 1,00 | 0,62 | 100% |
| 51% | 1,00 | 0,53 | 100% |
| 42% | 1,00 | 0,44 | 100% |
| 31% | 1,00 | 0,31 | 90% |
| 20% | 1,00 | 0,17 | 70% |

**El régimen más benigno con diferencia.** Degradación lineal, no cuadrática: si las dos cuentas de un par están en la muestra, el par se observa entero. Con solo el 20% de las cuentas todavía detecta algo en 7 de cada 10 audiencias, y nunca se equivoca.

> **Pero cuidado con el sesgo de selección.** Si el censo se construyó a partir de sospechas previas, el muestreo ya viene contaminado por la hipótesis que se quiere contrastar. Esta curva mide la pérdida estadística, no ese sesgo, que es un problema distinto y que ninguna curva arregla.

---

## Régimen 3 · Subconjunto de publicaciones, completas

Se observa una fracción de las publicaciones, pero todo su engagement. Corresponde a los límites de la búsqueda: ventana temporal acotada, tope de publicaciones por consulta, presupuesto agotado.

| Retención | Precisión | Recall | Tasa de detección |
|---|---|---|---|
| 100% | 1,00 | 1,00 | 100% |
| 80% | 1,00 | 1,00 | 100% |
| 57% | 1,00 | 0,20 | 20% |
| 49% | 1,00 | 0,10 | 10% |
| 43% | **0,50** | 0,09 | 20% |
| 34% | **0,00** | 0,00 | 10% |
| 23% | **0,00** | 0,00 | 10% |

### ⚠️ Este es el único régimen que puede hacerte publicar una falsedad

En todos los demás, los datos parciales te dejan **ciego**. Aquí te dejan **equivocado**.

Comprobación específica sobre audiencias **100% orgánicas**, sin ninguna campaña inyectada, 40 semillas por punto. Cualquier detección es un falso positivo puro:

| Régimen | Cobertura | Ejecuciones con falso positivo |
|---|---|---|
| target_subset | 100% | 0 / 40 |
| target_subset | 60% | 0 / 40 |
| target_subset | 40% | 0 / 40 |
| target_subset | 30% | 0 / 40 |
| **target_subset** | **20%** | **1 / 40 — cluster falso de 27 cuentas** |
| uniform | 60% / 30% | 0 / 40 |
| actor_subset | 60% / 30% | 0 / 40 |
| per_target_cap | cap 25 / cap 10 | 0 / 40 |

El mecanismo: al observar solo una fracción de las publicaciones, cuentas orgánicas que coincidieron únicamente en las publicaciones observadas parecen perfectamente correlacionadas. Y el modelo nulo se calcula sobre la matriz **observada**, así que no sabe nada de las publicaciones que faltan y no puede corregir el efecto.

**Y este es exactamente el régimen de la búsqueda de X.** Ventana temporal acotada, tope de publicaciones recuperables. Es el que más va a aplicarte y es el más peligroso.

---

## Régimen 4 · Tope de interactuantes por publicación — **el régimen de X**

Como mucho *N* interactuantes por publicación. El endpoint `liking_users` de X devuelve un máximo de 100, para siempre y sin paginación.

| Tope | Retención | Precisión | Recall | Tasa de detección |
|---|---|---|---|---|
| 100 | 94% | 1,00 | 1,00 | 100% |
| 40 | 81% | 1,00 | 0,87 | 90% |
| 25 | 70% | 1,00 | 0,10 | 10% |
| 20 | 59% | — | 0,00 | 0% |
| ≤15 | ≤47% | — | 0,00 | 0% |

**Acantilado entre el tope 40 y el 25.** No es muestreo uniforme: las publicaciones poco populares se observan íntegras y las virales se truncan. Como las virales son las que más pares de coengagement generan, el truncado se ceba con la parte del grafo que más evidencia aporta.

Lo que importa no es el número absoluto sino **la razón entre el tope y el grado típico de las publicaciones**. En estas audiencias sintéticas el grado mediano ronda las 30–40 interacciones, así que un tope de 100 no muerde. Extrapolando: el tope real de X (100) deja de morder cuando las publicaciones analizadas tienen menos de ~100 interactuantes, y se vuelve inútil cuando tienen miles.

> **Conclusión operativa para X:** el tope de 100 es inofensivo en cuentas medianas y letal en cuentas grandes — que son justo las que interesa analizar. Confirma la decisión de construir sobre retweets, quotes y respuestas vía búsqueda, que sí son enumerables.

---

## Suelos de cobertura, aplicados en código

Implementados en `validation/curves.py` como `MINIMUM_COVERAGE`, y consultables con `is_publishable(regime, coverage)`:

| Régimen | Suelo | Naturaleza del suelo |
|---|---|---|
| `uniform` | 90% | Por debajo, ciego |
| `actor_subset` | 20% | Por debajo, ciego |
| `target_subset` | **40%** | Por debajo, **puede fabricar clusters** |
| `per_target_cap` | 80% | Por debajo, ciego |

La distinción entre los dos tipos de suelo no es cosmética y la función devuelve motivos distintos:

- **Ciego** → un resultado negativo no significa nada, pero un positivo sigue siendo fiable.
- **Falsificable** → no publicar, ni siquiera con advertencias.

---

## Lo que esto permite afirmar, y lo que no

**Se puede afirmar:**

> *"Si esta herramienta detecta coordinación, la detección es fiable."* La precisión se mantiene en 1,00 en todos los regímenes y a todos los niveles de cobertura, con la única excepción de `target_subset` por debajo del 40%. Los datos parciales, en general, no te hacen mentir.

**No se puede afirmar:**

> *"No hemos detectado coordinación, luego no la hay."* Nunca, pero mucho menos con cobertura parcial. Con el 70% de los datos bajo muestreo uniforme, el detector es completamente ciego a una campaña de 30 cuentas que vería sin problema con el 90%.

**Toda cifra publicada debe ir acompañada de:**

1. El régimen de observación y la cobertura estimada
2. El veredicto de `is_publishable()`
3. Esta curva, o la que corresponda al régimen usado

---

## Limitaciones de esta validación

1. **Es sintética.** Las audiencias orgánicas se generan con popularidad de ley de potencias y selección independiente. Las audiencias reales tienen homofilia, comunidades temáticas y correlación temporal que el generador no reproduce. Los suelos reales son probablemente **más exigentes** que estos.
2. **Un solo tamaño de campaña.** Todo con 30 cuentas coordinadas sobre 200 orgánicas. Campañas proporcionalmente menores necesitarán más cobertura.
3. **Regímenes puros.** Una recolección real los combina: ventana temporal *más* tope por publicación *más* pérdidas de conexión. Los efectos se acumulan y previsiblemente de forma peor que aditiva.
4. **Sin dimensión temporal.** El muestreo se modela sobre la matriz de interacciones, no sobre la serie temporal. Un sesgo de recencia —observar solo las interacciones más recientes de cada publicación, que es lo que de hecho hace X— no está modelado y podría comportarse peor que el truncado aleatorio que aquí se simula.

El punto 4 es el hueco más relevante y el siguiente candidato a cerrarse.
