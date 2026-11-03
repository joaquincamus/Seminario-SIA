# Auditoría independiente — OB2, Actividad 3 (desarrollo de Andrés)

**Fecha de revisión:** 31 de octubre de 2026  
**Material auditado:** `Act. 3-20261031T034335Z-1-001.zip`  
**Dictamen:** **TÉCNICAMENTE CONSISTENTE Y REPRODUCIBLE EN LOS CONTROLES VERIFICADOS; NO CERRADO COMO RESULTADO CIENTÍFICO DEFINITIVO.**

## 1. Fuentes y alcance

- Se inspeccionaron los **71 archivos** del ZIP (11 scripts `.py` y 60 productos de salida, distribuidos en once carpetas de resultados).
- Se contrastó con la tesis formal `SIA_Bascunan_Camus_Monterrey(3).pdf`, especialmente la metodología de OB2, y las transcripciones `27-10-2026.pdf` y `27-10-2026 pt. 2.pdf`.
- Se utilizaron como referencia los archivos vigentes `DESARROLLO/Obj2/Act. 1/Perfiles_Normalizados_ESCO_12.csv`, `Ofertas_Normalizadas_ESCO_diccionario.csv` y `skills_es.csv`, obtenidos del ZIP actualizado de DESARROLLO del 30/10/2026.
- Se contrastó, cuando correspondía, con nuestra ejecución previa `Clusters_Perfiles_Academia.csv` (K=7). **Ningún archivo original del ZIP se modificó**; las pruebas se realizaron en una copia de trabajo.

## 2. Flujo auditado por pasos

