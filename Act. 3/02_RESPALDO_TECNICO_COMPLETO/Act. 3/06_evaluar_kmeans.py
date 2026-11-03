#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Obj2 / Act. 3 / Paso 6: evaluación exploratoria del número de clusters K.

En Visual Studio Code:
  - Guardar este archivo en DESARROLLO/Obj2/Act. 3/
  - Verificar que exista salida_vectores_registros/ (paso 5).
  - Abrir este .py y pulsar ▶ «Ejecutar archivo Python».

Evalúa por separado academia, mercado y conjunto. No selecciona K final,
no valida semánticamente los mapeos ESCO y NO estima cobertura curricular.

Método: K-Means euclidiano sobre vectores L2; métricas de silueta coseno,
silueta euclidiana, Davies-Bouldin, Calinski-Harabasz, inercia y estabilidad
entre semillas (Adjusted Rand Index, ARI). Reporta tamaños de clusters.
"""
from __future__ import annotations

import csv
import hashlib
import itertools
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

# =========== CONFIGURACIÓN ===========
ACT3 = Path(__file__).resolve().parent
ENTRADA = ACT3 / "salida_vectores_registros"
SALIDA = ACT3 / "salida_evaluacion_kmeans"
MATRIZ = ENTRADA / "05_vectores_registros.npy"
INDICE = ENTRADA / "05_indice_registros.csv"
RESUMEN_05 = ENTRADA / "05_resumen_agregacion.json"

SEMILLAS = (42, 123, 2026)
INICIALIZACIONES = 20
MAX_ITERACIONES = 400
# Rango acotado por tamaño muestral; no es una selección final de K.
RANGOS_K = {
    "academia": range(2, 9),   # 46 perfiles
    "mercado": range(2, 11),   # 228 ofertas
    "conjunto": range(2, 11),  # 274 registros (desbalanceado)
}


def importar_sklearn():
    try:
        from sklearn.cluster import KMeans
        from sklearn.metrics import (
            adjusted_rand_score, calinski_harabasz_score,
            davies_bouldin_score, silhouette_score,
        )
        return KMeans, adjusted_rand_score, calinski_harabasz_score, davies_bouldin_score, silhouette_score
    except ImportError:
        print("\nFalta scikit-learn. Intentaré instalarlo en el intérprete de Python de VS Code...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "scikit-learn"])
        from sklearn.cluster import KMeans
        from sklearn.metrics import (
            adjusted_rand_score, calinski_harabasz_score,
            davies_bouldin_score, silhouette_score,
        )
        return KMeans, adjusted_rand_score, calinski_harabasz_score, davies_bouldin_score, silhouette_score


def huella_sha256(ruta: Path) -> str:
    digest = hashlib.sha256()
    with ruta.open("rb") as archivo:
        for bloque in iter(lambda: archivo.read(1024 * 1024), b""):
            digest.update(bloque)
    return digest.hexdigest()


def leer_csv(ruta: Path) -> list[dict[str, str]]:
    with ruta.open("r", encoding="utf-8-sig", newline="") as archivo:
        lector = csv.DictReader(archivo, delimiter=";")
        requeridas = {"fila_vector_0_based", "origen", "fila_csv", "id_registro", "n_competencias_esco"}
        if lector.fieldnames is None or not requeridas.issubset(lector.fieldnames):
            raise ValueError(f"El índice {ruta.name} no tiene todas las columnas requeridas. Se espera separador ';'.")
        filas = list(lector)
        if any(None in fila or any(v is None for v in fila.values()) for fila in filas):
            raise ValueError(f"El índice {ruta.name} tiene una estructura CSV irregular.")
    return filas


def validar_entradas():
    for ruta in (MATRIZ, INDICE, RESUMEN_05):
        if not ruta.is_file():
            raise FileNotFoundError(f"No encuentro {ruta}. Ejecuta primero el script 05 en VS Code.")
    resumen = json.loads(RESUMEN_05.read_text(encoding="utf-8-sig"))
    huellas_esperadas = resumen.get("salidas_sha256", {})
    for archivo, nombre in ((MATRIZ, "05_vectores_registros.npy"), (INDICE, "05_indice_registros.csv")):
        esperado = huellas_esperadas.get(nombre)
        obtenido = huella_sha256(archivo)
        if not esperado or esperado != obtenido:
            raise ValueError(f"No coincide SHA-256 de {nombre}. Comprueba que matriz, índice y resumen sean de la misma ejecución 05.")
    x = np.load(MATRIZ, allow_pickle=False)
    filas = leer_csv(INDICE)
    if x.ndim != 2 or x.dtype != np.float32 or x.shape[0] != len(filas):
        raise ValueError("Matriz e índice desalineados o formato incorrecto: se espera matriz float32 de 2 dimensiones.")
    if not np.isfinite(x).all():
        raise ValueError("La matriz contiene valores NaN o infinitos.")
    if not np.allclose(np.linalg.norm(x, axis=1), 1, atol=2e-5):
        raise ValueError("Los vectores no tienen normalización L2 aproximadamente igual a 1.")
    if x.shape[1] != 384:
        raise ValueError(f"Se esperaban 384 dimensiones del modelo, se encontraron {x.shape[1]}.")
    ids = set()
    for i, fila in enumerate(filas):
        if int(fila["fila_vector_0_based"]) != i:
            raise ValueError(f"Desalineación: índice de vector en fila {i}.")
        if fila["origen"] not in ("academia", "mercado"):
            raise ValueError(f"Origen no reconocido en fila {i}: {fila['origen']}")
        clave = (fila["origen"], fila["fila_csv"], fila["id_registro"])
        if clave in ids:
            raise ValueError(f"Registro duplicado: {clave}")
        ids.add(clave)
        if int(fila["n_competencias_esco"]) < 1:
            raise ValueError(f"Registro sin competencias, fila {i}")
    conteos = Counter(fila["origen"] for fila in filas)
    esperados = resumen.get("conteos", {})
    if (len(filas) != esperados.get("registros_total")
        or conteos["academia"] != esperados.get("academia")
        or conteos["mercado"] != esperados.get("mercado")):
        raise ValueError("Los registros no coinciden con los conteos del resumen 05.")
    return x, filas, resumen, conteos


def escribir_csv(ruta: Path, filas: list[dict], campos: list[str]):
    with ruta.open("w", encoding="utf-8-sig", newline="") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=campos, delimiter=";", extrasaction="ignore")
        escritor.writeheader()
        escritor.writerows(filas)


def redondear(valor: float, n: int = 6):
    return round(float(valor), n)


def guardar_graficos(metricas: list[dict]) -> str:
    """Los gráficos son opcionales: las salidas CSV/JSON se producen incluso sin matplotlib."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return "Sin gráficos PNG: matplotlib no está instalado (los CSV están completos)."

    etiquetas = {"academia": "Academia (n=46)", "mercado": "Mercado (n=228)", "conjunto": "Combinados (n=274)"}
    for metrica, nombre, ylabel in [
        ("silueta_coseno", "06_silueta_coseno_por_k.png", "Silueta (distancia coseno)"),
        ("estabilidad_ari_media", "06_estabilidad_ari_por_k.png", "ARI medio entre semillas"),
        ("inercia_por_registro", "06_inercia_por_k.png", "Inercia euclidiana / n"),
    ]:
        fig, ax = plt.subplots(figsize=(8, 5))
        for grupo in ("academia", "mercado", "conjunto"):
            registros = [f for f in metricas if f["grupo"] == grupo and f["estado"] == "OK"]
            ax.plot([f["k"] for f in registros], [f[metrica] for f in registros], marker="o", label=etiquetas[grupo])
        ax.set_xlabel("Cantidad de grupos K")
        ax.set_ylabel(ylabel)
        ax.set_title(f"Evaluación exploratoria de K-Means: {ylabel}")
        ax.grid(alpha=0.25)
        ax.legend()
        ax.set_xticks(range(2, 11))
        fig.tight_layout()
        fig.savefig(SALIDA / nombre, dpi=160)
        plt.close(fig)
    return "Generados: 06_silueta_coseno_por_k.png, 06_estabilidad_ari_por_k.png, 06_inercia_por_k.png"


