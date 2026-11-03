"""Obj2 / Actividad 3 - Paso 11: muestra reproducible para revisión humana.

Ejecutar con ▶ en VS Code. No entrena modelos, no cambia los CSV originales,
no afirma haber validado semánticamente los emparejamientos texto–ESCO.
Solo utiliza bibliotecas estándar de Python.
"""
from __future__ import annotations

import csv
import hashlib
import json
import random
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

BASE = Path(__file__).resolve().parent
ACT1 = BASE.parent / "Act. 1"
OUT = BASE / "salida_revision_semantica"

RUTAS = {
    "asignaciones": BASE / "salida_seleccion_k" / "08_asignaciones_principales.csv",
    "clusters": BASE / "salida_seleccion_k" / "08_clusters_principales.csv",
    "revision_clusters": BASE / "salida_seleccion_k" / "08_revision_humana_clusters.csv",
    "distintivas": BASE / "salida_seleccion_k" / "08_competencias_distintivas.csv",
    "relaciones": BASE / "salida_textos" / "03_relaciones_trazables.csv",
    "academia": ACT1 / "Perfiles_Normalizados_ESCO_12.csv",
    "mercado": ACT1 / "Ofertas_Normalizadas_ESCO_diccionario.csv",
}

SEMILLA = 2026
EJEMPLOS_POR_CLUSTER = 5      # 2 cercanos, 2 lejanos y 1 aleatorio
COMPETENCIAS_POR_EJEMPLO = 3  # un criterio distintivo y otras posiciones


def leer_csv(ruta: Path) -> list[dict[str, str]]:
    with ruta.open("r", encoding="utf-8-sig", newline="") as handle:
        lector = csv.DictReader(handle, delimiter=";")
        if not lector.fieldnames or len(lector.fieldnames) < 2:
            raise ValueError(f"CSV sin columnas válidas o delimitador incorrecto: {ruta}")
        return list(lector)


def escribir_csv(ruta: Path, columnas: list[str], datos: list[dict], *, preservar: bool = False):
    if preservar and ruta.exists():
        return False
    with ruta.open("w", encoding="utf-8-sig", newline="") as handle:
        escritor = csv.DictWriter(handle, fieldnames=columnas, delimiter=";", extrasaction="ignore")
        escritor.writeheader()
        escritor.writerows(datos)
    return True


def validar_columnas(datos: list[dict], columnas: set[str], nombre: str):
    if not datos:
        raise ValueError(f"Sin filas: {nombre}")
    faltantes = columnas - set(datos[0])
    if faltantes:
        raise ValueError(f"Columnas faltantes en {nombre}: {sorted(faltantes)}")


def normalizar(texto: str) -> str:
    s = unicodedata.normalize("NFKD", texto or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s.casefold()).strip()


def firmar(ruta: Path) -> str:
    h = hashlib.sha256()
    with ruta.open("rb") as f:
        for fragmento in iter(lambda: f.read(1024 * 1024), b""):
            h.update(fragmento)
    return h.hexdigest()


def seleccionar_registros(filas: list[dict], key: tuple[str, str, str]) -> list[dict]:
    """Dos prototipos, dos periféricos y uno con selección aleatoria reproducible."""
    orden = sorted(filas, key=lambda x: (-float(x["similitud_coseno_centroide"]), x["id_registro"]))
    seleccion = {}
    for registro in orden[:2]:
        seleccion[registro["id_registro"]] = (registro, "CENTRAL")
    for registro in orden[-2:]:
        seleccion.setdefault(registro["id_registro"], (registro, "PERIFERICO"))
    candidatos = [r for r in orden if r["id_registro"] not in seleccion]
    if candidatos:
        seed = int(hashlib.sha256(("|".join(key) + f"|{SEMILLA}").encode()).hexdigest()[:16], 16)
        aleatorio = random.Random(seed).choice(candidatos)
        seleccion[aleatorio["id_registro"]] = (aleatorio, "ALEATORIO_REPRODUCIBLE")
    # Aunque haya clusters pequeños, no duplicar registros.
    return [dict(registro, criterio_muestreo=criterio) for registro, criterio in seleccion.values()]


