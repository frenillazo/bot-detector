# Roadmap

## Fase 1 — Motor sobre Bluesky ✅

Jetstream, DuckDB, matriz bipartita, IDF, umbral nulo, Leiden, calibración a nivel de cluster, IIA. Sin coste de datos y con cobertura del 100%.

## Fase 2 — Validación por inyección sintética ✅

Curvas de precisión/recall frente a fidelidad del operador y tamaño de campaña. Resultados y puntos ciegos en [METHODOLOGY.md](../METHODOLOGY.md).

Pendiente de ampliar:

- [ ] Curva frente a **fracción de datos muestreada**, que es lo que justificará qué se puede afirmar con los datos parciales de X
- [ ] Validación contra positivos reales: archivo público de Operaciones de Información de X y datasets etiquetados de IO
- [ ] Controles negativos sobre cuentas reales grandes y apolíticas — si marca a un club de fútbol, está midiendo *fandom*

## Fase 3 — Adaptador de X

Sobre **retweets, quotes y respuestas**, nunca sobre likes. La razón está en [`collectors/x.py`](../src/botdetector/collectors/x.py): el endpoint `liking_users` devuelve un máximo de 100 usuarios por publicación, para siempre y sin paginación, y no son 100 aleatorios.

- [ ] Búsqueda por `conversation_id` para respuestas
- [ ] Búsqueda con `is:retweet` para amplificaciones
- [ ] Búsqueda por URL del tweet original para quotes
- [ ] Control de presupuesto con corte duro (pago por uso: ~0,005 USD por lectura de publicación, ~0,010 por lectura de usuario, sin tramo gratuito para nuevas altas desde 2026)

## Fase 4 — Perfilado de cuentas

Capa complementaria, **nunca sustitutiva** de la de coordinación. Puntuación continua, jamás binaria.

- [ ] Features temporales: distribución circadiana (los bots no duermen), entropía entre eventos, ráfagas
- [ ] Features de red: vecindario compartido con otras cuentas sospechosas
- [ ] Modelo tabular entrenado sobre [TwiBot-22](https://arxiv.org/abs/2206.04564)

Nota del estado del arte: los cinco mejores modelos del benchmark TwiBot-22 son basados en grafos y superan en 8,2% la media de los baselines. Las features de perfil son el suelo, no el techo. Y frente a bots con LLM detrás, la separación por contenido puro ya no es viable — las señales conductuales y relacionales sí siguen siéndolo.

## Fase 5 — Informe reproducible

- [ ] Informe HTML autocontenido anclado al hash del snapshot y a `AnalysisConfig`
- [ ] Curva de sensibilidad incrustada automáticamente en cada informe
- [ ] Comparación con controles emparejados como sección obligatoria, no opcional

## En paralelo, desde ya — Acceso vía Artículo 40 del DSA

**Es la vía que separa un proyecto de fin de semana de una herramienta que produce evidencia utilizable.**

El Portal de Acceso a Datos del DSA está operativo desde el **28 de octubre de 2025** y las resoluciones llegan en unos **80 días hábiles**. Da acceso a datos que ninguna API vende.

Requisito: afiliación a una institución de investigación, según el art. 2(1) de la Directiva de Copyright en el Mercado Único Digital.

Pasos:

- [ ] Contactar con un grupo universitario español o con **IBERIFIER** (hub iberoamericano de EDMO)
- [ ] Definir el riesgo sistémico concreto que se investiga — es lo que el Artículo 40 exige justificar
- [ ] Preparar la EIPD del RGPD, que hará falta igualmente
- [ ] Presentar la solicitud en el portal

## Lo que este proyecto no va a hacer

- Clasificar cuentas individuales como "bot" de cara al público
- Publicar cifras absolutas sin línea base comparativa
- Aplicarse a un solo lado del espectro político
- Scrapear plataformas violando sus condiciones de servicio
