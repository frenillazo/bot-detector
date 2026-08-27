# Curvas de degradación por muestreo

**Qué se puede afirmar con datos parciales, y a partir de qué punto no se puede afirmar nada.**

Reproducible con `botdetector curve --regime <régimen>`. Cifras medidas con el detector actual (test hipergeométrico calibrado por permutación): 10 audiencias sintéticas por punto, fidelidad 0,9, campaña de 30 cuentas sobre 200 orgánicas y 300 publicaciones. Semillas 20–29, no usadas en el desarrollo.

---

## Por qué estas curvas se midieron dos veces

La primera versión de este documento describía un detector distinto —coseno con umbral calibrado por permutación— y sus números eran mucho peores. El cambio de criterio estadístico no fue una optimización menor:

| | Coseno | Hipergeométrico |
|---|---|---|
| Uniforme, 80% datos | recall 0,45 | **recall 1,00** |
| Tope por publicación, cap 20 | recall 0,00 | **recall 1,00** |
| Subconj. publicaciones, 34% | **precisión 0,00** | **precisión 1,00** |
| Campañas de 8 cuentas | recall 0,10 | **recall 1,00** |

El motivo está en `coordination/validated.py`: **el coseno no distingue "2 de 2 compartidos" de "40 de 40". Ambos valen 1,0.** Con datos completos rara vez importa; con observación parcial fabrica clusters de cuentas reales.

---

## El resultado que gobierna la recolección

> **A igual cantidad de datos retenidos, el recall varía mucho según *cómo* se hayan perdido.**

La señal de coordinación no vive en las interacciones sino en los **pares de interacciones que comparten publicación**. Para observar un coengagement hay que capturar las dos puntas. Bajo muestreo uniforme a tasa *p*, cada par sobrevive con probabilidad *p²*: el volumen cae linealmente, la evidencia al cuadrado.

Por eso el muestreo uniforme es, con diferencia, el peor régimen — y por eso los regímenes que conservan cuentas o publicaciones **enteras** aguantan mucho más.

---

## Régimen 1 · Muestreo uniforme

Cada interacción se observa con probabilidad *p*.

| Retención | Precisión | Recall | Tasa de detección |
|---|---|---|---|
| 100% | 1,00 | 1,00 | 100% |
| 90% | 1,00 | 1,00 | 100% |
| 80% | 1,00 | 1,00 | 100% |
| 70% | 1,00 | 0,91 | 100% |
| 60% | 1,00 | 0,18 | 60% |
| 50% | 1,00 | 0,07 | 20% |
| ≤30% | — | 0,00 | 0% |

Acantilado entre el 70% y el 60%, consecuencia directa del efecto *p²*. **Suelo: 70%.**

## Régimen 2 · Subconjunto de cuentas, actividad completa

Partir de un censo —seguidores enumerados, lista previa— y recolectarlo entero.

| Retención | Precisión | Recall | Tasa de detección |
|---|---|---|---|
| 100% | 1,00 | 1,00 | 100% |
| 79% | 1,00 | 0,79 | 100% |
| 60% | 1,00 | 0,62 | 100% |
| 51% | 1,00 | 0,53 | 100% |
| 42% | 1,00 | 0,44 | 100% |
| 31% | 0,96 | 0,31 | 90% |
| 20% | 0,93 | 0,21 | 100% |

Degradación lineal: si las dos cuentas de un par están en la muestra, el par se observa entero. Por debajo del 40% la precisión empieza a ceder. **Suelo: 40%.**

> **Ojo con el sesgo de selección.** Si el censo se construyó a partir de sospechas previas, el muestreo ya viene contaminado por la hipótesis que se quiere contrastar. Esta curva mide la pérdida estadística, no ese sesgo, que ninguna curva arregla.

## Régimen 3 · Subconjunto de publicaciones, completas

Ventana temporal acotada, tope de publicaciones por consulta, presupuesto agotado. **Es el régimen de la búsqueda de X.**

| Retención | Precisión | Recall | Tasa de detección |
|---|---|---|---|
| 100% | 1,00 | 1,00 | 100% |
| 80% | 1,00 | 1,00 | 100% |
| 57% | 1,00 | 1,00 | 100% |
| 49% | 1,00 | 1,00 | 100% |
| 43% | 1,00 | 0,98 | 100% |
| 34% | 1,00 | 0,93 | 100% |
| 23% | 1,00 | 0,59 | 90% |

**Aquí estaba el peligro, y está muy reducido pero no eliminado.** Con el criterio de coseno, este era el único régimen donde los datos parciales no dejaban ciego sino **equivocado**: al 20% de cobertura, 1 de cada 40 audiencias puramente orgánicas producía un falso cluster de **27 cuentas reales**.

