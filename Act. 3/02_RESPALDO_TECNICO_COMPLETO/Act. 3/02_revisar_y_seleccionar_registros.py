#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Obj2 / Actividad 3 / Etapa 1 / Paso 2: selección provisional y cola de revisión.

REQUISITOS: Python 3.9+; solo biblioteca estándar.

Desde DESARROLLO/Obj2/Act. 3:
    python 02_revisar_y_seleccionar_registros.py

Desde cualquier directorio:
    python 02_revisar_y_seleccionar_registros.py \
      --datos "RUTA/DESARROLLO/Obj2/Act. 1" \
      --validacion "RUTA/DESARROLLO/Obj2/Act. 3/salida_validacion" \
      --salida "RUTA/DESARROLLO/Obj2/Act. 3/salida_seleccion"

No modifica entradas, no calcula vectores, no entrena modelos y no valida
automáticamente la corrección semántica de las asociaciones ESCO.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

FUENTES = {
    "academia": (r"C:\Users\abasc\Desktop\DESARROLLO\Obj2\Act. 1\Perfiles_Normalizados_ESCO_12.csv", ("Universidad", "Carrera"), 12),
    "mercado": (r"C:\Users\abasc\Desktop\DESARROLLO\Obj2\Act. 1\Ofertas_Normalizadas_ESCO_diccionario.csv", ("job_id",), 8),
}
CAMPOS_INVENTARIO = [
    "origen", "fila_csv", "id_registro", "universidad", "carrera", "job_id",
    "titulo_oferta", "n_competencias_esco", "estado_esco", "estado_revision",
    "prioridad_revision", "motivos_revision", "elegible_vectorizacion_provisional",
    "motivo_exclusion", "aprobacion_semantica", "alcanza_limite_extractor",
]
CAMPOS_COMPETENCIAS = [
    "origen", "fila_csv", "id_registro", "posicion", "uri_esco",
    "etiqueta_esco", "evidencia_original", "estado_revision_registro",
]
CAMPOS_SELECCION = [
    "origen", "fila_csv", "id_registro", "universidad", "carrera", "job_id",
    "titulo_oferta", "n_competencias_esco", "uris_esco_json", "etiquetas_esco_json",
    "estado_esco", "estado_revision", "elegibilidad", "aviso_metodologico",
]
CAMPOS_PLANTILLA = [
    "origen", "fila_csv", "id_registro", "prioridad_revision", "motivos_revision",
    "n_competencias_esco", "decision_manual", "justificacion", "responsable", "fecha_revision",
]


def leer_csv(ruta: Path) -> list[dict[str, str]]:
    if not ruta.is_file():
        raise FileNotFoundError(f"No existe el archivo: {ruta}")
    csv.field_size_limit(10_000_000)
    with ruta.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        if not reader.fieldnames or len(reader.fieldnames) != len(set(reader.fieldnames)):
            raise ValueError(f"CSV sin encabezados válidos: {ruta}")
        filas = []
        for n, fila in enumerate(reader, 2):
            if None in fila:
                raise ValueError(f"{ruta.name}, fila {n}: columnas adicionales")
            filas.append({k: v or "" for k, v in fila.items()})
    return filas


def guardar_csv(ruta: Path, columnas: list[str], filas: list[dict]) -> None:
    with ruta.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columnas, delimiter=";", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(filas)


def resumen_validacion_y_inventario(ruta: Path) -> tuple[dict, dict]:
    archivo_resumen = ruta / "01_resumen_validacion.json"
    if not archivo_resumen.is_file():
        raise FileNotFoundError(f"Falta el resumen del paso 1: {archivo_resumen}")
    resumen = json.loads(archivo_resumen.read_text(encoding="utf-8-sig"))
    if resumen.get("incidencias_por_severidad", {}).get("ERROR", 0):
        raise ValueError("El paso 1 informó errores estructurales: no se puede seleccionar")
    inventario = leer_csv(ruta / "01_inventario_registros.csv")
    incidencias = leer_csv(ruta / "01_incidencias_validacion.csv")
    if any(i["severidad"] == "ERROR" for i in incidencias):
        raise ValueError("Las incidencias del paso 1 contienen errores estructurales")
    mapa = {}
    for fila in inventario:
        clave = (fila["origen"], int(fila["fila_csv"]))
        if clave in mapa:
            raise ValueError(f"Inventario de validación duplicado: {clave}")
        if int(fila["errores_estructurales"]) != 0:
            raise ValueError(f"Inventario tiene errores estructurales: {clave}")
        mapa[clave] = fila
    return resumen, mapa


