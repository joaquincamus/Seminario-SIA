# Act. 3 (OB2) — Dictamen de cierre documental independiente

**Fecha:** 31-10-2026. **Objeto:** versión de Andrés del clustering académico y laboral. **Alcance:** revisión independiente del material entregado; no acta de aprobación de la profesora ni firma del equipo.

## Decisión de uso

**Se acepta y conserva como la versión técnica definitiva de referencia de la Actividad 3.** Su pipeline, entradas, 598 URI combinados, 274 vectores de registros, asignaciones K-Means y métricas principales fueron contrastados y resultan reproducibles conforme a la auditoría previa. Las **particiones K=5 (academia) y K=3 (mercado) se adoptan como macrofamilias DESCRIPTIVAS EXPLORATORIAS**, con cautelas expresas. Esto cierra la revisión documental independiente sin certificar correspondencia curricular real ni aprobar individualmente la normalización ESCO.

## A. Justificación operativa de particiones

- **Academia:** K=5, 46 programas, tamaños 13/13/7/7/6, silhouette coseno 0,516, ARI entre semillas 0,964. Se elige por síntesis e interpretabilidad de macrofamilias, aunque K=7 presenta silhouette más alto (≈0,564) y mayor detalle de especialidades. **No existe un K universalmente óptimo demostrado**.
- **Mercado:** K=3, 228 ofertas vectorizables, tamaños 103/79/46, silhouette 0,212, ARI entre semillas 0,972. K=2 tiene silhouette superior (≈0,283) pero un grupo de 181 ofertas; K=4 da más detalle con menor silhouette (≈0,194). K=3 es compromiso descriptivo, con separación moderada/baja.
- El ARI entre **semillas** evalúa reproducibilidad frente a inicialización sobre los mismos registros; no prueba estabilidad frente a nuevos datos, reextracción ESCO ni muestreo temporal. El codo es indicador complementario, no demostración.

## B. Revisión de familias

Se examinaron **las ocho familias** mediante los nombres de carreras/cargos y las competencias distintivas documentadas. El detalle está en `08_FAMILIAS_REVISION_DOCUMENTAL.csv`.

- Cinco macrofamilias académicas: minas (7), gestión e industria (13), informática y otras ingenierías (13, **heterogénea**), electricidad/energía/mecánica/automotriz (7, **heterogénea**) y ambiente/prevención (6, **heterogénea**).
- Tres macrofamilias laborales: orientación analítica (46), operaciones/mantenimiento/calidad (103, **muy amplia**) y proyectos/coordinación (79, **amplia**).
- Conclusión: **las ocho particiones son utilizables para perfilamiento y descripción exploratoria** siempre que se mantengan las etiquetas propuestas originales con advertencias y no se les atribuya homogeneidad total ni validación curricular.

## C. Revisión textual de las 116 relaciones seleccionadas

Se examinaron las **116 parejas evidencia original abreviada — etiqueta ESCO** de la muestra dirigida. Se clasificaron solo como revisión documental independiente (NO como `decision_humana` ni validación por expertos del equipo):

| Clasificación documental | Registros | Interpretación |
|---|---:|---|
| Concordancia textual aparente | 60 | Frase compatible a nivel literal, sin acreditar dominio real de la habilidad. |
| Afinidad temática plausible | 29 | Interpretación defendible como tema, pero falta contexto para inferir la acción ESCO exacta. |
| Observación prioritaria | 27 | La frase es genérica, diferente o más limitada que la acción ESCO seleccionada. |

Casos especialmente claros para evitar afirmaciones excesivas: `ISO 50001` → sistemas de gestión de calidad (la norma trata gestión de energía); `Primavera P6` → software de programación **minera** (la herramienta no implica ese ámbito específico); `integridad de activos` → gestión de integridad de **tuberías**; y nombres de cursos de contabilidad → **uso de sistemas** contables. Estos casos **no se corrigieron ni eliminaron**. El inventario completo, con identificadores y observaciones, está en `116_RELACIONES_REVISION_DOCUMENTAL.csv`.

**Importante:** la muestra es dirigida, no probabilística. Estas frecuencias **no son una estimación de precisión o tasa de error del universo**. La falta de contexto suficiente impide otorgar aprobación semántica definitiva a las 116 correspondencias. La decisión humana original continúa sin completar, visible en los archivos inalterados de Andrés.

## D. Condiciones de interpretación al usar la tesis

1. Los embeddings representan **competencias ESCO seleccionadas**, no habilidades realmente adquiridas ni currículo exhaustivo.
2. 35 de 46 carreras llegaron al límite de 12 competencias; 55 de 242 ofertas al límite de 8. Este truncamiento puede afectar perfiles y fronteras de grupo.
3. Las 14 ofertas sin selección ESCO se conservan en el universo, pero quedan **no clasificables** para clustering; no significa que carezcan de requisitos.
4. Los grupos académicos y laborales se ajustaron por separado; IDs iguales no significan equivalencia entre fuentes.
5. No inferir cobertura, brechas porcentuales, causalidad ni eficacia curricular a partir de silhouette, PCA, cosenos o coincidencia de macrofamilias.
6. En OB3 usar las competencias **URI** como transacciones originales; segmentar por clúster solo de manera auxiliar.
7. Revisar la redacción de la tesis para que coincida con el modelo ejecutado: embeddings multilingües + agregación por registro + K-Means, no TF-IDF como algoritmo principal.

## E. Alcance del cierre

**CERRADO:** auditoría reproducible de archivos/cálculos; revisión documental de composición de ocho familias; revisión textual dirigida de 116 relaciones; aceptación editorial de K=5/K=3 como descriptores exploratorios.

**NO AFIRMADO NI CERTIFICADO:** aprobación humana/docente de las 116 relaciones; exactitud semántica de todos los URI; representatividad estadística de 242 ofertas; equivalencia profesional de miembros; brecha curricular de OB4.

**Preservación:** ninguno de los 71 archivos originales de Andrés fue modificado. Los anexos de revisión independiente son añadidos externos.
