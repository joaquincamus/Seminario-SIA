#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Obj2 / Act. 3 / Paso 5: un embedding por perfil académico/oferta laboral.

Uso en Visual Studio Code (Windows):
  1. Copia este archivo en DESARROLLO/Obj2/Act. 3/
  2. Comprueba que existen salida_textos/ (paso 3) y salida_embeddings/ (paso 4)
  3. Ábrelo en VS Code y pulsa ▶ «Ejecutar archivo Python».

No depende de la carpeta de trabajo de VS Code: usa la ruta de este .py.
Requiere sólo NumPy (ya instalado para el paso 4).

Representación: media aritmética, con igual peso, de los embeddings L2
normalizados de las URI ESCO asignadas al registro, seguida de
normalización L2. NO calcula cobertura, similitud entre sectores, clusters
ni valida la pertinencia de las asignaciones ESCO.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

# ======= CONFIGURACIÓN: no necesitas cambiar estas rutas =======
ACT3 = Path(__file__).resolve().parent
ENTRADAS_TEXTO = ACT3 / "salida_textos"
ENTRADAS_EMBEDDINGS = ACT3 / "salida_embeddings"
SALIDA = ACT3 / "salida_vectores_registros"

ARCHIVO_REGISTROS = "03_registros_preparados.csv"
ARCHIVO_RELACIONES = "03_relaciones_trazables.csv"
ARCHIVO_CATALOGO = "03_catalogo_competencias_esco.csv"
ARCHIVO_RESUMEN_03 = "03_resumen_corpus.json"
ARCHIVO_EMBEDDINGS = "04_embeddings_competencias_esco.npy"
ARCHIVO_INDICE_04 = "04_indice_embeddings_esco.csv"
ARCHIVO_RESUMEN_04 = "04_resumen_embeddings.json"

ARCHIVO_MATRIZ_05 = "05_vectores_registros.npy"
ARCHIVO_INDICE_05 = "05_indice_registros.csv"
ARCHIVO_RESUMEN_05 = "05_resumen_agregacion.json"

COLUMNAS_INDICE_05 = [
    "fila_vector_0_based", "origen", "fila_csv", "id_registro",
    "universidad", "carrera", "job_id", "titulo_oferta",
    "n_competencias_esco", "uris_esco_json", "filas_esco_0_based_json",
    "norma_media_antes_normalizar", "estado_revision", "elegibilidad",
]


def sha256(ruta: Path) -> str:
    digest = hashlib.sha256()
    with ruta.open("rb") as archivo:
        for bloque in iter(lambda: archivo.read(1024 * 1024), b""):
            digest.update(bloque)
    return digest.hexdigest()


def leer_json(ruta: Path) -> dict:
    if not ruta.is_file():
        raise FileNotFoundError(f"Falta el archivo: {ruta}")
    resultado = json.loads(ruta.read_text(encoding="utf-8-sig"))
    if not isinstance(resultado, dict):
        raise ValueError(f"Se esperaba un objeto JSON en: {ruta.name}")
    return resultado


def leer_csv(ruta: Path, obligatorias: set[str]) -> list[dict[str, str]]:
    if not ruta.is_file():
        raise FileNotFoundError(f"Falta el archivo: {ruta}")
    csv.field_size_limit(20_000_000)
    with ruta.open("r", encoding="utf-8-sig", newline="") as archivo:
        lector = csv.DictReader(archivo, delimiter=";")
        cabeceras = lector.fieldnames or []
        if len(cabeceras) != len(set(cabeceras)) or not obligatorias.issubset(cabeceras):
            raise ValueError(f"Columnas faltantes o repetidas en {ruta.name}: {sorted(obligatorias - set(cabeceras))}")
        filas = list(lector)
        if any(None in fila or any(valor is None for valor in fila.values()) for fila in filas):
            raise ValueError(f"CSV irregular: {ruta.name}")
    if not filas:
        raise ValueError(f"No hay datos en {ruta.name}")
    return filas


def clave_registro(fila: dict) -> tuple[str, str, str]:
    return (fila["origen"], fila["fila_csv"], fila["id_registro"])