def seleccionar_competencias(relaciones: list[dict], uris_distintivas: list[str]) -> list[dict]:
    orden = sorted(relaciones, key=lambda r: int(r["posicion"]))
    seleccion: list[dict] = []
    motivos: dict[str, str] = {}
    por_uri = {r["uri_esco"]: r for r in orden}
    for uri in uris_distintivas:
        if uri in por_uri:
            seleccion.append(por_uri[uri]); motivos[uri] = "DISTINTIVA_DEL_CLUSTER"; break
    for r, motivo in [(orden[0], "PRIMERA_ASIGNADA"), (orden[-1], "ULTIMA_ASIGNADA")]:
        if r["uri_esco"] not in motivos and len(seleccion) < COMPETENCIAS_POR_EJEMPLO:
            seleccion.append(r); motivos[r["uri_esco"]] = motivo
    for r in orden:
        if len(seleccion) >= COMPETENCIAS_POR_EJEMPLO:
            break
        if r["uri_esco"] not in motivos:
            seleccion.append(r); motivos[r["uri_esco"]] = "OTRA_ASIGNADA"
    return [dict(r, criterio_competencia=motivos[r["uri_esco"]]) for r in seleccion]


def localizar_evidencia(evidencia: str, fuente: dict, origen: str) -> tuple[str, str]:
    if origen == "academia":
        campos = ["Asignaturas", "Perfil_Egreso"]
    else:
        campos = ["habilidades_crudas", "texto_bruto"]
    objetivo = normalizar(evidencia)
    if not objetivo:
        return "EVIDENCIA_VACIA", ""
    for campo in campos:
        if objetivo in normalizar(fuente.get(campo, "")):
            return "LOCALIZADA_LITERAL_NORMALIZADA", campo
    return "NO_LOCALIZADA_LITERAL_REVISAR", " | ".join(campos)


