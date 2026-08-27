# Metodología

## La pregunta

No: *"¿esta cuenta es un bot?"*

Sí: *"¿la audiencia que amplifica a esta cuenta actúa de forma tan sincronizada que el azar no lo explica, comparada con audiencias de cuentas equivalentes?"*

El cambio no es cosmético. Responde a tres problemas de la primera pregunta:

1. **"Bot" es la categoría equivocada.** Buena parte de las operaciones documentadas se apoya en cuentas operadas por personas o semiautomatizadas. Un clasificador de bots las puntúa como humanas y concluye "audiencia limpia". Falso negativo catastrófico.
2. **Un número binario oculta el error.** Un clasificador con 5% de falsos positivos devuelve "5% de bots" sobre una audiencia perfectamente limpia.
3. **Es difamable.** "Esta cuenta es un bot" es una afirmación sobre una persona identificable. "Esta audiencia presenta 4,2× más coengagement sincronizado que audiencias comparables" es una afirmación estadística sobre un agregado.

## El pipeline

```
interacciones → matriz bipartita → umbral nulo → grafo → clusters → calibración → IIA
```

### 1. Matriz bipartita

Solo la matriz binaria actor × mensaje. Sin contenido, sin metadatos, sin modelos de lenguaje. Siguiendo a [Jahn & Rendsvig](https://arxiv.org/abs/2305.07384).

Las interacciones repetidas colapsan a 1: interesa *si* una cuenta amplificó un mensaje, no cuántas veces. Contar repeticiones daría peso desproporcionado a las cuentas más activas.

### 2. Test hipergeométrico por par

**No se usa similitud coseno.** El motivo es un fallo concreto y medido:

> El coseno no distingue *"2 de 2 compartidos"* de *"40 de 40 compartidos"*. Ambos valen 1,0.

Con datos completos rara vez importa, porque las cuentas tienen muchas interacciones. Con observación parcial es letal: observando el 20% de las publicaciones, 27 cuentas orgánicas con exactamente 2 interacciones observadas coincidieron en los mismos 2 posts y salieron con similitud 1,000. El detector las marcó como granja. Eran personas.

El test hipergeométrico hace la pregunta correcta: dadas dos cuentas que amplificaron k_i y k_j publicaciones de un universo de N, ¿qué probabilidad hay de que compartieran al menos c por azar?

```
p = P(X >= c),  X ~ Hipergeométrica(N, k_i, k_j)
```

Para el caso de arriba, p ≈ 3,3e-3. Para una granja real —40 de 40 sobre 300 publicaciones— p ≈ 1e-50. Cuarenta y tantos órdenes de magnitud separan lo que el coseno igualaba.

Referencia: Tumminello et al., *Statistically Validated Networks in Bipartite Complex Systems*, PLOS ONE, 2011.

> **Consecuencia práctica:** el filtro `min_target_engagement` debe quedarse en 1. Las publicaciones con un solo interactuante son parte del universo N, y N es justo lo que distingue "2 de 2 sobre 300 publicaciones" de "2 de 2 sobre 25". Subirlo a 2 elimina 55 aristas de 2.398 y hunde la precisión de 1,00 a 0,88.

### 3. Umbral calibrado por permutación (max-T)

El umbral **no** se fija con Bonferroni, y tampoco a ojo. Dos problemas simultáneos:

**El modelo está mal especificado.** La hipergeométrica asume que cada cuenta elige publicaciones equiprobablemente. Falso: la popularidad sigue una ley de potencias. Con Bonferroni salían falsos positivos en 25 de 30 audiencias puramente orgánicas, todos por coincidencias en publicaciones que había tocado casi todo el mundo.

Modelar la popularidad analíticamente tampoco funciona: la propia campaña infla el grado de sus objetivos, así que se estimaría el nulo con datos que contienen la señal, y el nulo declararía esperable justo lo que se busca.

**Los contrastes no son independientes.** Los p-valores de pares que comparten una cuenta están correlacionados, y Bonferroni supone que no.

La permutación de la columna de objetivos conserva **ambas** secuencias de grado —lo activa que es cada cuenta y lo popular que es cada publicación— y destruye solo *con quién coincide cada una*. Tomar el mínimo p-valor que produce el azar es la **corrección max-T de Westfall-Young**, que controla la tasa de error por familia respetando la dependencia real.

Un par se valida si es *más improbable que cualquier cosa que produzca el azar*.

### 4. Clustering y calibración a nivel de cluster

Leiden en lugar de Louvain: Louvain produce comunidades internamente desconectadas, artefacto que aquí equivaldría a agrupar cuentas sin evidencia mutua de sincronía.

Y después, el paso que casi todas las implementaciones se saltan. **Validar aristas no basta: la validación controla el error por arista, pero unas pocas aristas fortuitas todavía se ensamblan en coágulos de 3 a 5 cuentas con toda la apariencia de una campaña.**

Medido: con validación de aristas pero sin esta segunda capa, salían falsos positivos en 9 de 30 audiencias puramente orgánicas. Con ella, 0 de 30.

La segunda capa aplica al nulo **el mismo umbral de validación y el mismo clustering** que a los datos reales, y mide qué masa de evidencia llega a ensamblar el azar.

Un cluster se marca solo si cumple **los tres** criterios:

| Criterio | Descarta |
|---|---|
| **Masa de evidencia** ≥ 10 × la máxima que produce el nulo | Coágulos fortuitos |
| **Tamaño** ≥ 5 | Grupitos, incluidos los falsos positivos residuales |
| **Densidad** ≥ 0,5 | Comunidades grandes pero laxas |

El umbral de tamaño está en 5 y no en 3 por una razón medida: en 500 ejecuciones sobre audiencias puramente orgánicas con cobertura parcial, los 6 falsos clusters que aparecieron eran **todos** de exactamente 3 cuentas. Subir el suelo los elimina y cuesta perder las campañas de 3 y 4 cuentas, que solo se detectaban el 48% de las veces.

Ninguno es redundante. Ni el tamaño ni la densidad separan por sí solos —cuatro cuentas orgánicas coincidentes alcanzan densidad 1,0 igual que una granja—; y la evidencia por sí sola marca comunidades temáticas grandes solo por ser grandes.

La **masa de evidencia** (suma de pesos de las aristas internas) es el estadístico que decide porque crece con el cuadrado del tamaño del grupo: separa una granja de 30 cuentas (~435 pares anómalos) de un coágulo fortuito de 9 (~18) por dos órdenes de magnitud.

El factor de seguridad ×10 y la densidad 0,5 son elecciones **deliberadamente conservadoras**. Sesgan el error hacia el falso negativo.

### 5. Índice de Inautenticidad de Audiencia

| Componente | Qué mide |
|---|---|
| **Cuota de coordinación** | Fracción de interacciones procedentes de clusters marcados |
| **Recurrencia** | Fracción aportada por el 1% de cuentas más repetidas |
| **Gini de audiencia** | Concentración: audiencia amplia y difusa vs. cautiva |
| **Latencia** | Distribución de segundos entre publicación e interacción |

La cuota de coordinación se pondera por interacciones, no por cuentas: 50 cuentas que aportan el 40% de los retweets importan más que 50 que aportan uno cada una.

El intervalo de confianza remuestrea **actores**, no interacciones: las interacciones de una misma cuenta están fuertemente correlacionadas, y tratarlas como independientes produce intervalos artificialmente estrechos.

## Línea base

**Ningún valor absoluto es interpretable.** `relative_to_baseline()` lanza `ValueError` si no recibe controles: la restricción está en el código, no solo aquí.

Para cada cuenta objetivo hacen falta controles emparejados por tamaño de audiencia y temática, incluyendo **cuentas del espectro político opuesto** y cuentas apolíticas. Si la herramienta solo se aplica a un lado, *es* partidista por construcción aunque el algoritmo sea neutral.

Lo que se publica:

> La cuenta X presenta 4,2× más coengagement sincronizado que la mediana de cuentas comparables (IC 95%: 3,1–5,6). El 34% de sus retweets procede de un cluster de 1.847 cuentas cuya masa de evidencia supera en 40× la máxima producida por el modelo nulo.

Lo que no se publica: *"la cuenta X tiene un 60% de bots"*.

## Validación y puntos ciegos

Ejecutar `pytest tests/test_detection.py`. Cifras medidas con la configuración por defecto, 25 semillas por celda.

`fidelity` es la probabilidad de que una cuenta coordinada amplifique cada mensaje de su repertorio: el mando que simula lo bien que un operador oculta su campaña.

| Fidelidad | Precisión | Recall | Detección |
|---|---|---|---|
| 1,0 | 1,00 | 1,00 | 100% |
| 0,9 | 1,00 | 1,00 | 100% |
| 0,8 | 1,00 | 1,00 | 100% |
| 0,7 | 1,00 | 0,99 | 100% |
| 0,6 | 1,00 | 0,76 | 100% |
| 0,5 | 0,99 | 0,13 | 48% |
| 0,4 | 1,00 | 0,03 | 20% |
| 0,3 | **0,00** | 0,00 | 4% |

| Tamaño de campaña (fidelidad 0,9) | Precisión | Recall | Detección |
|---|---|---|---|
| 3 cuentas | 1,00 | 0,48 | 48% |
| 5 cuentas | 0,98 | 0,72 | 72% |
| 8 cuentas | 0,99 | 1,00 | 100% |
| ≥10 cuentas | 1,00 | 1,00 | 100% |

**Controles negativos**, audiencias 100% orgánicas de 250 cuentas, 50 semillas:

| Condición | Ejecuciones con falso positivo |
|---|---|
| Datos completos | **0 / 50** |
| Muestreo uniforme al 50% | 0 / 50 |
| Muestreo uniforme al 30% | 0 / 50 |
| Solo 50% de publicaciones | **2 / 50** |
| Solo 30% de publicaciones | **1 / 50** |
| Solo 20% de publicaciones | 0 / 50 |

### La precisión no es 1,00 en todas partes, y hay que decirlo

Con datos completos y campañas de ≥10 cuentas, sí: 0 falsos positivos en 50 ejecuciones y precisión 1,00. Pero hay dos zonas donde no:

1. **Fidelidad ≤0,3.** El detector casi nunca ve nada (4% de detección), pero lo poco que ve es falso. Un resultado positivo obtenido sobre una campaña que se sospecha muy evasiva merece escrutinio adicional.
2. **Subconjunto de publicaciones al 30–50%.** Quedan falsos positivos residuales en el 2–4% de las ejecuciones. Muy por debajo del criterio anterior de coseno —que llegó a marcar 27 cuentas reales de golpe— pero **no es cero**, y una versión previa de este documento afirmó que sí lo era. Era una afirmación basada en una muestra de 40 semillas que no se sostuvo al ampliarla a 50.

### Cobertura parcial

Ninguna recolección real ve el 100% de las interacciones, y **la forma de perder datos importa más que la cantidad**: a igual retención (~80%), el recall varía entre 0,45 y 0,87 según el régimen. La razón es que la señal vive en los *pares* de interacciones, así que bajo muestreo uniforme a tasa *p* la evidencia cae con *p²* mientras el volumen cae con *p*.

Suelos de cobertura por debajo de los cuales no se publica, aplicados en código (`validation/curves.py`):

| Régimen | Suelo | Por debajo del suelo |
|---|---|---|
| Muestreo uniforme | 90% | Ciego |
| Subconjunto de cuentas | 20% | Ciego |
| **Subconjunto de publicaciones** | **40%** | **Puede fabricar clusters falsos** |
| Tope por publicación (X) | 80% | Ciego |

El tercero es el único régimen donde los datos parciales no te dejan ciego sino **equivocado**, y es precisamente el de la búsqueda de X. Curvas completas y control negativo en [docs/CURVAS.md](docs/CURVAS.md).

### Los puntos ciegos, dichos claramente

1. **Campañas de menos de 10 cuentas son invisibles.** No hay masa de evidencia suficiente.
2. **Operadores que introducen ruido por debajo de fidelidad 0,5 son invisibles.** Un operador que sepa cómo funciona esta herramienta puede evadirla haciendo que sus cuentas amplifiquen solo la mitad del repertorio, de forma desacoplada.
3. **La herramienta no prueba intención ni autoría.** Detecta sincronía inverosímil. Que un grupo de cuentas actúe coordinadamente no prueba quién las opera ni con qué fin.
4. **Un resultado negativo no prueba limpieza.** Dados los puntos 1 y 2, "no se detectó coordinación" significa exactamente eso, y nunca "no hay coordinación". Con cobertura parcial, menos aún: con el 70% de los datos bajo muestreo uniforme el detector es completamente ciego a una campaña que vería sin problema con el 90%.

Cualquier informe publicado debe incluir esta curva de sensibilidad. Sin ella, no dice cuánta campaña se le escapó.

## Reproducibilidad

Todo informe se ancla al SHA-256 de un snapshot Parquet (`botdetector snapshot`) y a los parámetros de `AnalysisConfig`. Sin ambas cosas, un resultado no es verificable por terceros y no vale como evidencia.

Todas las funciones estocásticas aceptan `seed`.