def ejecutar():
    KMeans, adjusted_rand_score, calinski_harabasz_score, davies_bouldin_score, silhouette_score = importar_sklearn()
    x, indice, resumen_05, conteos = validar_entradas()
    SALIDA.mkdir(parents=True, exist_ok=True)

    metricas: list[dict] = []
    asignaciones: list[dict] = []
    distribucion: list[dict] = []
    recomendaciones: list[dict] = []

    print("PASO 6 - ENTRADAS VERIFICADAS")
    print(f"  Matriz: {x.shape[0]} registros x {x.shape[1]} dimensiones")
    print(f"  Academia: {conteos['academia']} | Mercado: {conteos['mercado']}")
    print(f"  Semillas: {SEMILLAS} | n_init={INICIALIZACIONES}")
    print("  Se evalúa K por separado y en conjunto; NO se selecciona K definitivo.\n")

    for grupo in ("academia", "mercado", "conjunto"):
        posiciones = [i for i, fila in enumerate(indice) if grupo == "conjunto" or fila["origen"] == grupo]
        datos = x[posiciones]
        distintos = np.unique(datos, axis=0).shape[0]
        print(f"Analizando: {grupo} (n={len(datos)}, vectores distintos={distintos})")
        for k in RANGOS_K[grupo]:
            if k >= len(datos) or k > distintos:
                print(f"  K={k} omitido: pocos registros/vectores distintos")
                metricas.append({"grupo": grupo, "n_registros": len(datos), "k": k, "estado": "OMITIDO_DATOS_INSUFICIENTES"})
                continue
            etiquetas_por_semilla = []
            modelos = []
            for semilla in SEMILLAS:
                modelo = KMeans(n_clusters=k, init="k-means++", n_init=INICIALIZACIONES,
                                max_iter=MAX_ITERACIONES, algorithm="lloyd", random_state=semilla)
                etiquetas = modelo.fit_predict(datos)
                etiquetas_por_semilla.append(etiquetas)
                modelos.append(modelo)
            etiquetas_base = etiquetas_por_semilla[0]
            tamanos = np.bincount(etiquetas_base, minlength=k)
            if np.count_nonzero(tamanos) != k:
                print(f"  K={k} omitido: produjo menos de {k} clusters no vacíos")
                metricas.append({"grupo": grupo, "n_registros": len(datos), "k": k, "estado": "OMITIDO_CLUSTERS_VACIOS"})
                continue
            sil_cos = silhouette_score(datos, etiquetas_base, metric="cosine")
            sil_euc = silhouette_score(datos, etiquetas_base, metric="euclidean")
            ari = [adjusted_rand_score(a, b) for a, b in itertools.combinations(etiquetas_por_semilla, 2)]
            met = {
                "grupo": grupo, "n_registros": len(datos), "k": k, "estado": "OK",
                "silueta_coseno": redondear(sil_cos),
                "silueta_euclidiana": redondear(sil_euc),
                "estabilidad_ari_media": redondear(np.mean(ari)),
                "estabilidad_ari_min": redondear(np.min(ari)),
                "davies_bouldin": redondear(davies_bouldin_score(datos, etiquetas_base)),
                "calinski_harabasz": redondear(calinski_harabasz_score(datos, etiquetas_base)),
                "inercia": redondear(modelos[0].inertia_),
                "inercia_por_registro": redondear(modelos[0].inertia_ / len(datos)),
                "cluster_mas_pequeno": int(tamanos.min()),
                "cluster_mas_grande": int(tamanos.max()),
                "clusters_unitarios": int(np.sum(tamanos == 1)),
                "iteraciones_kmeans": int(modelos[0].n_iter_),
            }
            metricas.append(met)
            for etiqueta in range(k):
                indices_c = [p for p, etiqueta_predicha in zip(posiciones, etiquetas_base) if etiqueta_predicha == etiqueta]
                cuenta = Counter(indice[i]["origen"] for i in indices_c)
                distribucion.append({
                    "grupo": grupo, "k": k, "cluster_provisional": int(etiqueta),
                    "total": len(indices_c), "academia": cuenta["academia"], "mercado": cuenta["mercado"],
                })
            for pos, predicha in zip(posiciones, etiquetas_base):
                registro = indice[pos]
                asignaciones.append({
                    "grupo": grupo, "k": k, "fila_vector_0_based": pos,
                    "origen": registro["origen"], "fila_csv": registro["fila_csv"],
                    "id_registro": registro["id_registro"],
                    "universidad": registro.get("universidad", ""),
                    "carrera": registro.get("carrera", ""),
                    "job_id": registro.get("job_id", ""),
                    "titulo_oferta": registro.get("titulo_oferta", ""),
                    "cluster_provisional": int(predicha),
                })
            print(f"  K={k:2d} | sil.cos={met['silueta_coseno']:.4f} | ARI={met['estabilidad_ari_media']:.3f} | "
                  f"tamaños min/max={met['cluster_mas_pequeno']}/{met['cluster_mas_grande']}")

        por_grupo = [f for f in metricas if f["grupo"] == grupo and f["estado"] == "OK"]
        # Los mayores valores de silueta son solo candidatos a examinar, NO la solución elegida.
        for posicion, met in enumerate(sorted(por_grupo, key=lambda f: (-f["silueta_coseno"], -f["estabilidad_ari_media"]))[:3], 1):
            recomendaciones.append({
                "grupo": grupo, "puesto_exploratorio": posicion, "k": met["k"],
                "silueta_coseno": met["silueta_coseno"],
                "estabilidad_ari_media": met["estabilidad_ari_media"],
                "cluster_mas_pequeno": met["cluster_mas_pequeno"],
                "clusters_unitarios": met["clusters_unitarios"],
                "interpretacion": "CANDIDATO_POR_SILUETA_NO_ES_K_DEFINITIVO",
            })
        print()

    campos_metricas = [
        "grupo", "n_registros", "k", "estado", "silueta_coseno", "silueta_euclidiana",
        "estabilidad_ari_media", "estabilidad_ari_min", "davies_bouldin", "calinski_harabasz",
        "inercia", "inercia_por_registro", "cluster_mas_pequeno", "cluster_mas_grande",
        "clusters_unitarios", "iteraciones_kmeans",
    ]
    escribir_csv(SALIDA / "06_metricas_por_k.csv", metricas, campos_metricas)
    escribir_csv(SALIDA / "06_asignaciones_exploratorias.csv", asignaciones,
                ["grupo", "k", "fila_vector_0_based", "origen", "fila_csv", "id_registro",
                 "universidad", "carrera", "job_id", "titulo_oferta", "cluster_provisional"])
    escribir_csv(SALIDA / "06_distribucion_clusters.csv", distribucion,
                ["grupo", "k", "cluster_provisional", "total", "academia", "mercado"])
    escribir_csv(SALIDA / "06_candidatos_por_silueta.csv", recomendaciones,
                ["grupo", "puesto_exploratorio", "k", "silueta_coseno", "estabilidad_ari_media",
                 "cluster_mas_pequeno", "clusters_unitarios", "interpretacion"])
    resultado_graficos = guardar_graficos(metricas)
    resumen = {
        "etapa": "Obj2 / Actividad 3 / Paso 6",
        "estado": "EVALUACION_EXPLORATORIA_K_SIN_K_FINAL",
        "metodo": {
            "algoritmo": "KMeans euclidiano sobre vectores L2",
            "silueta_principal": "distancia coseno",
            "semillas": list(SEMILLAS), "n_init": INICIALIZACIONES,
            "max_iter": MAX_ITERACIONES,
            "rangos_k": {g: list(v) for g, v in RANGOS_K.items()},
            "estabilidad": "ARI medio y mínimo entre todas las parejas de semillas",
            "nota": "Se evalúa cada grupo separadamente; la combinación academia-mercado está desbalanceada.",
        },
        "conteos": {"total": len(indice), "academia": conteos["academia"], "mercado": conteos["mercado"],
                    "vectores_distintos": int(np.unique(x, axis=0).shape[0])},
        "entradas_sha256": {"05_vectores_registros.npy": huella_sha256(MATRIZ),
                             "05_indice_registros.csv": huella_sha256(INDICE),
                             "05_resumen_agregacion.json": huella_sha256(RESUMEN_05)},
        "archivos": ["06_metricas_por_k.csv", "06_asignaciones_exploratorias.csv",
                     "06_distribucion_clusters.csv", "06_candidatos_por_silueta.csv"],
        "graficos": resultado_graficos,
        "alertas": [
            "La métrica de silueta no valida la interpretación semántica de los clusters.",
            "Los identificadores numéricos de cluster son arbitrarios y no se comparan entre valores de K.",
            "El resultado conjunto tiene más ofertas que carreras y puede reflejar ese desbalance.",
            "Los mapeos originales a ESCO siguen pendientes de revisión humana.",
            "No se ha seleccionado K definitivo ni calculado porcentaje de cobertura curricular.",
        ],
    }
    (SALIDA / "06_resumen_evaluacion.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("PASO 6 FINALIZADO CORRECTAMENTE")
    print(f"  Valores de K evaluados: {sum(f['estado']=='OK' for f in metricas)}")
    print(f"  Carpeta: {SALIDA}")
    print("  Archivo para revisar conmigo: 06_metricas_por_k.csv")
    print("  Archivo complementario: 06_candidatos_por_silueta.csv")
    print(f"  Gráficos: {resultado_graficos}")
    print("  IMPORTANTE: esto NO determina todavía el mejor K ni la cobertura curricular.")


if __name__ == "__main__":
    try:
        ejecutar()
    except Exception as exc:
        print(f"\nERROR PASO 6: {type(exc).__name__}: {exc}", file=sys.stderr)
        print("Verifica que 06_evaluar_kmeans.py esté en Obj2/Act. 3/ y exista salida_vectores_registros/ del paso 5.", file=sys.stderr)
        sys.exit(1)
