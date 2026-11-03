# -*- coding: utf-8 -*-
"""
OBJ2 / ACTIVIDAD 3 / PASO 10
Auditoria tecnica reproducible de los pasos 05, 08 y 09.

Ejecutar con ▶ en Visual Studio Code. No depende de la carpeta de la terminal.
NO modifica ningun CSV de entrada, NO reentrena modelos y NO calcula cobertura.
Requiere numpy y pandas (ya usados en los pasos anteriores).

Salida: salida_auditoria_act3/
  10_control_integridad.csv
  10_pendientes_revision_clusters.csv
  10_resumen_auditoria.json
  10_informe_cierre_tecnico.md
  10_manifest_archivos.csv
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent
ENTRADAS = {
    "matriz": BASE / "salida_vectores_registros" / "05_vectores_registros.npy",
    "indice": BASE / "salida_vectores_registros" / "05_indice_registros.csv",
    "principal": BASE / "salida_seleccion_k" / "08_asignaciones_principales.csv",
    "conjunto": BASE / "salida_seleccion_k" / "08_asignaciones_conjunto_exploratorio.csv",
    "clusters_principales": BASE / "salida_seleccion_k" / "08_clusters_principales.csv",
    "clusters_conjunto": BASE / "salida_seleccion_k" / "08_clusters_conjunto_exploratorio.csv",
    "revision_humana": BASE / "salida_seleccion_k" / "08_revision_humana_clusters.csv",
    "coordenadas": BASE / "salida_visualizacion_pca" / "09_coordenadas_pca.csv",
    "diagnostico": BASE / "salida_visualizacion_pca" / "09_diagnostico_pca.csv",
    "resumen_pca": BASE / "salida_visualizacion_pca" / "09_resumen_visualizacion.json",
}
GRAFICOS = [
    "09_pca_academia_k5.png",
    "09_pca_mercado_k3.png",
    "09_pca_conjunto_k4_exploratorio.png",
    "09_pca_conjunto_por_origen.png",
]
SALIDA = BASE / "salida_auditoria_act3"
N = {"academia": 46, "mercado": 228, "conjunto": 274}
K = {"academia": 5, "mercado": 3, "conjunto": 4}


def sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with ruta.open("rb") as fh:
        for bloque in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(bloque)
    return h.hexdigest()


def csv_entrada(ruta: Path) -> pd.DataFrame:
    return pd.read_csv(ruta, sep=";", encoding="utf-8-sig", dtype=str,
                       keep_default_na=False)


def entero(df: pd.DataFrame, nombre: str) -> pd.Series:
    if nombre not in df:
        raise ValueError(f"Falta la columna obligatoria {nombre}")
    return pd.to_numeric(df[nombre], errors="raise").astype(int)


def emitir_csv(df: pd.DataFrame, ruta: Path) -> None:
    df.to_csv(ruta, sep=";", index=False, encoding="utf-8-sig",
              quoting=csv.QUOTE_MINIMAL)


def auditoria() -> None:
    faltan = [str(r) for r in ENTRADAS.values() if not r.is_file()]
    if faltan:
        raise FileNotFoundError("Faltan archivos de pasos anteriores:\n  " + "\n  ".join(faltan))

    x = np.load(ENTRADAS["matriz"], allow_pickle=False)
    indice = csv_entrada(ENTRADAS["indice"])
    principal = csv_entrada(ENTRADAS["principal"])
    conjunto = csv_entrada(ENTRADAS["conjunto"])
    clusters_p = csv_entrada(ENTRADAS["clusters_principales"])
    clusters_c = csv_entrada(ENTRADAS["clusters_conjunto"])
    revision = csv_entrada(ENTRADAS["revision_humana"])
    xy = csv_entrada(ENTRADAS["coordenadas"])
    diag = csv_entrada(ENTRADAS["diagnostico"])
    resumen_pca = json.loads(ENTRADAS["resumen_pca"].read_text(encoding="utf-8-sig"))

    controles: list[dict] = []
    def verificar(nombre: str, valido: bool, detalle: str, severidad: str = "ERROR") -> None:
        controles.append({"control": nombre,
                          "resultado": "OK" if valido else severidad,
                          "detalle": detalle})

    verificar("matriz_forma", x.ndim == 2 and x.shape == (274, 384), f"shape={x.shape}")
    verificar("matriz_valores_finitos", bool(np.isfinite(x).all()), "Sin NaN ni infinito")
    if x.ndim == 2 and x.shape[0] > 0:
        norma = np.linalg.norm(x, axis=1)
        verificar("matriz_normalizacion_l2", bool(np.allclose(norma, 1, atol=2e-4)),
                  f"norma minima={norma.min():.7f}; maxima={norma.max():.7f}")
    for col in ("fila_vector_0_based", "id_registro", "origen"):
        verificar(f"indice_columna_{col}", col in indice.columns, f"Columna {col}")
    if not {"fila_vector_0_based", "id_registro", "origen"}.issubset(indice.columns):
        raise ValueError("No se puede continuar: indice 05 sin columnas obligatorias")
    indice["fila_vector_0_based"] = entero(indice, "fila_vector_0_based")
    indice = indice.sort_values("fila_vector_0_based").reset_index(drop=True)
    verificar("indice_orden", indice["fila_vector_0_based"].tolist() == list(range(274)),
              "Se esperan filas 0..273 exactamente una vez")
    verificar("indice_ids_unicos", bool(indice["id_registro"].is_unique),
              "Cada registro debe tener ID unico")
    verificar("indice_poblacion", indice["origen"].value_counts().to_dict() ==
              {"academia": 46, "mercado": 228}, f"origen={indice['origen'].value_counts().to_dict()}")

    def validar_asignaciones(df: pd.DataFrame, grupos: tuple[str, ...], nombre: str) -> pd.DataFrame:
        obligatorias = {"fila_vector_0_based", "id_registro", "origen", "grupo", "cluster", "k"}
        if not obligatorias.issubset(df.columns):
            raise ValueError(f"{nombre}: faltan columnas {obligatorias-set(df.columns)}")
        for c in ("fila_vector_0_based", "cluster", "k"):
            df[c] = entero(df, c)
        verificar(f"{nombre}_filas", len(df) == 274, f"filas={len(df)}")
        verificar(f"{nombre}_id_filas", df["fila_vector_0_based"].is_unique and
                  set(df["fila_vector_0_based"]) == set(range(274)), "Indices completos y unicos")
        df = df.sort_values("fila_vector_0_based").reset_index(drop=True)
        verificar(f"{nombre}_alineacion", len(df) == len(indice) and
                  df["id_registro"].tolist() == indice["id_registro"].tolist() and
                  df["origen"].tolist() == indice["origen"].tolist(),
                  "Identidad y origen fila a fila contra indice 05")
        verificar(f"{nombre}_grupos", set(df["grupo"]) == set(grupos),
                  f"grupos={sorted(set(df['grupo']))}")
        for g in grupos:
            sel = df[df["grupo"] == g]
            verificar(f"{nombre}_{g}_conteo", len(sel) == N[g], f"n={len(sel)}; esperado={N[g]}")
            verificar(f"{nombre}_{g}_k_clusters", bool((sel["k"] == K[g]).all()) and
                      set(sel["cluster"]) == set(range(K[g])),
                      f"K={K[g]}, clusters esperados={list(range(K[g]))}")
            if g != "conjunto":
                verificar(f"{nombre}_{g}_origen", bool((sel["origen"] == g).all()),
                          "Sin mezcla de origen")
        return df

    principal = validar_asignaciones(principal, ("academia", "mercado"), "principal")
    conjunto = validar_asignaciones(conjunto, ("conjunto",), "conjunto")

    def validar_catalogo(df: pd.DataFrame, a: pd.DataFrame, grupos: tuple[str, ...], nombre: str):
        for c in ("k", "cluster", "n_registros"):
            df[c] = entero(df, c)
        esperado = {(g, k) for g in grupos for k in range(K[g])}
        actual = {(r.grupo, int(r.cluster)) for r in df.itertuples(index=False)}
        verificar(f"{nombre}_clusters", len(df) == len(esperado) and actual == esperado,
                  f"clusters documentados={len(df)}")
        for r in df.itertuples(index=False):
            n_real = int(((a["grupo"] == r.grupo) & (a["cluster"] == r.cluster)).sum())
            verificar(f"{nombre}_{r.grupo}_C{r.cluster}_tamano", n_real == int(r.n_registros),
                      f"documentado={r.n_registros}; asignaciones={n_real}")
    validar_catalogo(clusters_p, principal, ("academia", "mercado"), "clusters_principales")
    validar_catalogo(clusters_c, conjunto, ("conjunto",), "clusters_conjunto")

    req_xy = {"grupo_proyeccion", "fila_vector_0_based", "id_registro", "origen",
              "pca_1", "pca_2", "cluster", "k"}
    if not req_xy.issubset(xy.columns):
        raise ValueError(f"Coordenadas 09: faltan columnas {req_xy-set(xy.columns)}")
    for c in ("fila_vector_0_based", "cluster", "k"):
        xy[c] = entero(xy, c)
    verificar("coordenadas_total", len(xy) == 548, f"filas={len(xy)}; esperadas=274+274=548")
    verificar("coordenadas_finitas", bool(pd.to_numeric(xy["pca_1"], errors="coerce").notna().all() and
              pd.to_numeric(xy["pca_2"], errors="coerce").notna().all()), "PCA1 y PCA2 son numeros")
    verificar("coordenadas_grupos", set(xy["grupo_proyeccion"]) == set(N),
              f"grupos={sorted(set(xy['grupo_proyeccion']))}")
    for g in ("academia", "mercado", "conjunto"):
        proy = xy[xy["grupo_proyeccion"] == g].copy()
        a = conjunto if g == "conjunto" else principal[principal["grupo"] == g]
        verificar(f"coordenadas_{g}_n", len(proy) == N[g],
                  f"n={len(proy)}; esperado={N[g]}")
        verificar(f"coordenadas_{g}_ids_unicos", proy["fila_vector_0_based"].is_unique,
                  "Cada vector aparece una vez en su PCA")
        left = proy.set_index("fila_vector_0_based")
        right = a.set_index("fila_vector_0_based")
        same = set(left.index) == set(right.index)
        if same:
            left = left.sort_index(); right = right.sort_index()
            same = (left["id_registro"].tolist() == right["id_registro"].tolist() and
                    left["origen"].tolist() == right["origen"].tolist() and
                    left["cluster"].tolist() == right["cluster"].tolist() and
                    left["k"].tolist() == right["k"].tolist())
        verificar(f"coordenadas_{g}_alineacion_clusters", same,
                  "IDs, origen, K y cluster coinciden con paso 08")

    esperado_diag = set(N)
    verificar("diagnostico_pca_grupos", set(diag["grupo"]) == esperado_diag and
              len(diag) == 3, "Un diagnostico por poblacion")
    for r in diag.itertuples(index=False):
        try:
            suma = float(r.pca_varianza_1) + float(r.pca_varianza_2)
            acumulada = float(r.pca_varianza_acumulada)
            valido = (0 < acumulada <= 1 and abs(suma - acumulada) < 1e-5 and
                      int(r.n) == N[r.grupo] and int(r.k) == K[r.grupo])
        except (ValueError, KeyError, TypeError):
            valido = False
        verificar(f"pca_{r.grupo}_varianza", valido,
                  f"varianza_2D={r.pca_varianza_acumulada}; n={r.n}; K={r.k}")

    for name in GRAFICOS:
        ruta = BASE / "salida_visualizacion_pca" / name
        verificar("grafico_" + name, ruta.is_file() and ruta.stat().st_size > 1000 if ruta.exists() else False,
                  f"Existe y tiene contenido: {name}")

    hashes_previos = resumen_pca.get("entradas_sha256", {})
    for nombre_archivo, codigo in [
        ("05_vectores_registros.npy", "matriz"),
        ("05_indice_registros.csv", "indice"),
        ("08_asignaciones_principales.csv", "principal"),
        ("08_asignaciones_conjunto_exploratorio.csv", "conjunto"),
        ("08_clusters_principales.csv", "clusters_principales"),
        ("08_clusters_conjunto_exploratorio.csv", "clusters_conjunto"),
    ]:
        huella = hashes_previos.get(nombre_archivo)
        verificar("sha256_" + nombre_archivo,
                  bool(huella) and sha256(ENTRADAS[codigo]) == huella,
                  "Coincide con SHA-256 registrado en paso 09")

    for col in ("grupo", "k", "cluster", "decision_humana"):
        if col not in revision:
            raise ValueError(f"La plantilla 08 no contiene {col}")
    revision["k"] = entero(revision, "k")
    revision["cluster"] = entero(revision, "cluster")
    claves = set(zip(revision["grupo"], revision["k"], revision["cluster"]))
    esperadas = {(g, K[g], i) for g in ("academia", "mercado") for i in range(K[g])}
    verificar("revision_plantilla_ocho_clusters", len(revision) == 8 and claves == esperadas,
              f"filas={len(revision)}; fichas necesarias=8")
    decisiones = revision["decision_humana"].str.strip().str.upper()
    revision["estado_auditoria"] = np.where(decisiones.isin(["", "PENDIENTE"]),
                                            "PENDIENTE_REVISION", "DECISION_REGISTRADA_REVISAR_EVIDENCIA")
    n_pendientes = int((revision["estado_auditoria"] == "PENDIENTE_REVISION").sum())
    verificar("revision_humana_completada", n_pendientes == 0,
              f"fichas pendientes={n_pendientes}; la validacion semantica no se infiere", "PENDIENTE")

    SALIDA.mkdir(exist_ok=True, parents=True)
    emitir_csv(pd.DataFrame(controles), SALIDA / "10_control_integridad.csv")
    emitir_csv(revision, SALIDA / "10_pendientes_revision_clusters.csv")
    archivos = []
    for nombre, ruta in ENTRADAS.items():
        archivos.append({"clave": nombre, "archivo": str(ruta.relative_to(BASE)),
                         "tamano_bytes": ruta.stat().st_size, "sha256": sha256(ruta)})
    for nombre in GRAFICOS:
        ruta = BASE / "salida_visualizacion_pca" / nombre
        if ruta.is_file():
            archivos.append({"clave": "grafico", "archivo": str(ruta.relative_to(BASE)),
                             "tamano_bytes": ruta.stat().st_size, "sha256": sha256(ruta)})
    emitir_csv(pd.DataFrame(archivos), SALIDA / "10_manifest_archivos.csv")

    errores = [c for c in controles if c["resultado"] == "ERROR"]
    pendientes = [c for c in controles if c["resultado"] == "PENDIENTE"]
    estado = "ERROR_TECNICO" if errores else ("TECNICAMENTE_CONSISTENTE_CON_REVISION_PENDIENTE"
                                           if pendientes else "TECNICAMENTE_CONSISTENTE")
    resumen = {
        "paso": 10, "estado": estado, "controles": len(controles),
        "errores": len(errores), "pendientes": len(pendientes),
        "registros": {"academia": 46, "mercado": 228, "total": 274},
        "representacion": "vectores semanticos 384D normalizados; media ESCO sin pesos",
        "configuraciones": {"academia": 5, "mercado": 3, "conjunto_exploratorio": 4},
        "filas_proyecciones": 548,
        "pca_varianza_2d": {r.grupo: float(r.pca_varianza_acumulada) for r in diag.itertuples(index=False)},
        "fichas_revision_clusters_pendientes": n_pendientes,
        "ofertas_sin_esco_no_incluidas": 14,
        "limites": [
            "No se reviso manualmente la correspondencia entre texto original y ESCO.",
            "La pertenencia a clusters no equivale a pertinencia ni cobertura curricular.",
            "La proyeccion PCA no conserva todas las distancias de 384 dimensiones.",
            "Las 14 ofertas sin competencias ESCO no tienen vector en esta muestra.",
            "Las poblaciones academia y mercado fueron agrupadas por separado; los IDs no se comparan.",
            "Las etiquetas de clusters siguen siendo provisionales.",
        ],
    }
    (SALIDA / "10_resumen_auditoria.json").write_text(
        json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")

    informe = f"""# Obj2 / Act. 3 — Paso 10: auditoría técnica del pipeline

