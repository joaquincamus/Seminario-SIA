# Cierre de la Actividad 3: plan de validación y aprobación

**Ninguna de las ocho familias ni de las 116 relaciones muestreadas está aprobada todavía.** Se entrega el modelo técnico como versión de trabajo estable; la aprobación científica requiere completar los controles siguientes y documentar al responsable.

## A. Revisión de 8 grupos (obligatoria)

Abrir la copia de trabajo `../02_RESPALDO_TECNICO_COMPLETO/VALIDACION_EN_CURSO/11_revision_clusters_TRABAJO.csv`. Confrontar cada nombre del clúster con (i) las carreras/cargos que contiene, (ii) ejemplos centrales/periféricos y (iii) URI distintivos. Registrar `decision_humana`: APROBAR / MODIFICAR / RECHAZAR / PENDIENTE; nombre validado, evidencia, observaciones, responsable y fecha. No editar el CSV original en `Act. 3/salida_revision_semantica/`.

**Revisión temática inicial NO equivalente a aprobación:**

| Fuente | Clúster | n | Revisión prioritaria |
|---|---:|---:|---|
| Academia | 0 | 7 | Minas: revisar que las siete carreras y evidencias respalden el nombre |
| Academia | 1 | 13 | Gestión e industria: distinguir capacidades administrativas de competencias industriales |
| Academia | 2 | 13 | **Alta:** ingeniería civil/mecánica, geomensura y telecomunicaciones dentro del grupo informático |
| Academia | 3 | 7 | **Alta:** electricidad y mecánica automotriz reunidas en una macrofamilia |
| Academia | 4 | 6 | Ambiente/riesgos: comprobar química industrial y biotecnología con evidencia |
| Mercado | 0 | 46 | Datos: revisar las vacantes periféricas no estrictamente analíticas |
| Mercado | 1 | 103 | **Alta:** macrogrupo de operaciones, mantenimiento, calidad y permisos |
| Mercado | 2 | 79 | Gestión de proyectos: comprobar las vacantes de corrosión/integridad en el borde temático |

## B. Revisión de 116 relaciones texto original–ESCO (obligatoria)

Abrir `../02_RESPALDO_TECNICO_COMPLETO/VALIDACION_EN_CURSO/11_revision_relaciones_texto_esco_TRABAJO.csv`. Para cada fila contrastar el fragmento, su oración/párrafo y las funciones del concepto URI. Registrar CORRECTA / INCORRECTA / AMBIGUA / PENDIENTE, explicación, responsable y fecha.

**Ejemplos de revisión prioritaria (números de registro 1–116, NO decisiones definitivas):**

| Registro | Evidencia | URI/etiqueta seleccionada | Pregunta de auditoría |
|---:|---|---|---|
| 21 | Taller de Proyecto de Título | gestionar proyectos | ¿El título de asignatura demuestra gestión de proyectos o solo un proyecto final? |
| 33 | Ingeniería de Software | utilizar herramientas de ingeniería de software asistida por ordenador | ¿Se evidencia uso de herramientas CAE o solamente la disciplina? |
| 60 | optimización de la disponibilidad de vehículos unitarios y flotas | gestionar el inventario de vehículos | ¿Disponibilidad de flota equivale a gestión de inventarios? |
| 88 | Manejo básico de software de minería | utilizar software de programación minera | ¿Se menciona programación minera específica? |
| 89 | Norma ISO 50.001 | implementar sistemas de gestión de calidad | ¿La referencia a gestión energética justifica una competencia específica de calidad? |
| 109 | Primavera P6 | utilizar software de programación minera | ¿Se trata de planificación general de proyectos, no exclusivamente minera? |

Los 116 fragmentos se localizaron literalmente en sus archivos fuente, pero **localización no prueba pertinencia semántica**. Esta selección es **dirigida, no muestra aleatoria representativa**; no extrapolar una tasa global de error desde sus resultados.

## C. Resolver K con interpretación y métricas

- **Academia:** contrastar K=5 vs. K=7 y la utilidad real de separar especialidades de electricidad, automotriz y mecánica. No escoger solo por silhouette.
- **Mercado:** contrastar K=3 vs. K=2 y K=4; justificar el grupo grande de operaciones y el valor añadido de los tres macroperfiles.
- Documentar quién aprobó la nomenclatura final, con qué evidencia y fecha. ARI reportado es entre semillas sobre la misma población, no remuestreo.

## D. Controles de cierre

- [ ] Revisar 8 fichas y resolver todas sus decisiones.
- [ ] Revisar 116 relaciones y registrar correctas, ambiguas e incorrectas sin modificar silenciosamente fuentes.
- [ ] Decidir K por fuente con justificación interpretativa y gráfica.
- [ ] Definir si los errores de asignación detectados ameritan rehacer datos derivados: toda modificación de URI exigiría recalcular embeddings agregados y agrupamiento, conservando versiones.
- [ ] Documentar el límite 12/8 y las 14 ofertas no vectorizables.
- [ ] Actualizar metodología de tesis (embeddings + K-Means; K diferente por fuente), sin reutilizar afirmaciones históricas incompatibles.
- [ ] Emitir aprobación científica de los grupos, firmada/fechada por integrantes o revisores, solo tras la evidencia.

**Al cierre** se puede sustituir `PENDIENTE` por el estado real, revisar si cambian las etiquetas o K, y regenerar la entrega editorial, siempre conservando el respaldo técnico intacto.
