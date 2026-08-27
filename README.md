# bot-detector

**Mide qué parte de la audiencia que amplifica a una cuenta se comporta de forma coordinada, y cuánto se desvía eso de lo que hacen cuentas comparables.**

No es un clasificador de bots. La pregunta "¿esta cuenta es un bot?" es la equivocada: se responde mal, envejece rápido frente a bots con LLM detrás, y produce acusaciones individuales que no se sostienen. La pregunta que responde esta herramienta es otra:

> ¿La audiencia que amplifica a esta cuenta actúa de forma tan sincronizada que el azar no lo explica, comparada con audiencias de cuentas equivalentes?

Solo quien miente necesita que sus mensajes *parezcan* mayoritarios. Esta herramienta mide esa fabricación de mayoría aparente.

## Estado

Esqueleto funcional. El motor de coordinación funciona y está validado por inyección sintética; el colector de Bluesky recolecta datos reales; el de X está especificado pero sin implementar (ver [ROADMAP](docs/ROADMAP.md)).

## Qué hace, concretamente

```
interacciones → matriz bipartita → umbral por modelo nulo → grafo → clusters → IIA
```

1. **Normaliza** cualquier plataforma a una tupla común: `(actor, acción, objetivo, instante)`.
2. **Construye** la matriz binaria actor × mensaje. Solo eso: sin contenido, sin metadatos, sin modelos de lenguaje.
3. **Deriva el umbral de los datos**, no del gusto del analista: aleatoriza el grafo preservando los grados y mide qué solapamiento produce el puro azar entre cuentas igual de activas.
4. **Agrupa** con Leiden los pares que superan ese umbral.
5. **Agrega** en el Índice de Inautenticidad de Audiencia, siempre con intervalo de confianza y siempre relativo a cuentas de control.

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

El endpoint `liking_users` de la API de X devuelve un máximo de **100 usuarios por publicación, para siempre**, sin paginación. Un tweet con 40.000 likes expone 100, y no son 100 aleatorios. Cualquier herramienta que publique un porcentaje de likes sobre esa base está extrapolando desde una muestra sesgada.

Lo que sí es enumerable —retweets, quotes y respuestas vía búsqueda— además trae marca temporal por interacción, que es justo lo que necesita el análisis de sincronía. Los likes no la traen. Ver [`collectors/x.py`](src/botdetector/collectors/x.py).

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

Hallazgo principal: **a igual cantidad de datos retenidos, el recall varía entre 0,45 y 0,87 según cómo se hayan perdido**. La forma importa más que la cantidad. Y hay un régimen —observar solo una fracción de las publicaciones, que es el de la búsqueda de X— donde los datos parciales no te dejan ciego sino **equivocado**. Ver [docs/CURVAS.md](docs/CURVAS.md).

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
