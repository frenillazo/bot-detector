# Límites de uso y publicación

Una herramienta antidesinformación con falsos positivos se convierte en munición para quien pretende combatir. Basta **un** caso de una persona real señalada por error para desacreditar todo el trabajo — y para causarle un daño que ningún porcentaje agregado justifica.

Este documento no es un descargo de responsabilidad. Son las condiciones bajo las cuales los resultados de esta herramienta significan algo.

## Lo que nunca se publica

- **Identificadores de cuentas individuales señaladas como coordinadas.** `AnalysisResult.coordinated_actor_ids()` existe para auditoría interna y para que un tercero pueda reproducir el resultado. No es material publicable.
- **Cualquier cifra sin su línea base.** Un porcentaje absoluto de coordinación no es interpretable. El código lo impone: `relative_to_baseline()` lanza `ValueError` sin controles.
- **Cualquier cifra sin su curva de sensibilidad.** Sin ella el lector no sabe cuánta campaña se escapó.
- **Conclusiones sobre intención o autoría.** La herramienta detecta sincronía inverosímil. No prueba quién opera las cuentas ni con qué fin. El salto de "hay coordinación" a "X paga por esto" requiere pruebas de otra naturaleza: documentales, financieras, testificales.

## Clusters pequeños bajo cobertura parcial: inspección manual obligatoria

Los falsos positivos residuales que quedan tienen una firma reconocible: **son exactamente del tamaño mínimo permitido**, tres cuentas, y aparecen solo cuando se observa una fracción de las publicaciones. Ver [docs/CURVAS.md](docs/CURVAS.md).

Regla práctica: si el cluster detectado es pequeño *y* la cobertura es parcial, no se publica sin revisión manual de las cuentas implicadas y de las publicaciones que las conectan. Un grupo de tres cuentas unidas por dos o tres coincidencias no es un hallazgo, es una coincidencia con buena suerte estadística.

Los hallazgos que importan —granjas reales— no tienen ese aspecto: son grandes, densos, y su evidencia supera al azar por órdenes de magnitud, no por un pelo.

## Lo que sí se publica

Agregados, clusters como entidades anónimas, y siempre en forma relativa:

> El 34% de los retweets de la cuenta X procede de un cluster de 1.847 cuentas cuya masa de evidencia supera en 40× la máxima producida por el modelo nulo, frente a una mediana de 3% en 12 cuentas de control emparejadas por tamaño y temática.

## Simetría de aplicación

**Si la herramienta solo se aplica a un lado del espectro político, es partidista por construcción, aunque el algoritmo sea perfectamente neutral.**

Obligatorio: analizar cuentas de todo el espectro y publicar todos los resultados, incluidos los incómodos. Los controles emparejados deben incluir cuentas del bando contrario al analizado. Esto no es equidistancia; es lo que separa una medición de una acusación motivada.

## RGPD

Se procesan datos personales de residentes en la UE (identificadores de cuenta, marcas temporales, patrones de comportamiento). Antes de cualquier publicación:

- **Base jurídica**: interés legítimo (art. 6.1.f) o tratamiento con fines de investigación (art. 89). Documentarla por escrito.
- **Evaluación de impacto (EIPD)**: obligatoria dada la escala y el perfilado de comportamiento.
- **Minimización**: no recolectar contenido de publicaciones si el análisis solo necesita la matriz de interacciones — que es el caso.
- **Retención**: plazo definido y borrado efectivo. `data/`, `*.duckdb`, `*.parquet` y `snapshots/` están en `.gitignore`; nunca se versionan datos crudos.
- **Derechos de los interesados**: prever cómo se atiende una solicitud de acceso o supresión antes de recolectar nada.

## Difamación

En España, una imputación de hechos que lesione la dignidad de una persona puede constituir injurias o calumnias, y las personas jurídicas pueden reclamar por daño reputacional. Los actores del ámbito de la desinformación política litigan de forma agresiva, y el coste de defenderse es real aunque se gane.

Las reglas de este documento son también la defensa: una afirmación estadística sobre un agregado, acompañada de método público, datos verificables por hash y tasas de error declaradas, es un terreno muy distinto de "esta cuenta es un bot".

Antes de publicar señalando a una persona o medio concretos: **asesoramiento jurídico**.

## Condiciones de servicio y acceso a datos

- **Scraping de X viola sus condiciones de servicio**, y X ha litigado activamente contra proyectos de recolección. Que los datos sean públicos no elimina el riesgo contractual.
- **La vía limpia en la UE es el Artículo 40 del DSA**: acceso para investigadores acreditados, con el portal operativo desde octubre de 2025. Requiere afiliación a una institución de investigación. Ver [docs/ROADMAP.md](docs/ROADMAP.md).
- **Bluesky vía Jetstream es abierto y sin autenticación** por diseño del protocolo. Ahí no hay conflicto.

## Licencia

AGPL-3.0, elegida deliberadamente: quien despliegue esta herramienta como servicio está obligado a publicar su código. Un instrumento que produce acusaciones públicas no puede ejecutarse en una versión cerrada y no auditable — incluido cualquier fork de este repositorio.
