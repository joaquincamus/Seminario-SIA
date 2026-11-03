#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Obj2 / Actividad 3 / Etapa 1: auditar los CSV normalizados de ESCO.

Este script NO modifica los datos originales, NO vectoriza y NO hace clustering.
Usa únicamente la biblioteca estándar de Python (3.9+).

Ejecución desde DESARROLLO/Obj2/Act. 3:
    python 01_validar_entradas_esco.py

Ejecución desde cualquier ubicación:
    python 01_validar_entradas_esco.py --datos "RUTA/DESARROLLO/Obj2/Act. 1" --salida "RUTA/validacion"

Códigos de salida: 0 = sin errores estructurales (puede haber advertencias);
                   2 = errores estructurales encontrados;
                   1 = no fue posible leer los archivos de entrada.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path


CONFIG = {
    "academia": {
        "archivo": "Perfiles_Normalizados_ESCO_12.csv",
        "identificadores": ("Universidad", "Carrera"),
        "texto_fuente": "Perfil_Egreso",
        "maximo_extractor": 12,
        "cantidad_esperada": 46,
    },
    "mercado": {
        "archivo": "Ofertas_Normalizadas_ESCO_diccionario.csv",
        "identificadores": ("job_id",),
        "texto_fuente": "texto_bruto",
        "maximo_extractor": 8,
        "cantidad_esperada": 242,
    },
}
COLUMNAS_ESCO = (
    "Competencias_ESCO_URI",
    "Competencias_ESCO_Detalle",
    "Estado_ESCO",
    "SHA256_catalogo_ESCO",
)
URI_ESCO = re.compile(r"^https?://data\.europa\.eu/esco/skill/[0-9a-fA-F-]{36}$")
SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")
COLUMNAS_INCIDENCIAS = ("severidad", "origen", "fila_csv", "id_registro", "codigo", "detalle")
COLUMNAS_INVENTARIO = (
    "origen", "fila_csv", "id_registro", "universidad", "carrera", "job_id",
    "n_competencias_esco", "estado_esco", "revision_pendiente", "alcanza_limite_extractor",
    "errores_estructurales",
)


def cargar_csv(ruta: Path) -> tuple[list[str], list[dict[str, str]]]:
    """Lee CSV separado por punto y coma; conserva todos los valores como texto."""
    # Un campo con descripción extensa puede exceder el límite predeterminado de csv.
    csv.field_size_limit(10_000_000)
    with ruta.open("r", encoding="utf-8-sig", newline="") as archivo:
        lector = csv.DictReader(archivo, delimiter=";")
        columnas = lector.fieldnames or []
        if not columnas:
            raise ValueError("CSV vacío o sin encabezados")
        if len(columnas) != len(set(columnas)):
            raise ValueError("Encabezados duplicados")
        filas = []
        for numero, fila in enumerate(lector, start=2):
            if None in fila:  # columnas extra debidas a delimitador o CSV mal formado
                raise ValueError(f"Fila {numero}: más campos que encabezados")
            filas.append({k: (v if v is not None else "") for k, v in fila.items()})
        return columnas, filas


def es_revision_pendiente(estado: str) -> bool:
    estado = estado.casefold()
    return "revision_pendiente" in estado or "revisar" in estado


