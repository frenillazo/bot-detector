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

### 2. Ponderación IDF

Cada mensaje se pondera por `log(1 + n_actores / n_que_lo_amplificaron)`.

Coincidir en un mensaje viral no es evidencia: lo amplificó medio país. Coincidir en uno oscuro sí lo es. Sin esta ponderación, dos cuentas orgánicas poco activas que solo tocaron lo más popular salen con similitud 1,0 y acaban señaladas.

### 3. Umbral por modelo nulo

Aquí está la diferencia principal con las herramientas que fijan el umbral a ojo (0,5; 0,8; el percentil 99...). Ese número arbitrario es por donde se ataca un informe: *"¿por qué 0,8 y no 0,9?"*.

El umbral se deriva de los datos. Se permuta la columna de objetivos del listado de aristas, lo que **conserva de forma exacta tanto lo activo que es cada cuenta como lo popular que es cada mensaje**, y destruye únicamente *con quién coincide cada una*. Se mide qué similitudes produce ese azar y se toma el cuantil 0,999.

El umbral resultante significa algo decible en voz alta: *"solo el 0,1% de los pares de cuentas alcanzaría este solapamiento por casualidad, entre cuentas igual de activas"*.

**Limitación conocida:** la permutación puede generar aristas repetidas, que colapsan a 1. En grafos densos esto adelgaza el nulo y hace el umbral algo conservador — el sentido correcto del error aquí.

### 4. Clustering y calibración a nivel de cluster

Leiden en lugar de Louvain: Louvain produce comunidades internamente desconectadas, artefacto que aquí equivaldría a agrupar cuentas sin evidencia mutua de sincronía.

Y después, el paso que casi todas las implementaciones se saltan. **El umbral de similitud controla el error por par, pero una audiencia de 250 cuentas tiene ~31.000 pares.** Al cuantil 0,999, decenas de parejas lo superan por azar, y el clustering las ensambla en coágulos de 4 a 9 cuentas con toda la apariencia de una campaña.

En validación sintética, esos coágulos hundían la precisión a **0,53 con el recall intacto en 1,00**: la campaña real siempre salía como un cluster grande y limpio, y todo el error venía de esos grupitos.

Un cluster se marca solo si cumple **los tres** criterios:

| Criterio | Descarta |
|---|---|
| **Masa de evidencia** ≥ 10 × la máxima que produce el nulo | Coágulos pequeños y fortuitos |
| **Tamaño** ≥ 3 | Parejas |
| **Densidad** ≥ 0,5 | Comunidades grandes pero laxas |

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

Ejecutar `pytest tests/test_detection.py`. Sobre audiencias sintéticas con verdad terreno, semillas no usadas en el desarrollo:

| Condición | Precisión | Recall |
|---|---|---|
| Fidelidad 1,0 | 1,00 | 1,00 |
| Fidelidad 0,9 | 1,00 | 1,00 |
| Fidelidad 0,7 | 1,00 | 0,42 |
| Fidelidad 0,5 | — | **0,00** |
| Fidelidad 0,3 | — | **0,00** |

| Tamaño de campaña (fidelidad 0,9) | Recall |
|---|---|
| 5 cuentas | **0,00** |
| 10 cuentas | 0,83 |
| ≥20 cuentas | 1,00 |

**Control negativo:** 0 falsos positivos en 20 ejecuciones sobre audiencias 100% orgánicas de 250 cuentas.

`fidelity` es la probabilidad de que una cuenta coordinada amplifique cada mensaje de su repertorio: el mando que simula lo bien que un operador oculta su campaña.

### Los puntos ciegos, dichos claramente

1. **Campañas de menos de 10 cuentas son invisibles.** No hay masa de evidencia suficiente.
2. **Operadores que introducen ruido por debajo de fidelidad 0,5 son invisibles.** Un operador que sepa cómo funciona esta herramienta puede evadirla haciendo que sus cuentas amplifiquen solo la mitad del repertorio, de forma desacoplada.
3. **La herramienta no prueba intención ni autoría.** Detecta sincronía inverosímil. Que un grupo de cuentas actúe coordinadamente no prueba quién las opera ni con qué fin.
4. **Un resultado negativo no prueba limpieza.** Dados los puntos 1 y 2, "no se detectó coordinación" significa exactamente eso, y nunca "no hay coordinación".

Cualquier informe publicado debe incluir esta curva de sensibilidad. Sin ella, no dice cuánta campaña se le escapó.

## Reproducibilidad

Todo informe se ancla al SHA-256 de un snapshot Parquet (`botdetector snapshot`) y a los parámetros de `AnalysisConfig`. Sin ambas cosas, un resultado no es verificable por terceros y no vale como evidencia.

Todas las funciones estocásticas aceptan `seed`.
