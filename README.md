# bot-detector

**Mide qué parte de la audiencia que amplifica a una cuenta se comporta de forma coordinada, y cuánto se desvía eso de lo que hacen cuentas comparables.**

No es un clasificador de bots. La pregunta "¿esta cuenta es un bot?" es la equivocada: se responde mal, envejece rápido frente a bots con LLM detrás, y produce acusaciones individuales que no se sostienen. La pregunta que responde esta herramienta es otra:

> ¿La audiencia que amplifica a esta cuenta actúa de forma tan sincronizada que el azar no lo explica, comparada con audiencias de cuentas equivalentes?

Solo quien miente necesita que sus mensajes *parezcan* mayoritarios. Esta herramienta mide esa fabricación de mayoría aparente.

## Estado

Motor funcional y validado por inyección sintética, incluidas curvas de degradación por cobertura parcial y a escala de cuenta grande. El colector de Bluesky recolecta datos reales; el de X está especificado pero sin implementar (ver [ROADMAP](docs/ROADMAP.md)).

## Qué hace, concretamente

```
interacciones → matriz bipartita → umbral por modelo nulo → grafo → clusters → IIA
```

1. **Normaliza** cualquier plataforma a una tupla común: `(actor, acción, objetivo, instante)`.
2. **Construye** la matriz binaria actor × mensaje. Solo eso: sin contenido, sin metadatos, sin modelos de lenguaje.
3. **Contrasta cada par** con un test hipergeométrico: dadas dos cuentas con k_i y k_j interacciones sobre un universo de N publicaciones, ¿qué probabilidad hay de que coincidieran tanto por azar?
4. **Deriva el umbral de los datos**, no del gusto del analista: aleatoriza el grafo preservando ambas secuencias de grado y exige superar el p-valor más extremo que produce el azar (max-T de Westfall-Young).
5. **Agrupa** con Leiden y vuelve a calibrar, ahora a nivel de cluster.
6. **Agrega** en el Índice de Inautenticidad de Audiencia, siempre con intervalo de confianza y siempre relativo a cuentas de control.

### Por qué no usa similitud coseno

> **El coseno no distingue "2 de 2 compartidos" de "40 de 40". Ambos valen 1,0.**

Con datos completos rara vez importa. Con observación parcial es letal: en validación, 27 cuentas orgánicas con 2 interacciones observadas coincidieron en los mismos 2 posts, salieron con similitud 1,000 y el detector las marcó como granja. Eran personas.

El p-valor hipergeométrico separa esos dos casos por cuarenta órdenes de magnitud. El cambio de estadístico mejoró todo a la vez: recall de 0,45 a 1,00 con el 80% de los datos, campañas de 8 cuentas de invisibles a detectables, y eliminó el único modo de fallo que producía acusaciones falsas.

## Instalación

```bash
python -m venv .venv && .venv/Scripts/activate && pip install -e ".[dev]"
```

## Uso

Recolectar del firehose de Bluesky — gratuito, sin autenticación, cobertura del 100%:

```bash
botdetector collect --minutes 30
```

Perfilar la audiencia de una cuenta:

```bash
botdetector report did:plc:ejemplo --actions repost,quote
```

Congelar un snapshot verificable con su hash:

```bash
botdetector snapshot
```

## Las tres reglas que no se negocian

Están incrustadas en el código, no solo en la documentación.

**1. Ningún número se publica en absoluto.** `relative_to_baseline()` lanza `ValueError` si no le pasas cuentas de control. No es un descuido de diseño: un clasificador con un 5% de falsos positivos devuelve "5% de bots" sobre una audiencia perfectamente limpia. Sin línea base comparativa, el número no significa nada.

**2. Nunca se señala a cuentas individuales.** La unidad de análisis es la audiencia agregada. En un agregado, el error del clasificador se promedia; en un señalamiento individual, se convierte en una acusación falsa contra una persona real.

**3. El error se inclina hacia el falso negativo.** Umbrales conservadores, modelos nulos que sobreestiman ligeramente el azar. `test_no_false_positives_on_purely_organic_audience` es el test más importante del repositorio. Es mejor no detectar una campaña que marcar a alguien por error.