**Estado:** {estado}.

## Alcance comprobado
- Matriz de **274 × 384** (46 carreras, 228 ofertas), vectores normalizados.
- Agrupamiento académico **K=5** y laboral **K=3**, provisionales.
- Agrupamiento combinado **K=4**, exclusivamente exploratorio.
- Archivo PCA con **548 filas**: 274 principales y 274 combinadas; no son 548 casos únicos.
- Integridad referencial entre IDs, índices de vector, clusters y puntos de PCA.
- Verificación de huellas SHA-256 registradas en el paso 09.

## Resultados
- Controles ejecutados: **{len(controles)}**.
- Errores técnicos: **{len(errores)}**.
- Controles pendientes: **{len(pendientes)}**.
- Fichas de revisión humana sin decisión: **{n_pendientes}/8**.
- Proporción de varianza representada en PCA 2D: academia **{float(diag.loc[diag['grupo']=='academia','pca_varianza_acumulada'].iloc[0]):.1%}**, mercado **{float(diag.loc[diag['grupo']=='mercado','pca_varianza_acumulada'].iloc[0]):.1%}**, conjunto **{float(diag.loc[diag['grupo']=='conjunto','pca_varianza_acumulada'].iloc[0]):.1%}**.

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
"""
    (SALIDA / "10_informe_cierre_tecnico.md").write_text(informe, encoding="utf-8")

    print("\nPASO 10 - AUDITORIA OBJ2 / ACT. 3")
    print(f"  Controles ejecutados: {len(controles)}")
    print(f"  Errores tecnicos: {len(errores)}")
    print(f"  Controles pendientes: {len(pendientes)}")
    print(f"  Fichas de revision humana pendientes: {n_pendientes}/8")
    print(f"  Estado: {estado}")
    print(f"  Salida: {SALIDA}")
    print("  No se ha calculado cobertura ni validado semanticamente ESCO.")
    if errores:
        print("\nERRORES DETECTADOS:")
        for e in errores:
            print(" -", e["control"], ":", e["detalle"])
        raise RuntimeError("La auditoria detecto inconsistencias; revisa 10_control_integridad.csv")


if __name__ == "__main__":
    try:
        auditoria()
    except Exception as exc:
        print("\nERROR EN PASO 10:", exc)
        print("Comprueba que ejecutaste los pasos 05, 08 y 09, y que este .py esta en Obj2/Act. 3/")
        sys.exit(1)
