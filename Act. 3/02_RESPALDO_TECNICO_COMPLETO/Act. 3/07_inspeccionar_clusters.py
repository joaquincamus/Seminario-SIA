#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OBJ2 / ACT. 3 / PASO 7: auditoría de clusters candidatos.

EJECUCIÓN EN VISUAL STUDIO CODE:
  1. Guardar este archivo en DESARROLLO/Obj2/Act. 3/
  2. Mantener las carpetas salida_textos/, salida_vectores_registros/ y
     salida_evaluacion_kmeans/ de los pasos 03, 05 y 06.
  3. Abrir este archivo y pulsar el botón ▶ Ejecutar archivo Python.

NO modifica datos originales, NO vuelve a ejecutar K-Means y NO calcula
cobertura o pertinencia curricular. Interpreta las particiones exploratorias
mediante competencias ESCO y registros representativos. Los IDs de clusters
son locales a cada población/K; no se comparan entre distintos K.

Requiere numpy (ya utilizado en los pasos 04-06); resto biblioteca estándar.
"""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

# ====================== CONFIGURACIÓN ======================
ACT3 = Path(__file__).resolve().parent
CARPETA_03 = ACT3 / "salida_textos"
CARPETA_05 = ACT3 / "salida_vectores_registros"
CARPETA_06 = ACT3 / "salida_evaluacion_kmeans"
SALIDA = ACT3 / "salida_inspeccion_clusters"

# Candidatos exploratorios: no son elecciones definitivas.
# Se eligieron para contrastar estructura interna, estabilidad y tamaños.
CANDIDATOS = {"academia": (5, 7, 8), "mercado": (2, 3, 4), "conjunto": (3, 4, 8)}
TOP_COMPETENCIAS = 8
EJEMPLOS_POR_CLUSTER = 3
SEPARADOR_CSV = ";"
# ===========================================================


def leer_csv(path: Path, obligatorias: set[str]) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(f"Archivo requerido no encontrado: {path}")
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        lector = csv.DictReader(f, delimiter=SEPARADOR_CSV)
        columnas = set(lector.fieldnames or [])
        if not obligatorias.issubset(columnas):
            raise ValueError(f"Columnas faltantes en {path.name}: {sorted(obligatorias - columnas)}")
        filas = list(lector)
    if any(None in r or any(v is None for v in r.values()) for r in filas):
        raise ValueError(f"Columnas irregulares en {path.name}; verificar separador ';'.")
    return filas


def escribir_csv(path: Path, filas: list[dict], columnas: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=columnas, delimiter=SEPARADOR_CSV, extrasaction="ignore")
        w.writeheader()
        w.writerows(filas)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def clave_registro(row: dict) -> tuple[str, str, str]:
    return (row["origen"], str(row["fila_csv"]), row["id_registro"])


def nombres_registro(row: dict) -> str:
    if row["origen"] == "academia":
        return str(row.get("carrera") or "SIN_NOMBRE")
    return str(row.get("titulo_oferta") or "SIN_TITULO")


def preparar_entradas():
    f_ind = CARPETA_05 / "05_indice_registros.csv"
    f_vec = CARPETA_05 / "05_vectores_registros.npy"
    f_res05 = CARPETA_05 / "05_resumen_agregacion.json"
    f_asig = CARPETA_06 / "06_asignaciones_exploratorias.csv"
    f_dist = CARPETA_06 / "06_distribucion_clusters.csv"
    f_met = CARPETA_06 / "06_metricas_por_k.csv"
    f_res06 = CARPETA_06 / "06_resumen_evaluacion.json"
    f_rel = CARPETA_03 / "03_relaciones_trazables.csv"
    f_cat = CARPETA_03 / "03_catalogo_competencias_esco.csv"
    for p in (f_ind, f_vec, f_res05, f_asig, f_dist, f_met, f_res06, f_rel, f_cat):
        if not p.is_file():
            raise FileNotFoundError(f"Falta {p}. Ejecuta los pasos anteriores antes del 07.")

    resumen05 = json.loads(f_res05.read_text(encoding="utf-8-sig"))
    resumen06 = json.loads(f_res06.read_text(encoding="utf-8-sig"))
    for file, expected in resumen05.get("salidas_sha256", {}).items():
        if file in (f_ind.name, f_vec.name):
            path = CARPETA_05 / file
            if sha256(path) != expected:
                raise ValueError(f"SHA-256 no coincide para {file}: entradas 05 alteradas.")
    for file, expected in resumen06.get("entradas_sha256", {}).items():
        if file in (f_ind.name, f_vec.name, f_res05.name):
            path = CARPETA_05 / file
            if sha256(path) != expected:
                raise ValueError(f"El paso 06 se generó con otro archivo: {file}.")

    x = np.load(f_vec, allow_pickle=False)
    indice = leer_csv(f_ind, {"fila_vector_0_based", "origen", "fila_csv", "id_registro", "n_competencias_esco"})
    if x.shape != (len(indice), 384) or not np.isfinite(x).all():
        raise ValueError("Matriz del paso 05 con dimensiones incorrectas o valores no finitos.")
    if not np.allclose(np.linalg.norm(x, axis=1), 1, atol=2e-5):
        raise ValueError("Los vectores de registros no están normalizados L2.")
    por_clave = {}
    for i, row in enumerate(indice):
        if int(row["fila_vector_0_based"]) != i:
            raise ValueError("Orden del índice distinto al orden de la matriz.")
        key = clave_registro(row)
        if key in por_clave:
            raise ValueError(f"Registro duplicado en 05: {key}")
        por_clave[key] = i

    catalogo = leer_csv(f_cat, {"uri_esco", "etiqueta_esco"})
    etiqueta_uri = {}
    for r in catalogo:
        u = r["uri_esco"].strip()
        if u in etiqueta_uri and etiqueta_uri[u] != r["etiqueta_esco"].strip():
            raise ValueError(f"URI con etiquetas contradictorias: {u}")
        etiqueta_uri[u] = r["etiqueta_esco"].strip()

    relaciones = leer_csv(f_rel, {"origen", "fila_csv", "id_registro", "uri_esco", "etiqueta_esco"})
    por_registro = defaultdict(set)
    for r in relaciones:
        key = clave_registro(r)
        u = r["uri_esco"].strip()
        if key not in por_clave:
            raise ValueError(f"Relación ESCO sin registro válido: {key}")
        if u not in etiqueta_uri:
            raise ValueError(f"URI sin etiqueta en catálogo: {u}")
        por_registro[por_clave[key]].add(u)
    for i, r in enumerate(indice):
        if len(por_registro[i]) != int(r["n_competencias_esco"]):
            raise ValueError(f"Registro {i}: discrepancia de competencias entre pasos 03 y 05.")
        uris_indice = set(json.loads(r["uris_esco_json"]))
        if uris_indice != por_registro[i]:
            raise ValueError(f"URI ESCO distintas entre los pasos 03 y 05, registro {i}.")

    asign = leer_csv(f_asig, {"grupo", "k", "fila_vector_0_based", "origen", "fila_csv", "id_registro", "cluster_provisional"})
    distrib = leer_csv(f_dist, {"grupo", "k", "cluster_provisional", "total", "academia", "mercado"})
    metricas = leer_csv(f_met, {"grupo", "k", "estado", "silueta_coseno", "estabilidad_ari_media", "cluster_mas_pequeno"})

    # Se comprueba también que un candidato contiene exactamente las posiciones
    # previstas y que su distribución coincide con el resumen del paso 06.
    a_por_combinacion = defaultdict(list)
    for row in asign:
        try:
            idx = int(row["fila_vector_0_based"])
            k = int(row["k"])
            cid = int(row["cluster_provisional"])
        except ValueError as e:
            raise ValueError(f"Valor no numérico en asignaciones del paso 06: {row}") from e
        if not (0 <= idx < len(indice)):
            raise ValueError("Índice de asignación fuera de rango")
        original = indice[idx]
        if clave_registro(row) != clave_registro(original):
            raise ValueError(f"Asignación del paso 06 no corresponde al índice 05, fila {idx}")
        if not 0 <= cid < k:
            raise ValueError("ID de cluster fuera de rango")
        a_por_combinacion[(row["grupo"], k)].append((idx, cid))
    distrib_lookup = {(r["grupo"], int(r["k"]), int(r["cluster_provisional"])): r for r in distrib}
    metricas_lookup = {(r["grupo"], int(r["k"])): r for r in metricas}
    for grupo, ks in CANDIDATOS.items():
        esperado = {i for i, r in enumerate(indice) if grupo == "conjunto" or r["origen"] == grupo}
        for k in ks:
            items = a_por_combinacion.get((grupo, k), [])
            pos = [i for i, _ in items]
            if len(pos) != len(esperado) or len(set(pos)) != len(pos) or set(pos) != esperado:
                raise ValueError(f"Asignaciones incompletas o repetidas para {grupo} K={k}")
            if (grupo, k) not in metricas_lookup or metricas_lookup[(grupo, k)]["estado"] != "OK":
                raise ValueError(f"No se evaluó correctamente {grupo} K={k} en paso 06")
            reales = Counter(c for _, c in items)
            for cid in range(k):
                fila_dist = distrib_lookup.get((grupo, k, cid))
                if fila_dist is None or int(fila_dist["total"]) != reales[cid]:
                    raise ValueError(f"Distribución inconsistente para {grupo}, K={k}, cluster={cid}")
                acad = sum(indice[i]["origen"] == "academia" for i, c in items if c == cid)
                mercado = reales[cid] - acad
                if int(fila_dist["academia"]) != acad or int(fila_dist["mercado"]) != mercado:
                    raise ValueError(f"Composición inconsistente en {grupo}, K={k}, cluster={cid}")
    return x, indice, por_registro, etiqueta_uri, a_por_combinacion, metricas_lookup, (f_ind, f_vec, f_asig, f_dist, f_met, f_rel, f_cat)


def ejecutar():
    x, indice, por_registro, etiquetas, asign, metricas, archivos_entrada = preparar_entradas()
    SALIDA.mkdir(exist_ok=True, parents=True)

    perfiles, destacados, representantes, asignaciones, panorama, alertas = [], [], [], [], [], []
    informe = ["# Paso 7: inspección semántica exploratoria de clusters", "",
               "Los clusters se interpretan mediante **etiquetas ESCO** y ejemplos de registros.",
               "La revisión humana de las relaciones origen–ESCO sigue pendiente. El nombre de cada grupo es provisional.",
               "Los IDs numéricos cambian entre valores de K y **no son equivalentes** entre particiones.",
               "Ni la silueta ni la similitud al centroide equivalen a cobertura curricular.", ""]

    for grupo, ks in CANDIDATOS.items():
        poblacion = [i for i, r in enumerate(indice) if grupo == "conjunto" or r["origen"] == grupo]
        # La prevalencia "afuera" se calcula solo dentro de la misma población.
        poblacion_set = set(poblacion)
        for k in ks:
            items = asign[(grupo, k)]
            met = metricas[(grupo, k)]
            tamaños = Counter(c for _, c in items)
            panorama.append({
                "grupo": grupo, "k": k, "n_registros": len(poblacion),
                "silueta_coseno": met["silueta_coseno"], "estabilidad_ari_media": met["estabilidad_ari_media"],
                "estabilidad_ari_min": met.get("estabilidad_ari_min", ""),
                "cluster_mas_pequeno": min(tamaños.values()),
                "cluster_mas_grande": max(tamaños.values()),
                "clusters_menores_5": sum(n < 5 for n in tamaños.values()),
                "clusters_unitarios": sum(n == 1 for n in tamaños.values()),
                "estado": "CANDIDATO_PENDIENTE_REVISION_HUMANA",
            })
            informe.extend([f"## {grupo.capitalize()}, K={k}",
                            f"Silueta coseno: {float(met['silueta_coseno']):.3f}; ARI medio: {float(met['estabilidad_ari_media']):.3f}. "
                            f"Tamaños: {', '.join(str(tamaños[c]) for c in range(k))}.", ""])
            for cid in range(k):
                miembros = sorted(i for i, c in items if c == cid)
                n = len(miembros)
                miembros_set = set(miembros)
                otros = poblacion_set - miembros_set
                preval_dentro = Counter(u for i in miembros for u in por_registro[i])
                preval_fuera = Counter(u for i in otros for u in por_registro[i])
                # Reportar URI originales: las etiquetas ESCO no identifican unívocamente.
                compartidas = sum(freq > 1 for freq in preval_dentro.values())
                valores_uris = list(preval_dentro)
                candidates = [u for u in valores_uris if preval_dentro[u] >= (2 if n >= 3 else 1)]
                if not candidates:
                    candidates = valores_uris

                def distinto(u: str):
                    dentro = preval_dentro[u] / n
                    afuera = preval_fuera[u] / len(otros) if otros else 0.0
                    return (dentro - afuera, preval_dentro[u], -preval_fuera[u], u)

                frecuentes = sorted(candidates, key=lambda u: (-preval_dentro[u], -distinto(u)[0], u))[:TOP_COMPETENCIAS]
                distintivas = sorted(candidates, key=lambda u: (-distinto(u)[0], -preval_dentro[u], u))[:TOP_COMPETENCIAS]
                for tipo, uris in (("frecuente_en_cluster", frecuentes), ("distintiva_vs_resto_poblacion", distintivas)):
                    for puesto, u in enumerate(uris, 1):
                        dentro = preval_dentro[u] / n
                        fuera = preval_fuera[u] / len(otros) if otros else 0.0
                        destacados.append({
                            "grupo": grupo, "k": k, "cluster_provisional": cid,
                            "tipo_ranking": tipo, "puesto": puesto, "uri_esco": u,
                            "etiqueta_esco": etiquetas[u], "registros_con_competencia_cluster": preval_dentro[u],
                            "registros_del_cluster": n, "proporcion_dentro": round(dentro, 6),
                            "registros_con_competencia_fuera": preval_fuera[u],
                            "registros_fuera": len(otros), "proporcion_fuera": round(fuera, 6),
                            "diferencia_prevalencia": round(dentro - fuera, 6),
                            "nota": "Proporción de registros, NO porcentaje de cobertura curricular",
                        })

                centro = np.mean(x[miembros], axis=0)
                centro /= np.linalg.norm(centro)
                simil = {i: float(np.dot(x[i], centro)) for i in miembros}
                orden = sorted(miembros, key=lambda i: (-simil[i], i))
                representativos = orden[:EJEMPLOS_POR_CLUSTER]
                for rank, i in enumerate(representativos, 1):
                    r = indice[i]
                    representantes.append({
                        "grupo": grupo, "k": k, "cluster_provisional": cid,
                        "puesto": rank, "fila_vector_0_based": i, "origen": r["origen"],
                        "fila_csv": r["fila_csv"], "id_registro": r["id_registro"],
                        "institucion": r.get("universidad", ""), "nombre": nombres_registro(r),
                        "similitud_coseno_al_centroide": round(simil[i], 6),
                        "n_competencias_esco": r["n_competencias_esco"],
                    })
                for i in miembros:
                    r = indice[i]
                    asignaciones.append({
                        "grupo": grupo, "k": k, "cluster_provisional": cid,
                        "fila_vector_0_based": i, "origen": r["origen"],
                        "fila_csv": r["fila_csv"], "id_registro": r["id_registro"],
                        "universidad": r.get("universidad", ""), "carrera": r.get("carrera", ""),
                        "job_id": r.get("job_id", ""), "titulo_oferta": r.get("titulo_oferta", ""),
                        "n_competencias_esco": r["n_competencias_esco"],
                        "similitud_coseno_centroide": round(simil[i], 6),
                    })
                academicos = sum(indice[i]["origen"] == "academia" for i in miembros)
                top_3 = " | ".join(etiquetas[u] for u in distintivas[:3])
                alerta = []
                if n < 5:
                    alerta.append("CLUSTER_PEQUENO_MENOS_5")
                if not compartidas:
                    alerta.append("SIN_COMPETENCIAS_COMPARTIDAS_POR_DOS_REGISTROS")
                if grupo == "conjunto" and (academicos == 0 or academicos == n):
                    alerta.append("CLUSTER_UN_SOLO_ORIGEN")
                perfiles.append({
                    "grupo": grupo, "k": k, "cluster_provisional": cid, "n_registros": n,
                    "n_academia": academicos, "n_mercado": n - academicos,
                    "proporcion_academia": round(academicos / n, 6),
                    "instituciones_distintas": len({indice[i].get("universidad", "").strip() for i in miembros if indice[i]["origen"] == "academia"}),
                    "competencias_uri_distintas": len(preval_dentro),
                    "competencias_compartidas_en_2_o_mas_registros": compartidas,
                    "similitud_media_al_centroide": round(float(np.mean(list(simil.values()))), 6),
                    "top_3_etiquetas_distintivas_descriptivas": top_3,
                    "ejemplos_de_registros": " | ".join(nombres_registro(indice[i]) for i in representativos),
                    "alertas": " | ".join(alerta), "etiqueta_manual_propuesta": "",
                    "decision_revision_humana": "PENDIENTE",
                })
                if alerta:
                    alertas.append({"grupo": grupo, "k": k, "cluster": cid, "tipo": " | ".join(alerta)})
                informe.append(f"### Cluster {cid} — {n} registros ({academicos} carreras; {n-academicos} ofertas)")
                informe.append(f"- Competencias distintivas (por diferencia de prevalencia): {top_3 or 'sin competencias suficientes' }.")
                informe.append(f"- Ejemplos cercanos al centroide: {'; '.join(nombres_registro(indice[i]) for i in representativos)}.")
                if alerta:
                    informe.append(f"- Revisar: {', '.join(alerta)}.")
                informe.append("")
            print(f"  {grupo:8s} K={k:2d}: tamaños {[tamaños[c] for c in range(k)]} | {len(poblacion)} registros")

    escribir_csv(SALIDA / "07_panorama_candidatos.csv", panorama,
                 ["grupo", "k", "n_registros", "silueta_coseno", "estabilidad_ari_media",
                  "estabilidad_ari_min", "cluster_mas_pequeno", "cluster_mas_grande",
                  "clusters_menores_5", "clusters_unitarios", "estado"])
    escribir_csv(SALIDA / "07_perfiles_clusters.csv", perfiles,
                 ["grupo", "k", "cluster_provisional", "n_registros", "n_academia", "n_mercado",
                  "proporcion_academia", "instituciones_distintas", "competencias_uri_distintas",
                  "competencias_compartidas_en_2_o_mas_registros", "similitud_media_al_centroide",
                  "top_3_etiquetas_distintivas_descriptivas", "ejemplos_de_registros",
                  "alertas", "etiqueta_manual_propuesta", "decision_revision_humana"])
    escribir_csv(SALIDA / "07_competencias_por_cluster.csv", destacados,
                 ["grupo", "k", "cluster_provisional", "tipo_ranking", "puesto", "uri_esco",
                  "etiqueta_esco", "registros_con_competencia_cluster", "registros_del_cluster",
                  "proporcion_dentro", "registros_con_competencia_fuera", "registros_fuera",
                  "proporcion_fuera", "diferencia_prevalencia", "nota"])
    escribir_csv(SALIDA / "07_registros_representativos.csv", representantes,
                 ["grupo", "k", "cluster_provisional", "puesto", "fila_vector_0_based", "origen",
                  "fila_csv", "id_registro", "institucion", "nombre", "similitud_coseno_al_centroide",
                  "n_competencias_esco"])
    escribir_csv(SALIDA / "07_asignaciones_candidatos.csv", asignaciones,
                 ["grupo", "k", "cluster_provisional", "fila_vector_0_based", "origen", "fila_csv",
                  "id_registro", "universidad", "carrera", "job_id", "titulo_oferta",
                  "n_competencias_esco", "similitud_coseno_centroide"])
    (SALIDA / "07_informe_inspeccion.md").write_text("\n".join(informe), encoding="utf-8")
    resumen = {
        "etapa": "Obj2 / Act. 3 / Paso 7",
        "estado": "CLUSTERS_INSPECCIONADOS_SIN_K_DEFINITIVO",
        "candidatos": {g: list(ks) for g, ks in CANDIDATOS.items()},
        "conteos": {"registros": len(indice), "competencias_ESCO_distintas": len(etiquetas),
                    "particiones_candidatas": len(panorama), "clusters_inspeccionados": len(perfiles),
                    "filas_competencias_destacadas": len(destacados), "filas_representantes": len(representantes),
                    "filas_asignaciones_candidatos": len(asignaciones),
                    "clusters_con_alertas": len(alertas)},
        "metodo": {
            "clusterizacion": "reusa asignaciones exploratorias del paso 06 (semilla 42)",
            "competencia_frecuente": "frecuencia absoluta por URI dentro del cluster",
            "competencia_distintiva": "proporción dentro del cluster MENOS proporción fuera del cluster, dentro de la misma población",
            "registros_representativos": "mayor coseno con centroide L2 del cluster",
            "alcance": "diagnostico exploratorio; no cobertura, no causalidad, no validación humana",
        },
        "entradas_sha256": {p.name: sha256(p) for p in archivos_entrada},
        "alertas": ["Los conceptos ESCO todavía no han sido validados manualmente contra su evidencia original.",
                    "K no se selecciona automáticamente. No confundir silueta o frecuencia con cobertura curricular.",
                    "En conjunto el mercado tiene 228 ofertas frente a 46 programas académicos.",
                    "Los números de cluster solo identifican una partición específica y no son etiquetas semánticas."],
    }
    (SALIDA / "07_resumen_inspeccion.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nPASO 7 FINALIZADO CORRECTAMENTE")
    print(f"  Candidatos inspeccionados: {len(panorama)}")
    print(f"  Clusters inspeccionados: {len(perfiles)}")
    print(f"  Con alertas de revisión: {len(alertas)}")
    print(f"  Salida: {SALIDA}")
    print("  Revisa: 07_perfiles_clusters.csv, 07_competencias_por_cluster.csv")
    print("  IMPORTANTE: NO se eligió K definitivo ni se calculó cobertura curricular.")


if __name__ == "__main__":
    try:
        print("PASO 7 - INSPECCIÓN DE CLUSTERS CANDIDATOS\n")
        ejecutar()
    except Exception as exc:
        print(f"\nERROR EN EL PASO 7: {type(exc).__name__}: {exc}")
        print("Revisa que este script esté en Obj2/Act. 3 y las carpetas salida_textos, ")
        print("salida_vectores_registros y salida_evaluacion_kmeans estén en la misma carpeta.")
        raise
