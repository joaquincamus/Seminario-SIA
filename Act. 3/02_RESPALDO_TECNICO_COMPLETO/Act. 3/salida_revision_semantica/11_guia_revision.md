# Obj2 / Act. 3 — Paso 11: revisión humana asistida

**Aún no hay validación científica automática.** Este paso selecciona ejemplos para inspección humana reproducible.

- Registros totales: **274** (46 academia, 228 mercado).
- Clusters principales: **8** (K=5 academia, K=3 mercado).
- Registros muestreados: **40**: dos centrales, dos periféricos y uno aleatorio por grupo.
- Pares evidencia–ESCO: **116**; hasta tres URI por registro.
- Localización literal normalizada de evidencia en la fuente: **{'LOCALIZADA_LITERAL_NORMALIZADA': 116}**.

## Cómo revisar

1. Abre `11_revision_clusters.csv` con Excel o el editor de CSV de VS Code. Para cada cluster contrasta el nombre propuesto con la descripción y los cinco registros de `11_muestra_registros.csv`. Rellena `decision_humana` (APROBAR / MODIFICAR / RECHAZAR / PENDIENTE), etiqueta validada, evidencia consultada, observaciones, responsable y fecha.
2. En `11_revision_relaciones_texto_esco.csv`, verifica que la evidencia original en su contexto realmente justifique la URI y la etiqueta ESCO. Consulta el CSV de `Obj2/Act. 1/`, columna y número de fila indicados. Rellena `decision_humana` (CORRECTA / INCORRECTA / AMBIGUA / PENDIENTE), observaciones, responsable y fecha.
3. `NO_LOCALIZADA_LITERAL_REVISAR` solo significa que el fragmento no se encontró literalmente en el texto fuente después de normalización básica. **No prueba que sea incorrecto.** Una coincidencia literal tampoco prueba que el mapeo semántico sea correcto.
4. Documenta las decisiones problemáticas sin editar ni eliminar los originales; cualquier corrección requerirá un pipeline versionado y repetir los resultados dependientes.

## Precauciones

- Muestra **dirigida**, no estimador estadístico representativo: los centrales y periféricos se eligen deliberadamente. No extrapolar porcentajes de error a todos los registros.
- Las etiquetas ESCO y los nombres de cluster siguen siendo provisionales.
- Las 14 ofertas sin ESCO están excluidas de las matrices y requieren una revisión aparte.
- No se han medido cobertura curricular, pertinencia o brechas academia–mercado.
- El script preserva los dos CSV de decisiones si ya existen: ejecutarlo de nuevo **no los sobrescribe**.