| Paso | Script | Función | Resultado observado |
|---|---|---|---|
| 01 | `01_validar_entradas_esco.py` | Valida estructura y trazabilidad de archivos fuente | 46 carreras, 242 ofertas, 0 errores estructurales y 392 advertencias (288 de revisión ESCO, 90 por alcanzar límites del extractor, 14 vacantes sin URI) |
| 02 | `02_revisar_y_seleccionar_registros.py` | Determina elegibilidad provisional sin desechar los no vectorizables | 46 carreras y 228/242 ofertas pasan; las 14 sin URI siguen identificadas |
| 03 | `03_preparar_corpus_esco.py` | Organiza conceptos URI y relaciones registro–concepto | 598 URI (255 academia, 446 mercado, 103 compartidos); 1.867 asignaciones |
| 04 | `04_generar_embeddings_esco.py` | Genera vectores reales de competencias ESCO por etiqueta | Modelo `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, 598 × 384, normalización L2 |
| 05 | `05_agregar_embeddings_por_registro.py` | Promedia los vectores de las competencias de cada carrera/vacante | 274 × 384, media con pesos iguales por URI, normalización L2 |
| 06 | `06_evaluar_kmeans.py` | Explora K y métricas por población | K-Means separado para academia, mercado y conjunto; silhouette, ARI entre semillas, inercia, Davies–Bouldin y Calinski–Harabasz |
| 07 | `07_inspeccionar_clusters.py` | Inspecciona frecuencias y competencias distintivas | Identifica candidatos y reconoce grupos heterogéneos/pequeños |
| 08 | `08_fijar_k_trabajo.py` | Selecciona particiones de trabajo, no finales | Academia K=5, mercado K=3, conjunto K=4 solo exploratorio |
| 09 | `09_visualizar_clusters_pca.py` | Grafica y documenta PCA | PCA academia 42,8 % de varianza 2D, mercado 28,7 %, conjunto 28,0 % |
| 10 | `10_auditar_cierre_act3.py` | Control técnico de integridad | 67 controles, 0 errores técnicos, 1 asunto pendiente: revisión humana |
| 11 | `11_preparar_revision_semantica.py` | Prepara una revisión humana dirigida | 8 fichas de grupos y 116 relaciones ESCO para revisar; **todas las decisiones siguen PENDIENTES** |

## 3. Verificaciones independientes realizadas

### 3.1. Identidad y procedencia de datos

| Fuente | SHA-256 contrastado con el DESARROLLO vigente |
|---|---|
| Academia | `fb0445540ebed660b8d3b872af081c916e4beb0eb471e598321699a9d7f32019` |
| Mercado | `4ec4dcba60cb27180e4a46ce56582ffef86539d3d0d18e17a6eb0a9dddae9315` |
| Catálogo ESCO | `30b1271fca7348a01ace7f33619ff6fc00fc3bb645a4dbdfa8fae6d57789f4a4` |

Los tres valores coinciden con la versión vigente. Se verificaron adicionalmente **46 referencias SHA-256 declaradas** en las salidas de los pasos 03–11; todas las 46 coincidieron con sus archivos correspondientes (incluidos los siete referenciados por nombres lógicos en el paso 11).

### 3.2. Representaciones vectoriales

- Se reconstruyeron independientemente **los 274 vectores por registro** desde la matriz de 598 embeddings de URI, utilizando las listas de índices del paso 05 y su media aritmética con normalización L2.
- El error absoluto máximo, elemento a elemento, fue **0,0** en esta reconstrucción con los archivos entregados.
- Se conservaron las **1.867 relaciones**: 526 académicas y 1.341 laborales.
- Esta comprobación verifica **el cálculo de agregación**, no la corrección semántica de cada mapeo ESCO de origen.

### 3.3. K-Means reproducido independientemente

Se reentrenó K-Means con `n_init=20`, `max_iter=400` y semillas 42, 123 y 2026 sobre los vectores distribuidos en el ZIP. Las métricas coincidieron con el paso 06:

| Población | K | Silhouette coseno | ARI medio entre semillas | Tamaños de grupo |
|---|---:|---:|---:|---|
| Academia | 5 | 0,515587 | 0,964158 | 6, 7, 7, 13, 13 |
| Academia | 7 | 0,563553 | 0,951531 | 3, 3, 4, 6, 7, 10, 13 |
| Mercado | 2 | 0,282967 | 1,000000 | 47, 181 |
| Mercado | 3 | 0,212029 | 0,971789 | 46, 79, 103 |
| Mercado | 4 | 0,193608 | 0,908473 | 43, 50, 52, 83 |
| Conjunto | 4 | 0,214489 | 0,847031 | 28, 52, 74, 120 |

Se confirmó además que las asignaciones recalculadas para **academia K=5 y mercado K=3** coinciden con las del archivo `08_asignaciones_principales.csv` (**ARI = 1,0** en ambos casos).

**Precaución sobre el ARI:** este ARI compara tres inicializaciones sobre **el mismo conjunto completo de datos**. Es una medida útil de sensibilidad a inicialización, pero **no es equivalente** al ARI por remuestreo de registros; no acredita por sí solo robustez frente a variaciones de muestra. Por ello, tampoco se compara directamente con el ARI de remuestreo de nuestro código anterior.

## 4. Alineación con tesis y retroalimentación docente

**Aspectos correctamente alineados:**

1. **Unidad de análisis:** se agrupan carreras y vacantes completas, no se sustituyen por grupos de URI. Esto concuerda con el propósito de identificar familias de perfiles descrito en la sección 4.2.3 de la tesis.
2. **Fuentes independientes:** academia y mercado tienen particiones principales separadas. La prueba conjunta no se presenta como evidencia de cobertura, lo que reduce el riesgo de comparar impropiamente los resultados de una fuente contra sí misma señalado por la profesora en la reunión.
3. **Origen de las competencias:** cada agrupación se remonta a los URI y evidencia de los CSV del OB2, lo que ayuda a responder a la exigencia docente de comprender qué entra y sale de cada etapa.
4. **Interpretación crítica:** el propio código advierte que los clústeres y su visualización no miden cobertura; no confunde similitud con pertinencia curricular.
5. **Visualizaciones:** se incluyen codo/inercia, silhouette, estabilidad y PCA. Los gráficos de burbujas del procedimiento histórico **no** aparecen en esta entrega; eran interpretativamente útiles, pero la reunión no los estableció como requisito literal obligatorio.

**Discrepancia documental que debe resolverse:** la metodología formal de la tesis del 27/10/2026 todavía describe **TF-IDF (500 características) y K=5**, mientras el método ejecutado usa **embeddings de 384 dimensiones, K=5 en academia y K=3 en mercado**. El cambio debe explicitarse en la redacción final de la metodología y en la presentación; los textos históricos contradictorios de INFO TESIS no deben copiarse sin verificación contra el código vigente.

## 5. Comparación con nuestro clustering académico anterior

Se cruzaron las 46 carreras por institución y nombre exactos:

- **Andrés K=5 vs. nuestro candidato K=7:** ARI de las particiones ≈ **0,8773**.
- **Andrés K=7 vs. nuestro candidato K=7:** ARI ≈ **0,9552**.

**Interpretación:** las familias principales de administración, minería y medioambiente son robustas a estos cambios de representación y K. La diferencia principal es de **granularidad**, no de integridad de registros. Andrés K=5 fusiona áreas de electricidad, automotriz y mecánica; su grupo informático también incluye Ingeniería Civil e Ingeniería Civil Mecánica. Nuestro K=7 las separa en familias menores.

Esta alta concordancia **no es una validación científica independiente de las competencias**, puesto que ambos modelos reutilizan los mismos mapeos ESCO de origen y la misma arquitectura neuronal de referencia.

## 6. Observaciones de auditoría priorizadas

### O1. **Crítica para declarar cierre científico: falta revisión humana**

- Las **8 fichas** `11_revision_clusters.csv` siguen en `PENDIENTE`.
- Las **116 relaciones texto–ESCO** seleccionadas también siguen en `PENDIENTE`.
- La localización literal de 116 fragmentos confirma rastreabilidad textual, **no la pertinencia conceptual** del URI.
- La muestra es dirigida (cinco registros por clúster), por lo que **no estima una tasa de error representativa**.

**Acción:** completar y documentar la auditoría de grupos y una muestra de relaciones originales, especialmente casos dudosos, antes de presentar nombres de grupos como categorías validadas. No es necesario borrar automáticamente los registros dudosos.

### O2. **Alta: justificar la decisión K=5 para academia y K=3 para mercado**

- **Academia K=5:** silhouette ≈ 0,516, ARI semillas ≈ 0,964, tamaño mínimo seis. Es un compromiso plausible entre síntesis y estabilidad, pero K=7 separa mejor algunas familias y tiene silhouette ≈ 0,564.
- **Mercado K=3:** silhouette ≈ 0,212, ARI semillas ≈ 0,972, tres grupos de 46, 103 y 79. K=2 tiene silhouette superior (≈ 0,283), pero forma un grupo dominante de 181 ofertas; K=4 es más detallado (43/50/52/83), aunque tiene silhouette inferior (≈ 0,194).
- El **método del codo** debe incluirse como orientación, no como demostración automática de optimalidad.

**Acción:** explicitar por escrito que K=5 y K=3 son **elecciones interpretativas de trabajo** sustentadas en métricas y estructura, y revisar brevemente K=7 y K=4 respectivamente. No forzar igual K en ambas fuentes.

### O3. **Alta: grupos con heterogeneidad conceptual**

- **Académico K=5, grupo informática/otras ingenierías (13):** mezcla informática con Ingeniería Civil, Ingeniería Civil Mecánica y Geomensura/Geomática; necesita etiqueta y análisis diferenciados.
- **Académico K=5, electricidad/control/mecánica (7):** combina Ingeniería Mecánica, automotriz y electricidad; válido quizá como macrofamilia, pero no como especialidad homogénea.
- **Mercado K=3, operaciones/mantenimiento/calidad (103):** es amplio y sus límites con gestión de proyectos requieren ejemplos de casos limítrofes.
- Los casos de Química Industrial y Biotecnología en familia ambiental son plausibles, pero precisan comprobación documental.

**Acción:** marcar y discutir los casos fronterizos; evitar renombrar clústeres con términos excesivamente específicos para su contenido real.

### O4. **Alta: dependencia de la normalización ESCO y máximos del extractor**

- **35 de 46 carreras** llegan a 12 selecciones ESCO.
- **55 de 242 ofertas** llegan a 8 selecciones ESCO.
- **14 de 242 ofertas** no son vectorizables y se excluyeron del clustering laboral, no del universo del estudio.

**Acción:** declarar que los vectores representan **competencias detectadas**, no el currículo completo ni el total de habilidades exigidas. Si se harán inferencias por prevalencia o brechas en OB3/OB4, gestionar denominadores y sensibilidad explícitamente.

### O5. **Media: estabilidad y reproducibilidad avanzada**

- ARI calculado con tres semillas y múltiples inicializaciones sobre el **mismo conjunto de datos**: no evalúa cambios de registros ni del extractor.
- El commit exacto del modelo está en `null`, por lo que la reproducción exacta tras futuras descargas del repositorio podría depender de una revisión distinta.
- La representación utiliza **etiqueta ESCO solamente**, con medias sin ponderar por importancia. Es una opción válida, pero se debe indicar por qué se eligió frente a etiqueta+descripción o ponderación IDF.
- Algunos scripts ofrecen instalación automática de bibliotecas con `pip`, lo que puede modificar el entorno de VS Code; preferir un entorno controlado con dependencias documentadas.

**Acción:** al menos una comprobación de estabilidad por remuestreo y documentar versión/revisión del encoder y las decisiones de agregación. No confundir comparaciones de ARI basadas en protocolos distintos.

### O6. **Media: claridad de entregables**

- El ZIP conserva 11 scripts y 60 salidas en 11 carpetas: útil para auditoría, pero excesivo para explicar el OB2 en la memoria de tesis.
- El informe final debe sintetizar preparación, vectorización, selección de K, interpretación y limitaciones, no tratar las 11 operaciones técnicas como 11 actividades metodológicas separadas.
- Falta un gráfico de burbujas equivalente al histórico; puede reconstruirse a partir de frecuencias ya calculadas sin alterar el clustering, si aporta una lectura significativa.

**Acción:** conservar ZIP íntegro como evidencia técnica; producir una selección editorial de tablas y figuras finales, con un informe metodológico consolidado.

## 7. Lo que **NO** puede darse por demostrado con esta actividad

1. No hay **brecha curricular calculada**, **equivalencia certificada** ni porcentaje de enseñanza efectiva.
2. La similitud coseno entre perfiles no es porcentaje de cobertura.
3. Las etiquetas de clúster no validan que cada relación texto–URI ESCO haya sido correctamente seleccionada.
4. Los IDs numéricos de grupos académicos y laborales **no** constituyen emparejamientos cruzados.
5. La muestra laboral reúne diferentes cargos/niveles de experiencia; el clustering no es automáticamente representativo del sector minero de una región.
6. OB3 debe trabajar con URI originales y analizar patrones por fuente; una posible segmentación por clúster es complementaria. OB4 requiere un diseño explícito y verificable de la comparación academia–mercado.

## 8. Ruta propuesta para el cierre sin rehacer el desarrollo

1. **Conservar** el pipeline de Andrés como base técnica del OB2 Act. 3.
2. **Completar** las fichas de los ocho clústeres y la auditoría dirigida de las 116 relaciones, registrando decisiones humanas y casos dudosos; tratar aparte las 14 ofertas no vectorizables.
3. **Contrastar brevemente** K académico 5 vs. 7 y K laboral 3 vs. 4 (con K=2 como referencia de desbalance), incluyendo interpretación temática y eventual remuestreo; no reconstruir los embeddings si las entradas no cambiaron.
4. **Elegir y justificar** la partición final, con nombres de macrofamilias acordes a los casos que realmente contienen.
5. **Consolidar** tablas, gráfico de codo, PCA y, si resulta útil, burbujas de recurrencia. Archivar las salidas intermedias separadamente para evitar ruido visual.
6. **Actualizar la metodología de la tesis**: pasar de la redacción histórica de TF-IDF/K=5 general a la implementación efectivamente utilizada de embeddings + K-Means y K específico por fuente.
7. **Vincular con OB3 y OB4 sin confusiones**: mantener URI y universos con sus denominadores; no inferir correspondencia académica-laboral desde IDs de clúster independientes.

## 9. Dictamen final

**Aprobación técnica condicionada.** Los cálculos centrales (procedencia de insumos, matriz, agregación, K-Means, asignaciones y control 10) resultaron consistentes y reproducibles. **No corresponde aprobar todavía los grupos como hallazgos científicos finales**, porque la revisión semántica humana y la justificación interpretativa de las particiones siguen pendientes.

No recomiendo descartar el desarrollo ni volver a codificarlo de cero. Recomiendo **cerrar las validaciones faltantes** y adaptar la presentación a la tesis y a la retroalimentación docente.