def auditar(datos: Path, salida: Path) -> dict:
    incidencias: list[dict] = []
    inventario: list[dict] = []
    conteos = {}
    uris_por_origen = {origen: set() for origen in CONFIG}
    etiquetas_por_uri: dict[str, set[str]] = defaultdict(set)
    hashes_por_origen: dict[str, set[str]] = defaultdict(set)
    estados_por_origen = {}
    n_incidencias = Counter()
    n_validos = Counter()
    universidades = set()

    def reportar(severidad: str, origen: str, fila: int | str,
                 identificador: str, codigo: str, detalle: str) -> None:
        incidencias.append({
            "severidad": severidad,
            "origen": origen,
            "fila_csv": fila,
            "id_registro": identificador,
            "codigo": codigo,
            "detalle": detalle,
        })
        n_incidencias[severidad] += 1

    for origen, conf in CONFIG.items():
        ruta = datos / conf["archivo"]
        if not ruta.is_file():
            raise FileNotFoundError(f"No existe el archivo de entrada: {ruta}")
        columnas, filas = cargar_csv(ruta)
        obligatorias = set(conf["identificadores"]) | set(COLUMNAS_ESCO) | {conf["texto_fuente"]}
        ausentes = sorted(obligatorias - set(columnas))
        if ausentes:
            raise ValueError(f"{ruta.name}: faltan columnas obligatorias: {', '.join(ausentes)}")

        conteos[origen] = len(filas)
        estados_por_origen[origen] = dict(Counter(f["Estado_ESCO"].strip() for f in filas))
        if len(filas) != conf["cantidad_esperada"]:
            reportar("ADVERTENCIA", origen, "", "", "CANTIDAD_INESPERADA",
                     f"Se esperaban {conf['cantidad_esperada']} registros, se encontraron {len(filas)}")

        ids_vistos: dict[tuple[str, ...], int] = {}
        for numero, fila in enumerate(filas, start=2):
            clave = tuple(fila[c].strip() for c in conf["identificadores"])
            identificador = " | ".join(clave)
            errores_antes = n_incidencias["ERROR"]
            if not all(clave):
                reportar("ERROR", origen, numero, identificador, "IDENTIFICADOR_INCOMPLETO",
                         "Falta al menos una parte del identificador del registro")
            clave_normalizada = tuple(c.casefold() for c in clave)
            if clave_normalizada in ids_vistos:
                reportar("ERROR", origen, numero, identificador, "IDENTIFICADOR_DUPLICADO",
                         f"Coincide con la fila {ids_vistos[clave_normalizada]}")
            else:
                ids_vistos[clave_normalizada] = numero

            if not fila[conf["texto_fuente"]].strip():
                reportar("ADVERTENCIA", origen, numero, identificador, "TEXTO_FUENTE_VACIO",
                         f"Columna {conf['texto_fuente']} sin texto para contrastar")

            estado = fila["Estado_ESCO"].strip()
            pendiente = es_revision_pendiente(estado)
            if not estado:
                reportar("ADVERTENCIA", origen, numero, identificador, "ESTADO_ESCO_VACIO",
                         "Sin trazabilidad del estado de normalización")
            elif pendiente:
                reportar("ADVERTENCIA", origen, numero, identificador, "REVISION_ESCO_PENDIENTE", estado)

            hash_catalogo = fila["SHA256_catalogo_ESCO"].strip()
            if not SHA256.fullmatch(hash_catalogo):
                reportar("ERROR", origen, numero, identificador, "HASH_CATALOGO_INVALIDO",
                         "SHA256_catalogo_ESCO no tiene 64 caracteres hexadecimales")
            else:
                hashes_por_origen[origen].add(hash_catalogo.casefold())

            uris = None
            detalles = None
            for campo in ("Competencias_ESCO_URI", "Competencias_ESCO_Detalle"):
                try:
                    contenido = json.loads(fila[campo])
                    if not isinstance(contenido, list):
                        raise ValueError("Debe ser una lista JSON")
                    if campo == "Competencias_ESCO_URI":
                        uris = contenido
                    else:
                        detalles = contenido
                except (json.JSONDecodeError, ValueError, TypeError) as exc:
                    reportar("ERROR", origen, numero, identificador, "JSON_INVALIDO",
                             f"{campo}: {exc}")

            cantidad = len(uris) if uris is not None else None
            if uris is not None:
                if cantidad == 0:
                    reportar("ADVERTENCIA", origen, numero, identificador, "SIN_COMPETENCIAS_ESCO",
                             "No equivale a demostrar ausencia real de competencias")
                if cantidad >= conf["maximo_extractor"]:
                    reportar("ADVERTENCIA", origen, numero, identificador, "ALCANZA_LIMITE_EXTRACTOR",
                             f"{cantidad} competencias; revisar posible truncamiento")
                for pos, uri in enumerate(uris, start=1):
                    if not isinstance(uri, str) or not URI_ESCO.fullmatch(uri.strip()):
                        reportar("ERROR", origen, numero, identificador, "URI_ESCO_INVALIDA",
                                 f"Competencia {pos}: URI ESCO inválida")
                    else:
                        uris_por_origen[origen].add(uri.strip())
                solo_strings = [u.strip() for u in uris if isinstance(u, str)]
                if len(solo_strings) != len(set(solo_strings)):
                    reportar("ERROR", origen, numero, identificador, "URI_REPETIDA_EN_REGISTRO",
                             "Una URI ESCO aparece más de una vez en el registro")

            if detalles is not None:
                for pos, detalle in enumerate(detalles, start=1):
                    if not isinstance(detalle, dict):
                        reportar("ERROR", origen, numero, identificador, "DETALLE_MAL_FORMADO",
                                 f"Competencia {pos}: se esperaba un objeto con uri, etiqueta y evidencia")
                        continue
                    uri = detalle.get("uri")
                    etiqueta = detalle.get("etiqueta")
                    evidencia = detalle.get("evidencia")
                    if not isinstance(uri, str) or not URI_ESCO.fullmatch(uri.strip()):
                        reportar("ERROR", origen, numero, identificador, "DETALLE_URI_INVALIDA",
                                 f"Competencia {pos}: detalle sin URI ESCO válida")
                    if not isinstance(etiqueta, str) or not etiqueta.strip():
                        reportar("ERROR", origen, numero, identificador, "ETIQUETA_VACIA",
                                 f"Competencia {pos}: etiqueta vacía")
                    if not isinstance(evidencia, str) or not evidencia.strip():
                        reportar("ADVERTENCIA", origen, numero, identificador, "EVIDENCIA_VACIA",
                                 f"Competencia {pos}: falta evidencia textual del mapeo")
                    if isinstance(uri, str) and isinstance(etiqueta, str) and uri.strip() and etiqueta.strip():
                        etiquetas_por_uri[uri.strip()].add(etiqueta.strip().casefold())

            if uris is not None and detalles is not None:
                uris_detalle = [d.get("uri", "") if isinstance(d, dict) else "" for d in detalles]
                if uris != uris_detalle:
                    reportar("ERROR", origen, numero, identificador, "URI_DETALLE_NO_COINCIDE",
                             "Las URIs y su orden difieren entre Competencias_ESCO_URI y Competencias_ESCO_Detalle")

            if origen == "academia":
                universidades.add(fila["Universidad"].strip())
            errores_registro = n_incidencias["ERROR"] - errores_antes
            n_validos[origen] += int(errores_registro == 0)
            inventario.append({
                "origen": origen,
                "fila_csv": numero,
                "id_registro": identificador,
                "universidad": fila.get("Universidad", ""),
                "carrera": fila.get("Carrera", ""),
                "job_id": fila.get("job_id", ""),
                "n_competencias_esco": cantidad if cantidad is not None else "",
                "estado_esco": estado,
                "revision_pendiente": str(pendiente).lower(),
                "alcanza_limite_extractor": str(cantidad is not None and cantidad >= conf["maximo_extractor"]).lower(),
                "errores_estructurales": errores_registro,
            })

    todos_hashes = set().union(*hashes_por_origen.values())
    if len(todos_hashes) > 1:
        reportar("ADVERTENCIA", "ambos", "", "", "CATALOGOS_ESCO_DIFERENTES",
                 "Se detectaron distintos SHA256 de catálogo ESCO entre registros")
    discordantes = {uri: etiquetas for uri, etiquetas in etiquetas_por_uri.items() if len(etiquetas) > 1}
    for uri, etiquetas in sorted(discordantes.items()):
        reportar("ADVERTENCIA", "ambos", "", uri, "ETIQUETAS_DIFERENTES_MISMA_URI",
                 " | ".join(sorted(etiquetas)))

    resumen = {
        "archivos_entrada": {origen: str(datos / conf["archivo"]) for origen, conf in CONFIG.items()},
        "registros": conteos,
        "registros_sin_errores_estructurales": dict(n_validos),
        "instituciones_academicas_distintas": len(universidades - {""}),
        "competencias_uris_unicas": {
            "academia": len(uris_por_origen["academia"]),
            "mercado": len(uris_por_origen["mercado"]),
            "compartidas": len(uris_por_origen["academia"] & uris_por_origen["mercado"]),
            "total": len(uris_por_origen["academia"] | uris_por_origen["mercado"]),
        },
        "catalogos_sha256_distintos": len(todos_hashes),
        "estados_esco": estados_por_origen,
        "incidencias_por_severidad": {s: n_incidencias[s] for s in ("ERROR", "ADVERTENCIA")},
        "incidencias_por_codigo": dict(sorted(Counter(i["codigo"] for i in incidencias).items())),
        "apto_estructuralmente_para_siguiente_paso": n_incidencias["ERROR"] == 0,
        "advertencia_metodologica": (
            "Aptitud estructural NO demuestra validez semántica del mapeo ESCO, "
            "representatividad de la muestra ni cobertura curricular."
        ),
    }
    salida.mkdir(parents=True, exist_ok=True)
    escribir_csv(salida / "01_incidencias_validacion.csv", COLUMNAS_INCIDENCIAS, incidencias)
    escribir_csv(salida / "01_inventario_registros.csv", COLUMNAS_INVENTARIO, inventario)
    (salida / "01_resumen_validacion.json").write_text(
        json.dumps(resumen, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return resumen


def escribir_csv(ruta: Path, columnas: tuple[str, ...], filas: list[dict]) -> None:
    with ruta.open("w", encoding="utf-8-sig", newline="") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=columnas, delimiter=";", extrasaction="ignore")
        escritor.writeheader()
        escritor.writerows(filas)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    carpeta_script = Path(__file__).resolve().parent
    parser.add_argument("--datos", type=Path, default=carpeta_script.parent / "Act. 1",
                        help="Carpeta con Perfiles_Normalizados_ESCO_12.csv y Ofertas_Normalizadas_ESCO_diccionario.csv")
    parser.add_argument("--salida", type=Path, default=carpeta_script / "salida_validacion",
                        help="Carpeta destino de los tres informes (los datos fuente no se modifican)")
    args = parser.parse_args()
    try:
        resultado = auditar(args.datos.resolve(), args.salida.resolve())
    except (OSError, ValueError, csv.Error) as exc:
        print(f"ERROR AL LEER DATOS: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    print(f"\nInformes guardados en: {args.salida.resolve()}")
    return 0 if resultado["apto_estructuralmente_para_siguiente_paso"] else 2


if __name__ == "__main__":
    sys.exit(main())
