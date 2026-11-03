#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OBJ2 / ACTIVIDAD 3 / PASO 4: embeddings de etiquetas ESCO por URI.

USO EN VISUAL STUDIO CODE:
  1) Copiar este .py a DESARROLLO/Obj2/Act. 3/.
  2) Ejecutar 03_preparar_corpus_esco.py (si aún no se hizo).
  3) Abrir este .py y presionar ▶ «Ejecutar archivo Python».

NO hace falta teclear comandos en una terminal. Si faltan paquetes, el script
puede instalarlos en el intérprete Python seleccionado en VS Code. La primera
vez también necesita conexión a Internet para descargar el modelo preentrenado.

SÓLO vectoriza las etiquetas ESCO del paso 3. No crea clusters, no aprueba
mapeos ESCO ni mide cobertura curricular. No modifica los archivos originales.
"""
from __future__ import annotations

import csv
import hashlib
import importlib
import importlib.metadata
import json
import math
import os
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

# ================================================================
# 1. CONFIGURACIÓN: modificar aquí sólo si lo necesitas.
# ================================================================
MODELO = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
TAMANO_LOTE = 32                 # Si hay poca memoria, usar 8 o 16.
USAR_CPU = True                 # Evita incompatibilidades con GPU.
INSTALAR_DEPENDENCIAS_SI_FALTAN = True  # Instala paquetes al pulsar ▶.
CARPETA_ACT3 = Path(__file__).resolve().parent
CARPETA_ENTRADAS = CARPETA_ACT3 / "salida_textos"
CARPETA_SALIDAS = CARPETA_ACT3 / "salida_embeddings"

# Nombres de archivos de salida. Un índice 0 equivale a la primera fila .npy.
ARCHIVO_MATRIZ = "04_embeddings_competencias_esco.npy"
ARCHIVO_INDICE = "04_indice_embeddings_esco.csv"
ARCHIVO_RESUMEN = "04_resumen_embeddings.json"


def huella_sha256(ruta: Path) -> str:
    digest = hashlib.sha256()
    with ruta.open("rb") as archivo:
        for trozo in iter(lambda: archivo.read(1024 * 1024), b""):
            digest.update(trozo)
    return digest.hexdigest()


def leer_csv(ruta: Path) -> list[dict[str, str]]:
    if not ruta.is_file():
        raise FileNotFoundError(f"No se encuentra el archivo del paso 3: {ruta}")
    csv.field_size_limit(20_000_000)
    with ruta.open("r", encoding="utf-8-sig", newline="") as archivo:
        lector = csv.DictReader(archivo, delimiter=";")
        if not lector.fieldnames or len(set(lector.fieldnames)) != len(lector.fieldnames):
            raise ValueError(f"Encabezados inexistentes/repetidos: {ruta.name}")
        filas = list(lector)
        if any(None in f or any(v is None for v in f.values()) for f in filas):
            raise ValueError(f"CSV irregular: {ruta.name}")
    return filas


def comprobar_entradas(carpeta: Path) -> tuple[list[dict[str, str]], dict, dict]:
    """Comprueba integridad de entrada sin cargar modelo ni instalar paquetes."""
    nombres = [
        "03_catalogo_competencias_esco.csv",
        "03_relaciones_trazables.csv",
        "03_registros_preparados.csv",
        "03_resumen_corpus.json",
    ]
    rutas = {nombre: carpeta / nombre for nombre in nombres}
    for ruta in rutas.values():
        if not ruta.is_file():
            raise FileNotFoundError(
                f"Falta {ruta.name}. Ejecuta primero 03_preparar_corpus_esco.py con ▶, "
                "desde la misma carpeta Act. 3."
            )
    resumen3 = json.loads(rutas["03_resumen_corpus.json"].read_text(encoding="utf-8-sig"))
    catalogo = leer_csv(rutas["03_catalogo_competencias_esco.csv"])
    relaciones = leer_csv(rutas["03_relaciones_trazables.csv"])
    registros = leer_csv(rutas["03_registros_preparados.csv"])

    columnas_cat = {"uri_esco", "etiqueta_esco", "texto_para_embedding", "asignaciones"}
    columnas_rel = {"uri_esco", "texto_para_embedding", "origen", "fila_csv", "id_registro"}
    columnas_reg = {"origen", "fila_csv", "id_registro", "n_competencias_esco"}
    if not catalogo or not columnas_cat.issubset(catalogo[0]):
        raise ValueError("Faltan columnas requeridas en 03_catalogo_competencias_esco.csv")
    if not relaciones or not columnas_rel.issubset(relaciones[0]):
        raise ValueError("Faltan columnas requeridas en 03_relaciones_trazables.csv")
    if not registros or not columnas_reg.issubset(registros[0]):
        raise ValueError("Faltan columnas requeridas en 03_registros_preparados.csv")

    esperados = resumen3.get("conteos", {})
    if len(catalogo) != esperados.get("competencias_uris_unicas", -1):
        raise ValueError("Cantidad de URI distinta del resumen del paso 3")
    if len(relaciones) != esperados.get("asignaciones_registro_competencia", -1):
        raise ValueError("Cantidad de relaciones distinta del resumen del paso 3")
    if len(registros) != esperados.get("registros_totales_preparados", -1):
        raise ValueError("Cantidad de registros distinta del resumen del paso 3")

    indice = {}
    etiqueta_a_uris = defaultdict(list)
    for numero, fila in enumerate(catalogo):
        uri = fila["uri_esco"].strip()
        texto = fila["texto_para_embedding"]
        if not uri.startswith("http://data.europa.eu/esco/skill/"):
            raise ValueError(f"URI ESCO inesperada en fila {numero + 2}: {uri}")
        if not texto.strip() or texto != " ".join(texto.split()):
            raise ValueError(f"Texto ESCO vacío o con espacios inconsistentes: {uri}")
        if uri in indice:
            raise ValueError(f"URI ESCO repetida en catálogo: {uri}")
        if int(fila["asignaciones"]) < 1:
            raise ValueError(f"URI sin asignaciones: {uri}")
        indice[uri] = fila
        etiqueta_a_uris[texto].append(uri)

    recuento = Counter()
    for relacion in relaciones:
        uri = relacion["uri_esco"]
        if uri not in indice:
            raise ValueError(f"Relación con URI no presente en catálogo: {uri}")
        if relacion["texto_para_embedding"] != indice[uri]["texto_para_embedding"]:
            raise ValueError(f"Texto incompatible para la URI {uri}")
        recuento[uri] += 1
    for uri, fila in indice.items():
        if recuento[uri] != int(fila["asignaciones"]):
            raise ValueError(f"Asignaciones inconsistentes para URI: {uri}")

    claves_registros = set()
    n_relaciones_por_registro = Counter()
    for fila in registros:
        clave = (fila["origen"], fila["fila_csv"], fila["id_registro"])
        if clave in claves_registros:
            raise ValueError(f"Registro duplicado: {clave}")
        claves_registros.add(clave)
    for fila in relaciones:
        clave = (fila["origen"], fila["fila_csv"], fila["id_registro"])
        if clave not in claves_registros:
            raise ValueError(f"Relación huérfana: {clave}")
        n_relaciones_por_registro[clave] += 1
    for fila in registros:
        clave = (fila["origen"], fila["fila_csv"], fila["id_registro"])
        if n_relaciones_por_registro[clave] != int(fila["n_competencias_esco"]):
            raise ValueError(f"Número de competencias inconsistente: {clave}")

    # Si la carpeta Act. 1 original sigue al lado, confirmar su SHA256.
    datos = carpeta.parent.parent / "Act. 1"
    for archivo, huella in resumen3.get("fuentes_sha256", {}).items():
        original = datos / archivo
        if original.is_file() and huella_sha256(original) != huella:
            raise ValueError(
                f"El original {archivo} cambió desde el paso 3. "
                "Vuelve a ejecutar primero los pasos 1, 2 y 3."
            )

    control = {
        "archivos_paso3_sha256": {n: huella_sha256(p) for n, p in rutas.items()},
        "uri_con_misma_etiqueta": [
            {"texto": t, "uris": us} for t, us in sorted(etiqueta_a_uris.items()) if len(us) > 1
        ],
        "total_relaciones": len(relaciones),
        "total_registros": len(registros),
    }
    return catalogo, resumen3, control


def instalar_paquetes_si_hace_falta() -> None:
    """Instalación transparente en el intérprete seleccionado por VS Code."""
    faltan = []
    if importlib.util.find_spec("numpy") is None:
        faltan.append("numpy")
    if importlib.util.find_spec("sentence_transformers") is None:
        faltan.append("sentence-transformers")
    if not faltan:
        return
    if not INSTALAR_DEPENDENCIAS_SI_FALTAN:
        raise RuntimeError(
            "Faltan bibliotecas: " + ", ".join(faltan) + ". "
            "Activa INSTALAR_DEPENDENCIAS_SI_FALTAN = True para instalarlas con ▶."
        )
    print("\nPRIMER USO: faltan las bibliotecas:", ", ".join(faltan), flush=True)
    print("Se instalarán mediante pip en ESTE intérprete Python de VS Code.", flush=True)
    print("Esto requiere conexión a Internet; puede descargar paquetes grandes.\n", flush=True)
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", *faltan],
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(
            "No fue posible instalar las dependencias automáticamente. "
            "Revisa tu conexión a Internet y el intérprete Python elegido en VS Code. "
            f"Detalle: {exc}"
        ) from exc
    importlib.invalidate_caches()


def obtener_version(paquete: str) -> str | None:
    try:
        return importlib.metadata.version(paquete)
    except importlib.metadata.PackageNotFoundError:
        return None


def codificar_textos(textos: list[str]) -> tuple[object, dict]:
    """El modelo real se usa SIEMPRE al ejecutar este archivo normalmente."""
    instalar_paquetes_si_hace_falta()
    from sentence_transformers import SentenceTransformer

    print(f"\nCargando modelo: {MODELO}", flush=True)
    print("Si es la primera ejecución, se descargará una copia a la caché local.", flush=True)
    modelo = SentenceTransformer(MODELO, device="cpu" if USAR_CPU else None)
    print(f"Generando embeddings para {len(textos)} competencias...", flush=True)
    matriz = modelo.encode(
        textos,
        batch_size=TAMANO_LOTE,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=True,
    )

    # Registrar commit cuando la librería/modelo expone ese dato.
    commit = None
    try:
        transformer = getattr(modelo, "transformers_model", None)
        configuracion = getattr(transformer, "config", None)
        commit = getattr(configuracion, "_commit_hash", None)
    except (AttributeError, TypeError):
        pass
    return matriz, {
        "modelo": MODELO,
        "modelo_commit_si_disponible": commit,
        "dimension_declarada": modelo.get_sentence_embedding_dimension(),
        "device": str(modelo.device),
        "version_sentence_transformers": obtener_version("sentence-transformers"),
        "version_transformers": obtener_version("transformers"),
        "version_torch": obtener_version("torch"),
        "version_numpy": obtener_version("numpy"),
    }


def verificar_matriz(matriz, textos: list[str], catalogo: list[dict]):
    import numpy as np

    matriz = np.asarray(matriz, dtype=np.float32)
    if matriz.ndim != 2 or matriz.shape[0] != len(catalogo) or matriz.shape[1] < 2:
        raise ValueError(f"Dimensiones inesperadas de embeddings: {matriz.shape}")
    if not np.isfinite(matriz).all():
        raise ValueError("La matriz tiene valores NaN o infinitos")
    normas = np.linalg.norm(matriz, axis=1)
    if not np.allclose(normas, 1.0, atol=2e-3):
        raise ValueError("No todos los vectores tienen norma aproximadamente 1")

    # La misma frase debe dar el mismo vector aunque sean URI diferentes.
    primera_posicion = {}
    for i, texto in enumerate(textos):
        j = primera_posicion.setdefault(texto, i)
        if i != j and not np.allclose(matriz[i], matriz[j], atol=1e-5):
            raise ValueError(f"Misma etiqueta con embeddings distintos: {texto}")
    return matriz, normas


def escribir_csv(ruta: Path, cabeceras: list[str], filas: list[dict]) -> None:
    with ruta.open("w", newline="", encoding="utf-8-sig") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=cabeceras, delimiter=";", extrasaction="ignore")
        escritor.writeheader()
        escritor.writerows(filas)


def ejecutar(carpeta_entradas: Path, carpeta_salidas: Path,
             proveedor=None, datos_proveedor: dict | None = None) -> dict:
    """Permite pruebas con un proveedor de prueba, no usado por el botón ▶."""
    catalogo, resumen3, control = comprobar_entradas(carpeta_entradas)
    textos = [fila["texto_para_embedding"] for fila in catalogo]
    print("PASO 4 - ENTRADAS VERIFICADAS")
    print(f"  Registros base: {control['total_registros']}")
    print(f"  Relaciones registro-competencia: {control['total_relaciones']}")
    print(f"  URI ESCO distintas: {len(catalogo)}")
    print(f"  Etiquetas compartidas por varias URI: {len(control['uri_con_misma_etiqueta'])}")
    print("  Representación: embedding de cada etiqueta ESCO, conservando su URI")

    if proveedor is None:
        matriz_cruda, metadatos_modelo = codificar_textos(textos)
    else:
        # Sólo para pruebas técnicas automatizadas; nunca es una opción del usuario.
        matriz_cruda = proveedor(textos)
        metadatos_modelo = datos_proveedor or {"tipo": "PRUEBA_TECNICA_NO_ES_EMBEDDING_REAL"}
    matriz, normas = verificar_matriz(matriz_cruda, textos, catalogo)

    lista_indice = []
    for i, fila in enumerate(catalogo):
        lista_indice.append({
            "fila_vector_0_based": i,
            "uri_esco": fila["uri_esco"],
            "etiqueta_esco": fila["etiqueta_esco"],
            "texto_para_embedding": textos[i],
            "asignaciones": fila["asignaciones"],
            "registros_academia": fila["registros_academia"],
            "registros_mercado": fila["registros_mercado"],
        })

    import numpy as np
    carpeta_salidas.mkdir(parents=True, exist_ok=True)
    ruta_matriz = carpeta_salidas / ARCHIVO_MATRIZ
    ruta_indice = carpeta_salidas / ARCHIVO_INDICE
    ruta_resumen = carpeta_salidas / ARCHIVO_RESUMEN

    # Invalidar resumen anterior: una ejecución fallida no debe quedar validada.
    ruta_resumen.unlink(missing_ok=True)
    temporal_matriz = carpeta_salidas / (ARCHIVO_MATRIZ + ".temporal")
    temporal_indice = carpeta_salidas / (ARCHIVO_INDICE + ".temporal")
    try:
        with temporal_matriz.open("wb") as archivo:
            np.save(archivo, matriz, allow_pickle=False)
        escribir_csv(temporal_indice, list(lista_indice[0]), lista_indice)
        os.replace(temporal_matriz, ruta_matriz)
        os.replace(temporal_indice, ruta_indice)
    finally:
        temporal_matriz.unlink(missing_ok=True)
        temporal_indice.unlink(missing_ok=True)

    # Comprobación de lectura desde disco de los artefactos finales.
    almacenada = np.load(ruta_matriz, allow_pickle=False)
    indice_recargado = leer_csv(ruta_indice)
    if almacenada.shape != matriz.shape or not np.array_equal(almacenada, matriz):
        raise RuntimeError("La matriz guardada no coincide con la calculada")
    if len(indice_recargado) != len(catalogo):
        raise RuntimeError("El índice guardado no coincide con el catálogo")
    if any(fila["uri_esco"] != catalogo[i]["uri_esco"] or
           int(fila["fila_vector_0_based"]) != i
           for i, fila in enumerate(indice_recargado)):
        raise RuntimeError("Se perdió la correspondencia entre vector y URI")

    resumen = {
        "etapa": "Obj2 / Actividad 3 / Paso 4",
        "estado": "EMBEDDINGS_CALCULADOS_SIN_VALIDACION_SEMANTICA_ESPECIALIZADA",
        "modelado": metadatos_modelo,
        "parametros": {
            "tamano_lote": TAMANO_LOTE,
            "normalizacion_l2": True,
            "tipo_dato": "float32",
            "unidad_vectorizada": "una URI ESCO y su etiqueta",
            "metodo_agregacion_por_registro": "AUN_NO_APLICADO",
        },
        "conteos": {
            "competencias_uri": int(matriz.shape[0]),
            "dimensiones_vector": int(matriz.shape[1]),
            "registros_preparados_paso3": control["total_registros"],
            "relaciones_paso3": control["total_relaciones"],
            "etiquetas_compartidas_por_multiples_uri": len(control["uri_con_misma_etiqueta"]),
            "minima_norma": float(normas.min()),
            "maxima_norma": float(normas.max()),
        },
        "archivo_indice": ARCHIVO_INDICE,
        "archivo_matriz": ARCHIVO_MATRIZ,
        "entradas_sha256": control["archivos_paso3_sha256"],
        "salidas_sha256": {
            ARCHIVO_INDICE: huella_sha256(ruta_indice),
            ARCHIVO_MATRIZ: huella_sha256(ruta_matriz),
        },
        "alertas": [
            "Los mapeos de origen a ESCO son provisionales; no se verificó su corrección.",
            "Las URI distintas con etiqueta idéntica producen el mismo vector textual.",
            "La similitud coseno no es un porcentaje de cobertura curricular.",
            "El identificador del modelo puede cambiar de revisión; revisar commit registrado cuando exista.",
        ],
    }
    ruta_resumen.write_text(json.dumps(resumen, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return resumen


def main() -> None:
    if sys.version_info < (3, 10):
        print("ERROR: para este modelo se recomienda Python 3.10 o posterior.")
        print("En VS Code, selecciona el intérprete desde 'Python: Select Interpreter'.")
        return
    try:
        resumen = ejecutar(CARPETA_ENTRADAS, CARPETA_SALIDAS)
    except (ValueError, RuntimeError, OSError, ImportError, KeyError) as exc:
        print("\nERROR EN EL PASO 4:", exc, file=sys.stderr)
        print("Verifica la carpeta salida_textos, el intérprete Python y la conexión.", file=sys.stderr)
        raise SystemExit(1)
    print("\nPASO 4 FINALIZADO CORRECTAMENTE")
    print("  Vectores:", resumen["conteos"]["competencias_uri"])
    print("  Dimensiones:", resumen["conteos"]["dimensiones_vector"])
    print("  Carpeta de salida:", CARPETA_SALIDAS.resolve())
    print("  Archivos: " + ", ".join((ARCHIVO_MATRIZ, ARCHIVO_INDICE, ARCHIVO_RESUMEN)))
    print("  Atención: aún NO se ha medido similitud ni cobertura curricular.")


if __name__ == "__main__":
    main()
