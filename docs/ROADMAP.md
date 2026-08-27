# Roadmap

## Fase 1 — Motor sobre Bluesky ✅

Jetstream, DuckDB, matriz bipartita, IDF, umbral nulo, Leiden, calibración a nivel de cluster, IIA. Sin coste de datos y con cobertura del 100%.

## Fase 2 — Validación por inyección sintética ✅

Curvas de precisión/recall frente a fidelidad del operador y tamaño de campaña. Resultados y puntos ciegos en [METHODOLOGY.md](../METHODOLOGY.md).

Curvas de degradación por cobertura parcial, con cuatro regímenes de observación y suelos de publicación aplicados en código: [CURVAS.md](CURVAS.md).

**Sesgo de recencia y cuentas grandes** ✅ — [ESCALA.md](ESCALA.md). Resultado: en cuentas grandes el truncado por recencia de X elimina el **100%** de la campaña, frente al 78% que elimina un truncado aleatorio equivalente. Los endpoints de interactuantes por publicación no son utilizables a esa escala.

Pendiente de ampliar:

- [ ] Regímenes combinados: ventana temporal *más* tope por publicación *más* pérdidas de conexión
- [ ] Audiencias sintéticas con homofilia y comunidades temáticas, más parecidas a las reales
- [ ] Caracterizar la transición: a partir de qué razón interactuantes/tope empieza a morder el sesgo de recencia
- [ ] Validación contra positivos reales: archivo público de Operaciones de Información de X y datasets etiquetados de IO
- [ ] Controles negativos sobre cuentas reales grandes y apolíticas — si marca a un club de fútbol, está midiendo *fandom*

## Fase 3 — Adaptador de X

Sobre **retweets, quotes y respuestas**, nunca sobre likes ni retweeters. Lo que empezó siendo una decisión por el tope de 100 usuarios por publicación está ahora medido y es mucho más grave: ese tope no trunca al azar sino por recencia, y en cuentas grandes elimina el 100% de la campaña. Ver [ESCALA.md](ESCALA.md).

- [ ] Búsqueda por `conversation_id` para respuestas
- [ ] Búsqueda con `is:retweet` para amplificaciones
- [ ] Búsqueda por URL del tweet original para quotes
- [ ] Control de presupuesto con corte duro

### Vía de acceso

El **Artículo 40(12) del DSA** cambia el planteamiento respecto a lo previsto inicialmente: acceso gratuito a datos públicos para investigadores afiliados a entidades sin ánimo de lucro, sin proceso de acreditación, y con las prohibiciones contractuales de scraping declaradas incompatibles con el DSA. La Comisión multó a X con 120 M€ en diciembre de 2025, 40 de ellos por incumplir ese artículo, y aceptó su plan correctora en julio de 2026.

Herramienta candidata para la recolección: **`twscrape`** (Python) — rotación multi-cuenta, gestión de límites de tasa por cuenta cada 15 minutos, soporte de retweeters, seguidores y búsqueda. Es el estándar de facto. Evaluar también la API oficial una vez implementado el acceso gratuito comprometido por X.

> **Importante:** la cobertura legal del scraping bajo el 40(12) depende de cumplir los requisitos de investigador elegible. Sin la entidad sin ánimo de lucro constituida y el compromiso de publicación, no aplica.

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
