# Cuentas grandes: el sesgo de recencia

**Conclusión operativa: en cuentas grandes, los endpoints de interactuantes por publicación de X no están limitados, están estructuralmente ciegos a lo que buscamos. No hay parámetro que lo arregle. Hay que usar otra fuente de datos.**

---

## El hallazgo

X no devuelve 100 interactuantes al azar por publicación: devuelve **los 100 más recientes**. Las granjas actúan rápido, en los primeros segundos tras la publicación. La combinación es peor que un truncado aleatorio, y no por poco.

Escenario simulado de cuenta grande: 60 publicaciones, mediana de **440 interactuantes por publicación**, máximo 2.584. Campaña de 60 cuentas que reacciona en el primer 5% de la ventana temporal. Tope de 100, el de X.

| Régimen | Datos retenidos | **Campaña que sobrevive** | Precisión | Recall |
|---|---|---|---|---|
| Sin tope | 100% | 100% | 1,00 | 1,00 |
| Tope aleatorio | 16% | 22% | — | 0,00 |
| **Tope por recencia (X)** | 16% | **0%** | — | 0,00 |

**Cero.** Ni una sola interacción de la campaña sobrevive al truncado por recencia.

La diferencia entre 22% y 0% es la diferencia entre *perder datos* y *perder exactamente la señal*. Un tope aleatorio conserva una muestra representativa y degrada la sensibilidad. El tope por recencia conserva sistemáticamente a los orgánicos tardíos y elimina a la granja rápida: no reduce la evidencia, la suprime.

## Por qué no aparecía en las curvas anteriores

En [CURVAS.md](CURVAS.md), sobre audiencias de ~250 cuentas, el tope por recencia y el aleatorio daban resultados casi idénticos. La razón es que **el sesgo solo muerde cuando una publicación tiene bastantes más interactuantes que el tope**.

En una cuenta mediana, una publicación con 30 interactuantes y un tope de 100 no se trunca: se observa entera, granja incluida. En una cuenta grande, con 440 interactuantes por publicación, el tope descarta el 77% de cada lista, y descarta por el extremo temprano.

Dicho de otro modo: **el sesgo de recencia es un problema exclusivo de las cuentas grandes, que son precisamente las que interesa analizar.** Validar la herramienta solo a escala pequeña lo habría ocultado por completo.

## Qué hacer

**No usar `liking_users` ni `retweeted_by` en cuentas grandes.** Ni con el tope de 100, ni con ningún tope. El problema no es la cantidad de datos sino su sesgo, y ningún ajuste de parámetros corrige un sesgo sistemático en contra de la señal.

Las fuentes enumerables no tienen este problema, porque devuelven **publicaciones**, no listas truncadas de interactuantes:

| Fuente | Vía | Truncado por recencia |
|---|---|---|
| Retweets como publicaciones | búsqueda con `is:retweet` | No |
| Quote tweets | búsqueda por URL del original | No |
| Respuestas | búsqueda por `conversation_id` | No |
| Likes | `liking_users` | **Sí, y letal** |
| Retweeters | `retweeted_by` | **Sí, y letal** |

Las tres primeras están sujetas a la ventana temporal del nivel de acceso —régimen `target_subset` en [CURVAS.md](CURVAS.md)—, que degrada la sensibilidad pero **no sesga contra la campaña**: precisión 1,00 en toda la curva, recall utilizable hasta el 30% de cobertura.

Esto refuerza, ahora con medición y no por intuición, la decisión de diseño tomada al principio del proyecto.

## Coste computacional a escala

La proyección actor × actor crece con el cuadrado del número de cuentas. Con 3.060 cuentas sobre 60 publicaciones salen **9,4 millones de pares**, y casi todos comparten al menos dos publicaciones porque hay muy pocas publicaciones donde repartirse.

Dos optimizaciones, ambas en `coordination/validated.py`:

1. **Deduplicación de p-valores.** El p-valor depende solo de la terna (coincidencias, k_i, k_j) y el test es simétrico. Con pocas publicaciones hay pocas ternas distintas: se calcula una vez por terna y se reparte. La ganancia crece justo donde hace falta.

2. **Permutaciones adaptativas.** El rigor del umbral max-T depende de `permutaciones x pares`. En una proyección de 9,4 millones de pares, una sola permutación ya aporta más contrastes nulos que 40 en una audiencia pequeña. Se fija un presupuesto de contrastes y se derivan las permutaciones, con suelo de 5.

## Limitaciones de este análisis

1. **`campaign_speed` es un supuesto.** Se modela la campaña actuando en el primer 5% de la ventana. Es coherente con lo documentado sobre granjas reales, pero no está medido sobre datos reales. Una granja que introdujera retardos aleatorios para imitar comportamiento humano sería menos vulnerable a este sesgo — y también más difícil de detectar por otros medios.
2. **⚠️ El truncado real de X puede no ser exactamente por recencia. NO ESTÁ VERIFICADO.**

   Se ha modelado según lo documentado públicamente, pero no se ha contrastado contra X. **Todo el argumento de esta página descansa en ese supuesto**, y con él la decisión de no usar `liking_users` ni `retweeted_by`.

   Verificación pendiente, y es la primera tarea en cuanto haya acceso: coger una publicación con miles de interacciones, pedir la lista truncada, y comprobar si los devueltos son los más recientes, los más antiguos o una muestra. Si el truncado resulta ser otro, hay que rehacer la conclusión sobre qué fuente de datos usar.
3. **Escenario único.** Un solo tamaño de cuenta grande. La transición entre "el tope no muerde" y "el tope mata la señal" depende de la razón entre interactuantes por publicación y el tope, y no está caracterizada en detalle.