def seleccionar(datos: Path, validacion: Path, salida: Path) -> dict:
    auditoria, inventario_validado = resumen_validacion_y_inventario(validacion)
    seleccionados: list[dict] = []
    inventario: list[dict] = []
    competencias: list[dict] = []
    conteos: dict[str, dict] = {}
    huellas = {}
    claves_vistas: set[tuple[str, int]] = set()

    for origen, (archivo, id_campos, limite) in FUENTES.items():
        ruta = datos / archivo
        filas = leer_csv(ruta)
        huellas[archivo] = hashlib.sha256(ruta.read_bytes()).hexdigest()
        n_con_esco = 0
        n_sin_esco = 0
        n_limite = 0
        n_pendiente = 0
        for numero, fila in enumerate(filas, 2):
            clave = (origen, numero)
            previo = inventario_validado.get(clave)
            if previo is None:
                raise ValueError(f"El paso 1 no cubrió {clave}; ejecutar nuevamente el paso 1")
            identificador = " | ".join(fila[k].strip() for k in id_campos)
            if previo["id_registro"] != identificador:
                raise ValueError(f"Cambio de identificador desde el paso 1: {clave}")
            try:
                uris = json.loads(fila["Competencias_ESCO_URI"])
                detalles = json.loads(fila["Competencias_ESCO_Detalle"])
            except (KeyError, json.JSONDecodeError) as exc:
                raise ValueError(f"JSON ESCO ilegible en {clave}: {exc}") from exc
            if not isinstance(uris, list) or not isinstance(detalles, list):
                raise ValueError(f"Listas ESCO inválidas en {clave}")
            if len(uris) != int(previo["n_competencias_esco"]):
                raise ValueError(f"Cambió la cantidad de competencias desde el paso 1: {clave}")
            if len(uris) != len(detalles) or any(
                not isinstance(d, dict) or d.get("uri") != uri
                for uri, d in zip(uris, detalles)
            ):
                raise ValueError(f"URIs y detalles difieren en {clave}")
            claves_vistas.add(clave)
            cantidad = len(uris)
            sin_esco = cantidad == 0
            saturado = cantidad >= limite
            estado = fila["Estado_ESCO"].strip()
            pendiente = "revision_pendiente" in estado.casefold() or "revisar" in estado.casefold()
            motivos = []
            if sin_esco:
                motivos.append("SIN_COMPETENCIAS_ESCO")
                n_sin_esco += 1
            else:
                n_con_esco += 1
            if saturado:
                motivos.append("ALCANZA_LIMITE_EXTRACTOR")
                n_limite += 1
            if pendiente:
                motivos.append("REVISION_ESCO_PENDIENTE")
                n_pendiente += 1
            # Prioridad de auditoría, NO confianza ni calidad del registro.
            prioridad = "P1_SIN_ESCO" if sin_esco else ("P2_TOPE_EXTRACTOR" if saturado else "P3_REVISION_GENERAL")
            estado_revision = "PENDIENTE_REVISION_HUMANA" if pendiente else "SIN_MARCA_REVISION_EN_FUENTE"
            es_elegible = not sin_esco
            inventario.append({
                "origen": origen, "fila_csv": numero, "id_registro": identificador,
                "universidad": fila.get("Universidad", ""),
                "carrera": fila.get("Carrera", ""), "job_id": fila.get("job_id", ""),
                "titulo_oferta": fila.get("titulo", ""),
                "n_competencias_esco": cantidad, "estado_esco": estado,
                "estado_revision": estado_revision, "prioridad_revision": prioridad,
                "motivos_revision": "|".join(motivos),
                "elegible_vectorizacion_provisional": "SI" if es_elegible else "NO",
                "motivo_exclusion": "SIN_COMPETENCIAS_ESCO" if sin_esco else "",
                "aprobacion_semantica": "NO_VERIFICADA",
                "alcanza_limite_extractor": "SI" if saturado else "NO",
            })
            if es_elegible:
                seleccionados.append({
                    "origen": origen, "fila_csv": numero, "id_registro": identificador,
                    "universidad": fila.get("Universidad", ""),
                    "carrera": fila.get("Carrera", ""), "job_id": fila.get("job_id", ""),
                    "titulo_oferta": fila.get("titulo", ""),
                    "n_competencias_esco": cantidad,
                    "uris_esco_json": json.dumps(uris, ensure_ascii=False),
                    "etiquetas_esco_json": json.dumps([d["etiqueta"] for d in detalles], ensure_ascii=False),
                    "estado_esco": estado, "estado_revision": estado_revision,
                    "elegibilidad": "PROVISIONAL_NO_VALIDADA_SEMANTICAMENTE",
                    "aviso_metodologico": "No interpretar como cobertura curricular o calidad ESCO",
                })
            for indice, (uri, detalle) in enumerate(zip(uris, detalles), start=1):
                competencias.append({
                    "origen": origen, "fila_csv": numero, "id_registro": identificador,
                    "posicion": indice, "uri_esco": uri,
                    "etiqueta_esco": detalle.get("etiqueta", ""),
                    "evidencia_original": detalle.get("evidencia", ""),
                    "estado_revision_registro": estado_revision,
                })
        if len(filas) != int(auditoria["registros"].get(origen, -1)):
            raise ValueError(f"Cambió la cantidad de filas de {origen} desde el paso 1")
        conteos[origen] = {
            "registros_originales": len(filas),
            "elegibles_provisionales": n_con_esco,
            "sin_esco_no_vectorizables": n_sin_esco,
            "en_tope_extractor": n_limite,
            "con_revision_pendiente": n_pendiente,
        }
    if claves_vistas != set(inventario_validado):
        raise ValueError("El inventario del paso 1 tiene filas que no aparecen en las entradas actuales")

    # Salidas repetibles. La plantilla de revisión humana se crea SOLO si no existe.
    salida.mkdir(parents=True, exist_ok=True)
    inventario.sort(key=lambda f: (0 if f["prioridad_revision"].startswith("P1") else
                                  1 if f["prioridad_revision"].startswith("P2") else 2,
                                  f["origen"], f["fila_csv"]))
    guardar_csv(salida / "02_inventario_y_prioridades.csv", CAMPOS_INVENTARIO, inventario)
    guardar_csv(salida / "02_competencias_para_auditar.csv", CAMPOS_COMPETENCIAS, competencias)
    guardar_csv(salida / "02_elegibles_provisionales.csv", CAMPOS_SELECCION, seleccionados)
    plantilla = salida / "02_plantilla_revision_manual.csv"
    plantilla_creada = not plantilla.exists()
    if plantilla_creada:
        guardar_csv(plantilla, CAMPOS_PLANTILLA, [{
            **{k: f[k] for k in CAMPOS_PLANTILLA if k in f},
            "decision_manual": "", "justificacion": "", "responsable": "", "fecha_revision": "",
        } for f in inventario])
    resumen = {
        "criterio": "ELEGIBLE PROVISIONAL si tiene >= 1 URI ESCO; sin ESCO se retiene pero no se vectoriza",
        "no_valida_semantica": True,
        "fuentes_sha256": huellas,
        "conteos": conteos,
        "totales": {
            "registros_originales": len(inventario),
            "elegibles_provisionales": len(seleccionados),
            "sin_esco_no_vectorizables": sum(f["n_competencias_esco"] == 0 for f in inventario),
            "competencias_asignadas_filas": len(competencias),
            "cola_revision_registros": len(inventario),
        },
        "prioridades": dict(sorted(Counter(f["prioridad_revision"] for f in inventario).items())),
        "plantilla_revision_manual_creada": plantilla_creada,
        "nota": "No usar las URIs ni etiquetas para calcular cobertura hasta revisar su validez. "
                "Tope del extractor indica posible truncamiento; no invalida automáticamente el registro.",
    }
    (salida / "02_resumen_seleccion.json").write_text(
        json.dumps(resumen, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return resumen


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    raiz = Path(__file__).resolve().parent
    parser.add_argument("--datos", type=Path, default=raiz.parent / "Act. 1")
    parser.add_argument("--validacion", type=Path, default=raiz / "salida_validacion")
    parser.add_argument("--salida", type=Path, default=raiz / "salida_seleccion")
    args = parser.parse_args()
    try:
        resumen = seleccionar(args.datos, args.validacion, args.salida)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(resumen, ensure_ascii=False, indent=2))
    print(f"\nArchivos generados en: {args.salida.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