def main():
    faltantes = [str(p) for p in RUTAS.values() if not p.is_file()]
    if faltantes:
        raise FileNotFoundError(
            "No se encontraron entradas. Pon este script en Obj2/Act. 3 y conserva las salidas previas.\n"
            + "\n".join(faltantes)
        )
    a = leer_csv(RUTAS["asignaciones"])
    c = leer_csv(RUTAS["clusters"])
    rev = leer_csv(RUTAS["revision_clusters"])
    d = leer_csv(RUTAS["distintivas"])
    rel = leer_csv(RUTAS["relaciones"])
    aca = leer_csv(RUTAS["academia"])
    mer = leer_csv(RUTAS["mercado"])
    validar_columnas(a, {"grupo", "k", "cluster", "id_registro", "fila_csv", "origen", "similitud_coseno_centroide"}, "asignaciones")
    validar_columnas(rel, {"origen", "fila_csv", "id_registro", "posicion", "uri_esco", "etiqueta_esco", "evidencia_original"}, "relaciones")
    validar_columnas(d, {"grupo", "k", "cluster", "uri_esco", "puesto_distintivo"}, "distintivas")
    validar_columnas(c, {"grupo", "k", "cluster", "etiqueta_propuesta_no_validada", "n_registros", "top_3_etiquetas_distintivas", "ejemplos_de_registros"}, "clusters")

    if len(a) != 274 or Counter(x["origen"] for x in a) != {"academia": 46, "mercado": 228}:
        raise ValueError("No coinciden 274 registros principales (46 academia y 228 mercado).")
    if len(c) != 8 or len(rev) != 8:
        raise ValueError("Se esperaban ocho fichas principales de clusters.")

    fuentes = {"academia": aca, "mercado": mer}
    rel_index: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for r in rel:
        rel_index[(r["origen"], r["fila_csv"], r["id_registro"])].append(r)
    grupos: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for r in a:
        grupos[(r["grupo"], r["k"], r["cluster"])].append(r)
    distintos: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    for r in sorted(d, key=lambda r: int(r["puesto_distintivo"])):
        distintos[(r["grupo"], r["k"], r["cluster"])].append(r["uri_esco"])

    if set(grupos) != {(r["grupo"], r["k"], r["cluster"]) for r in c}:
        raise ValueError("Los clusters no corresponden a las asignaciones principales.")
    OUT.mkdir(exist_ok=True)
    ejemplos = []
    auditoria = []
    resumen_clusters = []
    for cl in sorted(c, key=lambda r: (r["grupo"], int(r["cluster"]))):
        key = cl["grupo"], cl["k"], cl["cluster"]
        reg_cluster = grupos[key]
        if len(reg_cluster) != int(cl["n_registros"]):
            raise ValueError(f"Tamaño contradictorio en cluster {key}")
        elegidos = seleccionar_registros(reg_cluster, key)
        resumen_clusters.append({
            "grupo": key[0], "k": key[1], "cluster": key[2],
            "etiqueta_propuesta_no_validada": cl["etiqueta_propuesta_no_validada"],
            "n_registros": len(reg_cluster), "n_ejemplos_para_auditar": len(elegidos),
            "top_3_etiquetas_distintivas": cl["top_3_etiquetas_distintivas"],
            "ejemplos_originales_paso8": cl["ejemplos_de_registros"],
            "decision_humana": "PENDIENTE", "etiqueta_validada": "", "evidencia_revisada": "",
            "observaciones": "", "responsable_revision": "", "fecha_revision": ""
        })
        for r in elegidos:
            origen = r["origen"]
            fila = int(r["fila_csv"])
            if fila < 2 or fila - 2 >= len(fuentes[origen]):
                raise ValueError(f"Fila CSV fuera del rango para {origen}: {fila}")
            fuente = fuentes[origen][fila - 2]
            id_real = (fuente["Universidad"] + " | " + fuente["Carrera"] if origen == "academia" else fuente["job_id"])
            if id_real != r["id_registro"]:
                raise ValueError(f"Identificador de origen no coincide con fila CSV {fila}: {origen}")
            campor = (origen, r["fila_csv"], r["id_registro"])
            rr = rel_index.get(campor, [])
            if not rr:
                raise ValueError(f"No existen relaciones trazables para {campor}")
            nombre = fuente["Carrera"] if origen == "academia" else fuente["titulo"]
            ejemplos.append({
                "grupo": key[0], "k": key[1], "cluster": key[2],
                "etiqueta_cluster_no_validada": cl["etiqueta_propuesta_no_validada"],
                "criterio_muestreo": r["criterio_muestreo"], "origen": origen,
                "id_registro": r["id_registro"], "fila_csv": fila,
                "institucion_o_empresa": fuente["Universidad"] if origen == "academia" else fuente["empresa"],
                "nombre": nombre, "similitud_coseno_centroide": r["similitud_coseno_centroide"],
                "n_competencias": len(rr), "archivo_fuente": RUTAS[origen].name,
            })
            for comp in seleccionar_competencias(rr, distintos[key]):
                evidencia = comp["evidencia_original"]
                marca, campo = localizar_evidencia(evidencia, fuente, origen)
                auditoria.append({
                    "grupo": key[0], "k": key[1], "cluster": key[2],
                    "criterio_muestreo_registro": r["criterio_muestreo"],
                    "criterio_muestreo_competencia": comp["criterio_competencia"],
                    "origen": origen, "id_registro": r["id_registro"],
                    "fila_csv": fila, "nombre": nombre,
                    "posicion_competencia": comp["posicion"],
                    "uri_esco": comp["uri_esco"], "etiqueta_esco": comp["etiqueta_esco"],
                    "evidencia_original": evidencia,
                    "localizacion_literal_en_fuente": marca, "columna_fuente": campo,
                    "archivo_fuente": RUTAS[origen].name,
                    "decision_humana": "PENDIENTE", "observaciones": "",
                    "responsable_revision": "", "fecha_revision": "",
                })

    ejemplos_cols = ["grupo", "k", "cluster", "etiqueta_cluster_no_validada", "criterio_muestreo", "origen", "id_registro", "fila_csv", "institucion_o_empresa", "nombre", "similitud_coseno_centroide", "n_competencias", "archivo_fuente"]
    auditoria_cols = ["grupo", "k", "cluster", "criterio_muestreo_registro", "criterio_muestreo_competencia", "origen", "id_registro", "fila_csv", "nombre", "posicion_competencia", "uri_esco", "etiqueta_esco", "evidencia_original", "localizacion_literal_en_fuente", "columna_fuente", "archivo_fuente", "decision_humana", "observaciones", "responsable_revision", "fecha_revision"]
    cluster_cols = ["grupo", "k", "cluster", "etiqueta_propuesta_no_validada", "n_registros", "n_ejemplos_para_auditar", "top_3_etiquetas_distintivas", "ejemplos_originales_paso8", "decision_humana", "etiqueta_validada", "evidencia_revisada", "observaciones", "responsable_revision", "fecha_revision"]
    escribir_csv(OUT / "11_muestra_registros.csv", ejemplos_cols, ejemplos)
    nuevo1 = escribir_csv(OUT / "11_revision_relaciones_texto_esco.csv", auditoria_cols, auditoria, preservar=True)
    nuevo2 = escribir_csv(OUT / "11_revision_clusters.csv", cluster_cols, resumen_clusters, preservar=True)
    estados_localizacion = dict(Counter(a["localizacion_literal_en_fuente"] for a in auditoria))
    resumen = {
        "paso": 11, "objetivo": "Auditoría humana dirigida, sin cambios al pipeline",
        "semilla": SEMILLA, "muestra_por_cluster": EJEMPLOS_POR_CLUSTER,
        "competencias_por_registro_objetivo": COMPETENCIAS_POR_EJEMPLO,
        "clusters": len(c), "registros_total": len(a),
        "registros_muestreados": len(ejemplos), "pares_texto_esco_para_revision": len(auditoria),
        "localizacion_literal_evidencia": estados_localizacion,
        "plantilla_relaciones_creada": nuevo1,
        "plantilla_clusters_creada": nuevo2,
        "validacion_humana_realizada_automaticamente": False,
        "entradas_sha256": {k: firmar(ruta) for k, ruta in RUTAS.items()}
    }
    (OUT / "11_resumen_muestreo.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")
    guia = f"""# Obj2 / Act. 3 — Paso 11: revisión humana asistida

**Aún no hay validación científica automática.** Este paso selecciona ejemplos para inspección humana reproducible.

- Registros totales: **{len(a)}** (46 academia, 228 mercado).
- Clusters principales: **{len(c)}** (K=5 academia, K=3 mercado).
- Registros muestreados: **{len(ejemplos)}**: dos centrales, dos periféricos y uno aleatorio por grupo.
- Pares evidencia–ESCO: **{len(auditoria)}**; hasta tres URI por registro.
- Localización literal normalizada de evidencia en la fuente: **{estados_localizacion}**.

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
"""
    (OUT / "11_guia_revision.md").write_text(guia, encoding="utf-8")
    print("PASO 11 - MUESTRA PARA REVISION SEMANTICA")
    print(f"  Clusters de trabajo: {len(c)}")
    print(f"  Registros seleccionados: {len(ejemplos)} de {len(a)}")
    print(f"  Pares texto–ESCO seleccionados: {len(auditoria)}")
    print(f"  Localización de evidencia: {estados_localizacion}")
    print(f"  Revisión de relaciones: {'CREADA' if nuevo1 else 'CONSERVADA (no sobrescrita)'}")
    print(f"  Revisión de clusters: {'CREADA' if nuevo2 else 'CONSERVADA (no sobrescrita)'}")
    print(f"  Carpeta: {OUT}")
    print("  AVISO: ninguna asignación ESCO ha sido aprobada automáticamente.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("ERROR PASO 11:", exc)
        raise
