# Roadmap y estado del proyecto

> **Última actualización: 27 de agosto de 2026.**
> Documento de traspaso: pensado para retomar el proyecto tras semanas o meses sin tocarlo.

---

## Dónde estamos

El motor funciona, está validado y sabe declarar sus propios límites. **El siguiente paso técnico grande está bloqueado por el papeleo**, no por el código: hace falta acceso real a datos de X, y esa vía es el Artículo 40(12) del DSA.

| Fase | Estado |
|---|---|
| 1 · Motor sobre Bluesky | ✅ Completa |
| 2 · Validación por inyección sintética | ✅ Completa |
| 2b · Curvas de cobertura parcial y escala | ✅ Completa |
| 3 · Adaptador de X | ⛔ **Bloqueada: requiere acceso 40(12)** |
| 4 · Perfilado de cuentas | ⏸ No empezada, opcional |
| 5 · Informe reproducible | ⏸ No empezada |

Estado de la suite: **94 tests, ~40 s**, lint y formato limpios.

---

## Decisiones ya tomadas (no re-litigar sin datos nuevos)

Estas se tomaron con medición detrás. Si alguien las cambia sin evidencia, el detector empeora.

**1 · El estadístico es el test hipergeométrico, no el coseno.**
El coseno no distingue "2 de 2 compartidos" de "40 de 40": ambos valen 1,0. Ese era el mecanismo exacto de un falso positivo de 27 cuentas reales. Ver `coordination/validated.py`.

**2 · El umbral se calibra por permutación, no con Bonferroni.**
El modelo hipergeométrico asume publicaciones equiprobables, cosa falsa, y esa mala especificación daba 25 falsos positivos de 30 con Bonferroni. Modelar la popularidad analíticamente tampoco vale: la propia campaña infla el grado de sus objetivos, así que se estimaría el nulo con datos que contienen la señal.

**3 · `min_target_engagement` se queda en 1.**
Las publicaciones con un solo interactuante son parte del universo N, y N es lo que distingue "2 de 2 sobre 300 publicaciones" de "2 de 2 sobre 25". Subirlo a 2 hunde la precisión de 1,00 a 0,88.

**4 · `min_cluster_size` se queda en 5.**
En 500 ejecuciones sobre audiencias orgánicas con cobertura parcial, los 6 falsos clusters residuales tenían **todos exactamente 3 cuentas**. Con suelo 5: 0/200. Cuesta las campañas de 3-4 cuentas, que solo se detectaban el 48% de las veces.

**5 · Nunca sobre likes ni retweeters de X.**
No por el tope de 100, sino porque ese tope trunca **por recencia**: en cuentas grandes elimina el 100% de la campaña frente al 78% de un truncado aleatorio. Es sesgo direccional, no falta de volumen. Ver [ESCALA.md](ESCALA.md).

---

## Qué se puede hacer sin esperar al 40(12)

Ninguna de estas necesita acceso a X.

- [ ] **Audiencias sintéticas más realistas**: con homofilia y comunidades temáticas. Las actuales tienen selección independiente, lo que probablemente hace los suelos de cobertura optimistas.
- [ ] **Regímenes de observación combinados**: ventana temporal *más* tope por publicación *más* pérdidas de conexión. Los efectos previsiblemente se acumulan peor que de forma aditiva.
- [ ] **Caracterizar la transición del sesgo de recencia**: a partir de qué razón interactuantes/tope empieza a morder. Ahora solo hay dos puntos, uno donde no muerde y otro donde mata.
- [ ] **Validación contra positivos reales**: archivo público de Operaciones de Información de X y datasets etiquetados de IO. Es verdad terreno confirmada por las plataformas y no requiere permisos.
- [ ] **Controles negativos sobre cuentas reales de Bluesky**: grandes y apolíticas. Si marca a un club de fútbol, está midiendo *fandom* y no coordinación.
- [ ] **Fase 5, informe reproducible**: HTML autocontenido anclado al hash del snapshot y a `AnalysisConfig`, con la curva de sensibilidad incrustada y la comparación con controles como sección obligatoria.

---

## Fase 3 · Adaptador de X — bloqueada

### Qué hay que construir

Sobre **retweets, quotes y respuestas**. Nunca likes ni retweeters (decisión 5).