## Por qué no mide "% de likes que son bots"

Porque en X **no se puede**, y decir lo contrario sería exactamente el tipo de afirmación sin respaldo que la herramienta pretende combatir.

El endpoint `liking_users` devuelve un máximo de **100 usuarios por publicación, para siempre**, sin paginación. Un tweet con 40.000 likes expone 100.

Y esos 100 no son aleatorios: son **los más recientes**. Como las granjas actúan en los primeros segundos, en cuentas grandes el tope no degrada la muestra, la invierte:

| Cuenta grande, 440 interactuantes/publicación | Campaña que sobrevive |
|---|---|
| Tope aleatorio de 100 | 22% |
| **Tope por recencia (el real)** | **0%** |

No es una limitación de volumen que se compense recolectando más. Es un sesgo sistemático en contra de la señal buscada, y ningún parámetro lo corrige. Ver [docs/ESCALA.md](docs/ESCALA.md).

Lo que sí sirve —retweets, quotes y respuestas vía búsqueda— devuelve publicaciones, no listas truncadas de interactuantes, y trae marca temporal por interacción. Ver [`collectors/x.py`](src/botdetector/collectors/x.py).

## Validación

El motor se valida por inyección sintética sobre audiencias con verdad terreno conocida, barriendo el parámetro `fidelity` (cuánto ruido introduce el operador para evadir detección):

```bash
pytest tests/test_detection.py -v
```

La curva resultante —recall frente a fidelidad y tamaño de campaña— debe acompañar a cualquier informe publicado. Un resultado sin su curva de sensibilidad no dice cuánta campaña se le escapó.

Y la degradación por cobertura parcial, que es lo que determina qué se puede afirmar con datos incompletos:

```bash
botdetector curve --regime per_target_cap
```

Hallazgo principal: **a igual cantidad de datos retenidos, el recall varía mucho según cómo se hayan perdido**. La forma importa más que la cantidad, porque la señal vive en los *pares* de interacciones. Ver [docs/CURVAS.md](docs/CURVAS.md).

### Dónde la precisión no es 1,00

Con datos completos y campañas de ≥10 cuentas: 0 falsos positivos en 50 ejecuciones. Pero hay dos zonas donde el detector puede equivocarse, y conviene conocerlas:

- **Fidelidad ≤0,3.** Casi nunca detecta nada (4% de las ejecuciones), pero lo poco que detecta es falso.
- **Cobertura parcial de publicaciones.** Quedan falsos positivos residuales en el 2–4% de las ejecuciones. Todos, sin excepción, del tamaño mínimo permitido: es la firma que permite reconocerlos. Por eso `min_cluster_size` está en 5 y no en 3.

Cifras completas en [METHODOLOGY.md](METHODOLOGY.md).

## Documentación

- [METHODOLOGY.md](METHODOLOGY.md) — qué se mide, por qué, y qué NO se puede concluir
- [ETHICS.md](ETHICS.md) — límites de publicación, RGPD, riesgo de difamación
- [docs/ROADMAP.md](docs/ROADMAP.md) — fases y acceso a datos vía Artículo 40 del DSA

## Referencias

- Jahn & Rendsvig, [*Towards Detecting Inauthentic Coordination in Twitter Likes Data*](https://arxiv.org/abs/2305.07384) — el enfoque minimalista sobre la matriz binaria
- [*Detection and Characterization of Coordinated Online Behavior: A Survey*](https://arxiv.org/html/2408.01257v1)
- Feng et al., [*TwiBot-22*](https://arxiv.org/abs/2206.04564) — benchmark de referencia; los mejores modelos son basados en grafos
- [Jetstream / AT Protocol](https://bsky.network/docs/jetstream/)

## Licencia

AGPL-3.0. Elegida deliberadamente: quien despliegue esta herramienta como servicio está obligado a publicar su código. Un instrumento que produce acusaciones públicas no puede ejecutarse en una versión cerrada y no auditable.