Control negativo con el criterio actual, 50 semillas por punto:

| Cobertura | Ejecuciones con falso positivo | Tamaño del cluster falso |
|---|---|---|
| 50% | 2 / 50 | 3 cuentas |
| 30% | 1 / 50 | 3 cuentas |
| 20% | 0 / 50 | — |

> **Corrección.** Una versión anterior de este documento afirmaba que el modo de fallo estaba eliminado, basándose en 40 semillas donde salió 0/40. Al ampliar a 50 semillas distintas aparecen falsos positivos residuales en el 2–4% de las ejecuciones. La afirmación era demasiado fuerte para la evidencia que la sostenía.

Lo que sí cambia es la **magnitud**: los falsos clusters residuales tienen 3 cuentas, el mínimo que el detector podía emitir, frente a los 27 del criterio anterior. Un falso positivo de 3 cuentas en una audiencia de 250 es un artefacto detectable por inspección; uno de 27 se parece a un hallazgo.

Y esa regularidad da la solución. En 500 ejecuciones, los **6** falsos clusters observados eran **todos** de tamaño exactamente 3. Por eso `min_cluster_size` pasó de 3 a 5: los elimina por construcción, al coste de perder las campañas de 3 y 4 cuentas —que solo se detectaban el 48% de las veces—. Las tablas de esta página se midieron con el suelo antiguo de 3, así que representan el **peor caso**.

**Suelo: 30%.** Y a diferencia del resto de regímenes, aquí el suelo no basta: cualquier resultado obtenido bajo cobertura parcial de publicaciones debe inspeccionarse manualmente si el cluster es pequeño.

## Régimen 4 · Tope de interactuantes por publicación

Como mucho *N* interactuantes por publicación, elegidos al azar. El endpoint `liking_users` de X devuelve un máximo de 100.

| Tope | Retención | Precisión | Recall | Tasa de detección |
|---|---|---|---|---|
| 100 | 94% | 1,00 | 1,00 | 100% |
| 40 | 81% | 1,00 | 1,00 | 100% |
| 25 | 70% | 1,00 | 1,00 | 100% |
| 20 | 59% | 1,00 | 1,00 | 100% |
| 15 | 47% | 1,00 | 0,38 | 100% |
| 12 | 40% | 1,00 | 0,15 | 60% |
| ≤6 | ≤25% | — | 0,00 | 0% |

Lo que importa no es el tope absoluto sino **su razón con el grado típico de las publicaciones**. **Suelo: 55%.**

---

## Suelos de cobertura, aplicados en código

`validation/curves.py`, consultables con `is_publishable(regime, coverage)`. Criterio: menor cobertura a la que la precisión sigue en 1,00 y el recall supera 0,5.

| Régimen | Suelo | Suelo anterior (coseno) |
|---|---|---|
| `uniform` | 70% | 90% |
| `actor_subset` | 40% | 20% |
| `target_subset` | 30% | 40% (y *falsificable*) |
| `per_target_cap` | 55% | 80% |

Por debajo del suelo el detector queda **ciego**: un resultado negativo no significa nada, pero un positivo sigue siendo fiable. Con el criterio actual ya no existe ningún régimen que produzca falsedades por falta de cobertura.

---

## Lo que esto permite afirmar, y lo que no

**Se puede afirmar:**

> *"Si esta herramienta detecta coordinación, la detección es fiable."* Precisión 1,00 en 200 ejecuciones con datos completos (40 semillas × 5 niveles de fidelidad, desviación típica 0,000), y 1,00 en prácticamente toda la superficie de cobertura parcial.

**No se puede afirmar:**

> *"No hemos detectado coordinación, luego no la hay."* Nunca, y menos con cobertura parcial.

**Toda cifra publicada debe ir acompañada de:** el régimen de observación y la cobertura estimada, el veredicto de `is_publishable()`, y esta curva.

---

## Limitaciones de esta validación

1. **Es sintética.** Las audiencias reales tienen homofilia, comunidades temáticas y correlación temporal que el generador no reproduce. Los suelos reales son probablemente más exigentes.
2. **Un solo tamaño de campaña** en las curvas: 30 cuentas sobre 200 orgánicas.
3. **Regímenes puros.** Una recolección real los combina, y los efectos se acumulan de forma previsiblemente peor que aditiva.
4. **Escala pequeña.** Las curvas se miden sobre audiencias de ~250 cuentas y 300 publicaciones. El comportamiento con cuentas grandes se trata aparte en [ESCALA.md](ESCALA.md).