- [ ] Búsqueda por `conversation_id` para respuestas
- [ ] Búsqueda con `is:retweet` para amplificaciones
- [ ] Búsqueda por URL del tweet original para quotes
- [ ] Control de presupuesto con corte duro

Herramienta candidata: **`twscrape`** (Python) — rotación multi-cuenta, gestión de límites de tasa por cuenta cada 15 minutos, soporte de búsqueda y retweeters. Evaluar también la API oficial una vez X implemente el acceso gratuito comprometido.

### Lo primero que hay que comprobar con datos reales

> **El truncado de X se ha modelado *suponiendo* que es por recencia.** Todo el argumento de [ESCALA.md](ESCALA.md) —y con él la decisión 5, que determina qué fuente de datos usar— depende de ese supuesto. No está verificado contra X.
>
> En cuanto haya acceso: coger una publicación con miles de interacciones, pedir la lista truncada, y comprobar si los devueltos son los más recientes, los más antiguos, o una muestra. **Si el truncado resulta ser distinto, hay que rehacer la conclusión sobre qué fuente usar.**

Segunda comprobación prioritaria: contrastar los suelos de cobertura de [CURVAS.md](CURVAS.md) contra una audiencia real. Los actuales salen de audiencias sintéticas y probablemente son optimistas.

### Vía de acceso: Artículo 40(12) del DSA

Acceso gratuito a datos públicos para investigadores afiliados a **entidades sin ánimo de lucro**, **sin proceso de acreditación**, con las prohibiciones contractuales de scraping declaradas incompatibles con el DSA.

La Comisión multó a X con 120 M€ en diciembre de 2025 —40 de ellos por incumplir ese artículo— y aceptó su plan correctora en julio de 2026, con seis meses de implementación y auditoría externa.

> El procedimiento completo está en el directorio `tramites-dsa/` de la raíz: guía maestra, borradores de acta fundacional y estatutos, plantilla de EIPD, dossier de investigación, textos de solicitud por plataforma y bitácora de actuaciones. **No está versionado** (excluido vía `.git/info/exclude`), así que existe solo en la copia local. Empezar por `tramites-dsa/00-CHECKLIST.md`.

Resumen del camino: constituir una asociación con objeto social de investigación → anclar la pregunta al art. 34(1)(c), efectos sobre el discurso cívico y los procesos electorales → dossier reutilizable con EIPD → formulario propio de cada plataforma.

**La cobertura legal del scraping depende de cumplir los requisitos de investigador elegible.** Sin la entidad constituida y el compromiso de publicación, no aplica y volvemos al escenario de riesgo contractual.

---

## Fase 4 · Perfilado de cuentas — opcional

Capa complementaria, **nunca sustitutiva** de la de coordinación. Puntuación continua, jamás binaria.

- [ ] Features temporales: distribución circadiana (los bots no duermen), entropía entre eventos, ráfagas
- [ ] Features de red: vecindario compartido con otras cuentas sospechosas
- [ ] Modelo tabular entrenado sobre [TwiBot-22](https://arxiv.org/abs/2206.04564)

Del estado del arte: los cinco mejores modelos de TwiBot-22 son basados en grafos y superan en 8,2% la media de los baselines. Las features de perfil son el suelo, no el techo. Frente a bots con LLM detrás la separación por contenido ya no es viable; las señales conductuales y relacionales sí.

Se marca como opcional a propósito: la capa de coordinación ya funciona y es más defendible. El perfilado añade sensibilidad a costa de introducir un clasificador de cuentas individuales, que es justo lo que [ETHICS.md](../ETHICS.md) restringe.

---

## Lo que este proyecto no va a hacer

- Clasificar cuentas individuales como "bot" de cara al público
- Publicar cifras absolutas sin línea base comparativa
- Aplicarse a un solo lado del espectro político
- Scrapear plataformas sin la cobertura del Artículo 40(12)

---

## Al retomar: por dónde empezar

1. Leer las **decisiones ya tomadas** de este documento. Están medidas y desharlas cuesta caro.
2. `pytest -q` para confirmar que el motor sigue verde (~40 s).
3. Si el 40(12) está desbloqueado: la **verificación del truncado de X** es lo primero, antes de escribir el colector. Determina qué fuente de datos usar.
4. Si no lo está: cualquiera de las tareas de la sección "sin esperar al 40(12)". La más rentable es la validación contra los datasets públicos de Operaciones de Información — es verdad terreno real y no depende de nadie.
