# OB2 — Actividad 3: síntesis del desarrollo de Andrés

**Estado:** versión técnica final de referencia y particiones K=5/K=3 aceptadas para uso exploratorio; revisión documental independiente concluida con observaciones, sin certificar validación docente/exhaustiva. Este resumen es editorial: conserva los resultados de Andrés sin modificarlos.

## Propósito y datos
Agrupar **perfiles académicos (46 carreras de Coquimbo)** y **ofertas laborales (242 ofertas mineras, de las cuales 228 se pudieron vectorizar)** usando las competencias ESCO extraídas y sus URI; 14 ofertas se señalan como normalización incompleta y **no** son prueba de ausencia de competencias.

- Competencias distintas: 255 academia; 446 mercado; 598 en el conjunto unido; 103 compartidas.
- Asignaciones ESCO originales: 526 académicas y 1.341 laborales.
- Modelo `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, vectores por URI de 384 dimensiones; **promedio de los embeddings** de las competencias por carrera u oferta y normalización L2; el desarrollo ejecutado **no utiliza TF-IDF como representación principal**.
- K-Means sobre perfiles, separadamente por población. El codo/inercia, silhouette coseno y estabilidad entre semillas contribuyen a justificar K, sin imponer coincidencia de K entre fuentes.

## Particiones adoptadas para descripción exploratoria (sin validación curricular exhaustiva)

| Fuente | K | Tamaños | Silhouette coseno | ARI entre semillas |
|---|---:|---|---:|---:|
| Academia | 5 | 6, 7, 7, 13, 13 | 0,516 | 0,964 |
| Mercado | 3 | 46, 79, 103 | 0,212 | 0,972 |

**Rigor:** ARI entre semillas comprueba consistencia respecto a la inicialización sobre los mismos registros, no estabilidad ante remuestreo de datos. K académico=7 produce mayor silhouette (~0,564) pero grupos pequeños. K laboral=2 presenta mayor silhouette (~0,283), pero concentra 181 de 228 ofertas en un grupo. La revisión documental y el dictamen de uso conservador de K se detallan en `02_DICTAMEN_Y_LIMITACIONES.md`.

## Familias propuestas (etiquetas originales no homologadas formalmente)

**Academia K=5:** (1) minas y planificación minera, n=7; (2) gestión/administración/industria, n=13; (3) informática y otras ingenierías, n=13, **heterogéneo**; (4) electricidad/control/mecánica, n=7, **heterogéneo**; (5) ambiente y prevención, n=6.

**Mercado K=3:** (1) datos y analítica, n=46; (2) operaciones/mantenimiento/calidad, n=103, **muy amplio**; (3) gestión y coordinación de proyectos, n=79.

## Interpretación responsable

- La agrupación compara afinidades de **competencias detectadas**; no certifica todas las asignaturas impartidas, habilidades exigidas ni la pertinencia curricular.
- Los URI originales son las unidades recomendadas para Apriori en OB3. Los números de clúster no se emparejan entre academia y mercado.
- 35/46 carreras alcanzan el máximo de 12 URI seleccionados y 55/242 ofertas el límite de 8: declarar sensibilidad y sesgos potenciales.
- No presentar la similitud coseno ni las burbujas como porcentajes de cobertura efectiva.

## Material seleccionado

- `Tablas/`: asignaciones por registro, 8 clústeres, competencias distintivas, métricas K.
- `Figuras/`: inercia/codo, silhouette, estabilidad ARI, PCA académico y laboral.
- `Informes/`: decisión provisional de K y auditoría técnica originales de Andrés.
- Para evidencia, código y validaciones completas, usar `02_RESPALDO_TECNICO_COMPLETO/`.
