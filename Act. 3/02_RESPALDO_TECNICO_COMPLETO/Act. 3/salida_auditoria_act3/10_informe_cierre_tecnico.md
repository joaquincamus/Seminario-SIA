# Obj2 / Act. 3 — Paso 10: auditoría técnica del pipeline

**Estado:** TECNICAMENTE_CONSISTENTE_CON_REVISION_PENDIENTE.

## Alcance comprobado
- Matriz de **274 × 384** (46 carreras, 228 ofertas), vectores normalizados.
- Agrupamiento académico **K=5** y laboral **K=3**, provisionales.
- Agrupamiento combinado **K=4**, exclusivamente exploratorio.
- Archivo PCA con **548 filas**: 274 principales y 274 combinadas; no son 548 casos únicos.
- Integridad referencial entre IDs, índices de vector, clusters y puntos de PCA.
- Verificación de huellas SHA-256 registradas en el paso 09.

## Resultados
- Controles ejecutados: **67**.
- Errores técnicos: **0**.
- Controles pendientes: **1**.
- Fichas de revisión humana sin decisión: **8/8**.
- Proporción de varianza representada en PCA 2D: academia **42.8%**, mercado **28.7%**, conjunto **28.0%**.

## Qué NO demuestra este paso
1. Que las asignaciones de competencias ESCO coincidan correctamente con los textos originales.
2. Que los grupos sean categorías profesionales validadas por expertos.
3. Que la silueta, la similitud entre vectores o la proximidad de puntos PCA sea porcentaje de cobertura curricular.
4. Que las **14 ofertas excluidas** carezcan de competencias en la realidad.

## Próximos hitos
- Completar `salida_seleccion_k/08_revision_humana_clusters.csv` (sin borrar registros).
- Auditar muestras de las relaciones texto original–URI ESCO con trazabilidad por carrera/oferta.
- Documentar exclusiones, límites del extractor y sesgos de la muestra.
- Solo después definir por separado la metodología de comparación academia–mercado y análisis de brechas.

Los archivos de este paso son controles técnicos; **no** constituyen por sí solos una validación científica final.
