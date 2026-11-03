# OB2 — Actividad 3: decisión de cierre y condiciones de uso

**Versión de referencia del equipo: desarrollo original de Andrés, inalterado.**

## Decisión

Se **conserva como entrega técnica final** la implementación de Andrés. Se aceptan **K=5 académico y K=3 laboral para caracterización exploratoria de familias**, con respaldo independiente de los cálculos y una revisión documental de las ocho familias. Son resultados reproducibles y útiles dentro de OB2, **no una validación docente o curricular completa**.

| Fuente | Registros analizados | K de trabajo aceptado para uso descriptivo | Silhouette coseno | ARI entre semillas |
|---|---:|---:|---:|---:|
| Academia | 46 | 5 | 0,516 | 0,964 |
| Mercado laboral | 228 de 242 | 3 | 0,212 | 0,972 |

Las 14 ofertas sin competencias seleccionadas se mantienen identificadas como no clasificables, no como puestos sin requisitos.

## Alcance de revisión independiente

- **Ocho macrofamilias revisadas:** compatibles con una **interpretación amplia**, con advertencias de heterogeneidad (grupo informático de academia, electricidad/mecánica, bloque de operaciones laborales).
- **116 relaciones texto–ESCO revisadas documentalmente:** 60 con concordancia textual aparente, 29 con afinidad temática plausible y 27 con observaciones prioritarias. **No son decisiones humanas validadas ni una estimación estadística del error total.**
- El trabajo original, sus nombres de grupos, parámetros y resultados **no fue alterado**. El registro de los casos observados está en el anexo independiente del respaldo técnico.

## Principales precauciones

La elección de K es una decisión descriptiva fundada en compromiso entre estabilidad, separación, tamaño e interpretabilidad: K=7 separa más especialidades académicas y K=2 tiene mejor silhouette en mercado, por lo que **no se atribuye optimalidad matemática única** a K=5/K=3. Los indicadores ARI publicados corresponden a semillas, no a remuestreo.

La extracción ESCO mantiene posibles sobreinterpretaciones (por ejemplo, `Primavera P6` → software de programación minera; `ISO 50001` → gestión de calidad), sin evidencia de que todas las correspondencias sean válidas. **No se convierten grupos ni similitudes en porcentajes de cobertura o brecha curricular.** Los URI originales se conservan para Apriori (OB3).

## Archivos para citar y desarrollar OB3

- `Tablas/08_asignaciones_principales.csv`: pertenencia de cada carrera/vacante al grupo.
- `Tablas/08_clusters_principales.csv`: ocho familias descriptivas, con etiquetas provisionales originales.
- `Tablas/06_metricas_por_k.csv`: comparación de parámetros K.
- `Figuras/`: codo, silhouette, ARI, PCA para ambas fuentes.
- `Informes/`: explicaciones técnicas originales de Andrés.
- `02_RESPALDO_TECNICO_COMPLETO/REVISION_DOCUMENTAL_INDEPENDIENTE/` (en el otro paquete): anexo de revisión documental de ocho familias y 116 relaciones.

**Estado final que sí puede afirmarse:** versión técnica adoptada y revisión documental independiente concluida; resultados de clúster aceptados **con alcance exploratorio y observaciones**. Aprobación humana/docente exhaustiva no documentada.
