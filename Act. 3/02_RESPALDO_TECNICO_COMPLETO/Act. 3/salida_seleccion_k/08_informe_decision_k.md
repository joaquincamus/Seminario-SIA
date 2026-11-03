# Obj2 · Actividad 3 — Paso 08: selección de K de trabajo

## Alcance
Decisión **provisional y reproducible** sobre particiones existentes del paso 06, interpretadas en paso 07.
El programa no ejecuta K-Means, no mide cobertura curricular ni valida la normalización ESCO original.
La semilla de referencia para las asignaciones ya calculadas es 42; los IDs de clusters solo valen dentro de cada población y K.

## Decisiones

| Población | Uso | K | Silueta coseno | ARI medio | Tamaños |
|---|---|---:|---:|---:|---|
| academia | Principal provisional | 5 | 0.516 | 0.964 | 7, 13, 13, 7, 6 |
| mercado | Principal provisional | 3 | 0.212 | 0.972 | 46, 103, 79 |
| conjunto | Exploratorio solamente | 4 | 0.214 | 0.847 | 52, 120, 28, 74 |

### Academia: K=5
Entre K=5, 7 y 8, se escoge K=5 como solución de trabajo por estabilidad alta,
mínimo seis carreras por grupo y mejor legibilidad interpretativa. K=7 y K=8
tienen mayor silueta, pero crean respectivamente 3 y 4 clusters de menos de cinco carreras.
Se debe revisar especialmente el grupo académico heterogéneo de informática y otras ingenierías.

### Mercado: K=3
K=2 tiene mayor silueta (aprox. 0,283), pero concentra 181 ofertas en un solo grupo.
K=3 reduce la silueta (aprox. 0,212), a cambio de separar de manera exploratoria
analítica, operaciones/mantenimiento y gestión de proyectos. El ARI medio permanece alto
(aprox. 0,972) y ningún grupo es pequeño. **No** debe presentarse como K matemáticamente óptimo.

### Conjunto: K=4 solo exploratorio
Permite diferenciar una familia minera (7 carreras y 21 ofertas), pero su estabilidad
es menor que la de K=3 y contiene 228 ofertas frente a 46 carreras.
No se usará para inferir cobertura ni emparejamiento currículo-empleo.

## Clusters principales y etiquetas de trabajo

| Población | Cluster (local) | n | Nombre propuesto, **no validado** |
|---|---:|---:|---|
| academia | 0 | 7 | Ingeniería de minas y planificación minera |
| academia | 1 | 13 | Gestión, administración e ingeniería industrial |
| academia | 2 | 13 | Informática y otras ingenierías (grupo heterogéneo) |
| academia | 3 | 7 | Electricidad, control y mecánica |
| academia | 4 | 6 | Medioambiente y prevención de riesgos |
| mercado | 0 | 46 | Datos y analítica |
| mercado | 1 | 103 | Operaciones, mantenimiento y calidad |
| mercado | 2 | 79 | Gestión y coordinación de proyectos |

## Limitaciones obligatorias
- Los mapeos ESCO originales siguen pendientes de revisión humana; estas etiquetas pueden cambiar.
- 14 ofertas sin competencias ESCO siguen fuera de la matriz; 228 de 242 ofertas fueron representadas.
- Los promedios de embeddings no ponderan competencias y no equivalen a porcentajes de cobertura.
- Las competencias distintivas se ordenan por diferencia de prevalencia en el propio conjunto; no prueban pertinencia laboral.
- Los clusters principales se ajustaron separadamente. Sus números no son equivalentes ni comparables entre academia y mercado.
- Las agrupaciones están condicionadas por el extractor ESCO, su límite de competencias y la composición de la muestra.

## Revisión humana pendiente
Completar `08_revision_humana_clusters.csv`: confirmar/corregir etiquetas, auditar evidencias originales
y justificar la utilidad para el objetivo de la tesis. No borrar registros solo por pertenecer a un grupo.

## Siguiente paso
Visualización descriptiva, preferentemente mapas PCA/UMAP distinguiendo origen, con la advertencia
de que las proyecciones 2D pueden distorsionar distancias. La cobertura deberá modelarse aparte.