def validar_y_agregar() -> tuple[np.ndarray, list[dict], dict]:
    archivos_03 = {
        n: ENTRADAS_TEXTO / n for n in (
            ARCHIVO_CATALOGO, ARCHIVO_RELACIONES, ARCHIVO_REGISTROS, ARCHIVO_RESUMEN_03
        )
    }
    archivos_04 = {
        n: ENTRADAS_EMBEDDINGS / n for n in (
            ARCHIVO_EMBEDDINGS, ARCHIVO_INDICE_04, ARCHIVO_RESUMEN_04
        )
    }
    resumen_04 = leer_json(archivos_04[ARCHIVO_RESUMEN_04])
    resumen_03 = leer_json(archivos_03[ARCHIVO_RESUMEN_03])

    if resumen_04.get("estado") != "EMBEDDINGS_CALCULADOS_SIN_VALIDACION_SEMANTICA_ESPECIALIZADA":
        raise ValueError("El paso 4 no declara embeddings reales finalizados.")
    if resumen_04.get("modelado", {}).get("modelo") != "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2":
        raise ValueError("El modelo del paso 4 no coincide con el esperado.")
    if resumen_04.get("parametros", {}).get("normalizacion_l2") is not True:
        raise ValueError("Se esperaban embeddings ESCO normalizados L2 desde el paso 4.")

    # Comparar huellas de las entradas usadas realmente en el paso 4.
    # Si el resumen de paso 3 fue regenerado sin cambiar los CSV de datos,
    # verificamos su contenido/conteos, pero no bloqueamos por ese JSON.
    expected_03 = resumen_04.get("entradas_sha256", {})
    for nombre in (ARCHIVO_CATALOGO, ARCHIVO_RELACIONES, ARCHIVO_REGISTROS):
        actual = sha256(archivos_03[nombre])
        if actual != expected_03.get(nombre):
            raise ValueError(
                f"El archivo {nombre} cambió después de ejecutar el paso 4. "
                "Regenera el paso 4 antes de continuar."
            )
    expected_04 = resumen_04.get("salidas_sha256", {})
    for nombre in (ARCHIVO_EMBEDDINGS, ARCHIVO_INDICE_04):
        if sha256(archivos_04[nombre]) != expected_04.get(nombre):
            raise ValueError(f"La huella SHA256 de {nombre} no coincide con el resumen 04.")

    registros = leer_csv(archivos_03[ARCHIVO_REGISTROS], {
        "origen", "fila_csv", "id_registro", "n_competencias_esco", "uris_esco_json",
        "estado_revision", "elegibilidad"
    })
    relaciones = leer_csv(archivos_03[ARCHIVO_RELACIONES], {
        "origen", "fila_csv", "id_registro", "posicion", "uri_esco"
    })
    catalogo = leer_csv(archivos_03[ARCHIVO_CATALOGO], {
        "uri_esco", "texto_para_embedding"
    })
    indice_04 = leer_csv(archivos_04[ARCHIVO_INDICE_04], {
        "fila_vector_0_based", "uri_esco", "texto_para_embedding"
    })

    conteos_03 = resumen_03.get("conteos", {})
    conteos_04 = resumen_04.get("conteos", {})
    if (
        len(registros) != conteos_03.get("registros_totales_preparados")
        or len(relaciones) != conteos_03.get("asignaciones_registro_competencia")
        or len(catalogo) != conteos_03.get("competencias_uris_unicas")
        or len(registros) != conteos_04.get("registros_preparados_paso3")
        or len(relaciones) != conteos_04.get("relaciones_paso3")
        or len(catalogo) != conteos_04.get("competencias_uri")
    ):
        raise ValueError("Los conteos de los pasos 3 y 4 no coinciden con los CSV originales.")

    matriz_04 = np.load(archivos_04[ARCHIVO_EMBEDDINGS], allow_pickle=False)
    if (
        matriz_04.ndim != 2
        or matriz_04.shape != (len(indice_04), int(conteos_04.get("dimensiones_vector", -1)))
        or matriz_04.dtype != np.float32
        or not np.isfinite(matriz_04).all()
    ):
        raise ValueError(f"Matriz de competencias inválida: {matriz_04.shape}")
    normas_04 = np.linalg.norm(matriz_04, axis=1)
    if not np.allclose(normas_04, 1.0, atol=2e-3):
        raise ValueError("Los embeddings ESCO de entrada no están normalizados L2.")

    indice_por_uri = {}
    for i, (fila_indice, fila_catalogo) in enumerate(zip(indice_04, catalogo)):
        uri = fila_indice["uri_esco"]
        if (
            int(fila_indice["fila_vector_0_based"]) != i
            or fila_catalogo["uri_esco"] != uri
            or fila_catalogo["texto_para_embedding"] != fila_indice["texto_para_embedding"]
            or uri in indice_por_uri
        ):
            raise ValueError(f"Desalineación o URI repetida en índice ESCO: fila {i}")
        indice_por_uri[uri] = i
    if len(indice_04) != len(catalogo):
        raise ValueError("Número diferente de filas en índice ESCO y catálogo.")

    # Vincular cada relación a una clave original, preservando su posición.
    posiciones_por_registro = defaultdict(dict)
    for fila in relaciones:
        clave = clave_registro(fila)
        try:
            posicion = int(fila["posicion"])
        except ValueError as exc:
            raise ValueError(f"Posición inválida de competencia para {clave}") from exc
        if posicion < 1 or posicion in posiciones_por_registro[clave]:
            raise ValueError(f"Posición repetida o inválida: {clave} / {posicion}")
        if fila["uri_esco"] not in indice_por_uri:
            raise ValueError(f"URI sin vector en paso 4: {fila['uri_esco']}")
        posiciones_por_registro[clave][posicion] = fila["uri_esco"]

    vectores_05 = []
    indice_05 = []
    vistos = set()
    conteos_origen = Counter()
    normas_media = []
    for i, registro in enumerate(registros):
        clave = clave_registro(registro)
        if clave in vistos:
            raise ValueError(f"Registro repetido: {clave}")
        vistos.add(clave)
        if clave[0] not in ("academia", "mercado"):
            raise ValueError(f"Origen inesperado: {clave[0]}")
        conteos_origen[clave[0]] += 1
        try:
            uris = json.loads(registro["uris_esco_json"])
            cantidad = int(registro["n_competencias_esco"])
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            raise ValueError(f"URIs o cantidad no válidas para {clave}") from exc
        if (
            not isinstance(uris, list) or any(not isinstance(x, str) for x in uris)
            or len(uris) < 1 or len(uris) != cantidad or len(set(uris)) != len(uris)
        ):
            raise ValueError(f"URI vacía, duplicada o inconsistente en: {clave}")
        relaciones_en_orden = posiciones_por_registro.get(clave, {})
        if [relaciones_en_orden.get(p) for p in range(1, cantidad + 1)] != uris or len(relaciones_en_orden) != cantidad:
            raise ValueError(f"Las relaciones no coinciden con las URIs del registro: {clave}")
        filas_ESCO = [indice_por_uri[uri] for uri in uris]
        promedio = matriz_04[filas_ESCO].mean(axis=0, dtype=np.float64)
        norma = float(np.linalg.norm(promedio))
        if not np.isfinite(norma) or norma < 1e-10:
            raise ValueError(f"Vector medio indefinido (norma casi cero) para: {clave}")
        vector = (promedio / norma).astype(np.float32)
        if not np.isfinite(vector).all():
            raise ValueError(f"Vector no finito para: {clave}")
        vectores_05.append(vector)
        normas_media.append(norma)
        indice_05.append({
            "fila_vector_0_based": i,
            "origen": registro["origen"],
            "fila_csv": registro["fila_csv"],
            "id_registro": registro["id_registro"],
            "universidad": registro.get("universidad", ""),
            "carrera": registro.get("carrera", ""),
            "job_id": registro.get("job_id", ""),
            "titulo_oferta": registro.get("titulo_oferta", ""),
            "n_competencias_esco": cantidad,
            "uris_esco_json": json.dumps(uris, ensure_ascii=False),
            "filas_esco_0_based_json": json.dumps(filas_ESCO),
            "norma_media_antes_normalizar": f"{norma:.10f}",
            "estado_revision": registro["estado_revision"],
            "elegibilidad": registro["elegibilidad"],
        })

    if len(posiciones_por_registro) != len(vistos) or set(posiciones_por_registro) != vistos:
        raise ValueError("Existen relaciones huérfanas o registros sin relaciones.")
    if conteos_origen["academia"] != conteos_03.get("registros_academia") or conteos_origen["mercado"] != conteos_03.get("registros_mercado"):
        raise ValueError("Los conteos de academia/mercado difieren del resumen del paso 3.")
    matriz_05 = np.stack(vectores_05, axis=0)
    if matriz_05.shape != (len(registros), matriz_04.shape[1]):
        raise ValueError(f"Dimensión inesperada de la matriz resultante: {matriz_05.shape}")
    if not np.allclose(np.linalg.norm(matriz_05, axis=1), 1.0, atol=2e-6):
        raise ValueError("Los vectores resultantes no están normalizados correctamente.")

    resumen = {
        "etapa": "Obj2 / Actividad 3 / Paso 5",
        "estado": "AGREGACION_TECNICA_FINALIZADA_SIN_VALIDACION_SEMANTICA",
        "metodo": {
            "unidad": "registro académico u oferta laboral",
            "agregacion": "media_aritmetica_sin_pesos_de_vectores_ESCo_L2",
            "normalizacion_resultado": "L2",
            "peso_por_competencia": "igual_por_URI_en_cada_registro",
            "modelo_base": resumen_04["modelado"]["modelo"],
            "dimensiones": int(matriz_05.shape[1]),
            "interpretable_como_porcentaje_de_cobertura": False,
        },
        "conteos": {
            "registros_total": len(registros),
            "academia": conteos_origen["academia"],
            "mercado": conteos_origen["mercado"],
            "relaciones_registro_competencia": len(relaciones),
            "URI_ESCo_distintas": len(indice_por_uri),
            "ofertas_sin_ESCO_excluidas": conteos_03.get("ofertas_sin_esco_no_incluidas"),
        },
        "diagnostico": {
            "min_norma_media_sin_normalizar": min(normas_media),
            "max_norma_media_sin_normalizar": max(normas_media),
            "min_norma_vectores_guardados": float(np.linalg.norm(matriz_05, axis=1).min()),
            "max_norma_vectores_guardados": float(np.linalg.norm(matriz_05, axis=1).max()),
        },
        "entradas_sha256": {
            **{nombre: sha256(ruta) for nombre, ruta in archivos_03.items()},
            **{nombre: sha256(ruta) for nombre, ruta in archivos_04.items()},
        },
        "alertas": [
            "Las relaciones origen-ESCO siguen pendientes de validación humana.",
            "Las 14 ofertas sin ESCO no reciben vector; permanecen fuera de esta matriz.",
            "La media de etiquetas ESCO es una línea base, no una medida validada de pertinencia.",
            "No se ha calculado similitud academia-mercado, cobertura curricular ni clustering.",
        ],
    }
    return matriz_05, indice_05, resumen


def guardar_resultados(matriz: np.ndarray, indice: list[dict], resumen: dict) -> None:
    SALIDA.mkdir(parents=True, exist_ok=True)
    ruta_npy = SALIDA / ARCHIVO_MATRIZ_05
    ruta_csv = SALIDA / ARCHIVO_INDICE_05
    ruta_json = SALIDA / ARCHIVO_RESUMEN_05
    ruta_json.unlink(missing_ok=True)  # Evita tomar por bueno un resumen viejo.
    temp_npy = SALIDA / (ARCHIVO_MATRIZ_05 + ".temporal")
    temp_csv = SALIDA / (ARCHIVO_INDICE_05 + ".temporal")
    try:
        with temp_npy.open("wb") as archivo:
            np.save(archivo, matriz, allow_pickle=False)
        with temp_csv.open("w", encoding="utf-8-sig", newline="") as archivo:
            escritor = csv.DictWriter(archivo, fieldnames=COLUMNAS_INDICE_05, delimiter=";")
            escritor.writeheader()
            escritor.writerows(indice)
        os.replace(temp_npy, ruta_npy)
        os.replace(temp_csv, ruta_csv)
    finally:
        temp_npy.unlink(missing_ok=True)
        temp_csv.unlink(missing_ok=True)

    matriz_leida = np.load(ruta_npy, allow_pickle=False)
    indice_leido = leer_csv(ruta_csv, set(COLUMNAS_INDICE_05))
    if not np.array_equal(matriz_leida, matriz) or len(indice_leido) != len(indice):
        raise RuntimeError("Los resultados guardados no coinciden con lo calculado.")
    if any(int(fila["fila_vector_0_based"]) != i or fila["id_registro"] != indice[i]["id_registro"]
           for i, fila in enumerate(indice_leido)):
        raise RuntimeError("Se perdió la correspondencia entre vector e identificador de registro.")
    resumen["salidas_sha256"] = {ARCHIVO_MATRIZ_05: sha256(ruta_npy), ARCHIVO_INDICE_05: sha256(ruta_csv)}
    ruta_json.write_text(json.dumps(resumen, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    try:
        matriz, indice, resumen = validar_y_agregar()
        print("PASO 5 - DATOS VERIFICADOS")
        print(f"  Vectores ESCO de entrada: {resumen['conteos']['URI_ESCo_distintas']}")
        print(f"  Relaciones trazables: {resumen['conteos']['relaciones_registro_competencia']}")
        print("  Agregación: media aritmética + normalización L2, sin ponderación")
        guardar_resultados(matriz, indice, resumen)
    except (OSError, ValueError, RuntimeError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print("\nERROR EN EL PASO 5:", exc, file=sys.stderr)
        print("Comprueba salida_textos/ y salida_embeddings/ dentro de Act. 3.", file=sys.stderr)
        raise SystemExit(1)
    print("\nPASO 5 FINALIZADO CORRECTAMENTE")
    print(f"  Perfiles académicos: {resumen['conteos']['academia']}")
    print(f"  Ofertas laborales: {resumen['conteos']['mercado']}")
    print(f"  Matriz creada: {matriz.shape[0]} registros x {matriz.shape[1]} dimensiones")
    print("  Carpeta de salida:", SALIDA)
    print("  Archivos:", ARCHIVO_MATRIZ_05 + ",", ARCHIVO_INDICE_05 + ",", ARCHIVO_RESUMEN_05)
    print("  Nota: NO se calculó cobertura curricular ni clustering.")


if __name__ == "__main__":
    main()
