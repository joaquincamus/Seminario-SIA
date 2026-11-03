#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Obj2 / Act. 3 / Etapa 1 / Paso 3: corpus trazable de etiquetas ESCO.

Python 3.9+, sin dependencias externas.

En Visual Studio Code: abrir este archivo en DESARROLLO/Obj2/Act. 3 y pulsar
    ▶ Run Python File (Ejecutar archivo Python), sin escribir comandos.

Rutas por defecto relativas al archivo .py, NO a la carpeta de trabajo.

También permite rutas explícitas:
    python 03_preparar_corpus_esco.py --seleccion RUTA/salida_seleccion \
      --datos RUTA/Obj2/Act. 1 --salida RUTA/salida_textos

Requiere el paso 2 y los CSV originales INALTERADOS. No vectoriza, entrena,
compara ofertas/perfiles ni aprueba la asignación semántica de ESCO.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

FUENTES = (r"C:\Users\abasc\Desktop\DESARROLLO\Obj2\Act. 1\Perfiles_Normalizados_ESCO_12.csv", r"C:\Users\abasc\Desktop\DESARROLLO\Obj2\Act. 1\Ofertas_Normalizadas_ESCO_diccionario.csv")
COL_REG = [
    "origen", "fila_csv", "id_registro", "universidad", "carrera", "job_id",
    "titulo_oferta", "n_competencias_esco", "uris_esco_json",
    "etiquetas_esco_json", "texto_concatenado_diagnostico",
    "estado_revision", "elegibilidad", "representacion_recomendada",
]
COL_CON = [
    "uri_esco", "etiqueta_esco", "texto_para_embedding", "asignaciones",
    "registros_academia", "registros_mercado", "requiere_revision_semantica",
]
COL_LINK = [
    "origen", "fila_csv", "id_registro", "posicion", "uri_esco",
    "etiqueta_esco", "texto_para_embedding", "evidencia_original",
    "estado_revision_registro",
]
COL_ALERT = ["tipo", "valor", "uris_esco_json", "detalle"]


def leer_csv(ruta: Path) -> list[dict[str, str]]:
    if not ruta.is_file():
        raise FileNotFoundError(f"No se encuentra: {ruta}")
    csv.field_size_limit(20_000_000)
    with ruta.open("r", encoding="utf-8-sig", newline="") as f:
        lector = csv.DictReader(f, delimiter=";")
        if not lector.fieldnames or len(set(lector.fieldnames)) != len(lector.fieldnames):
            raise ValueError(f"Encabezados repetidos o inexistentes: {ruta}")
        resultado = []
        for num, fila in enumerate(lector, 2):
            if None in fila or any(v is None for v in fila.values()):
                raise ValueError(f"CSV irregular en {ruta.name}, fila física {num}")
            resultado.append(fila)
        return resultado


def escribir_csv(ruta: Path, columnas: list[str], filas: list[dict]) -> None:
    with ruta.open("w", encoding="utf-8-sig", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=columnas, delimiter=";", extrasaction="ignore")
        escritor.writeheader()
        escritor.writerows(filas)


def normalizar_texto(texto: str) -> str:
    """Solo normaliza espacios y caracteres de control, NO lematiza ni traduce."""
    return re.sub(r"\s+", " ", texto).strip()


def cargar_json_lista(valor: str, contexto: str) -> list[str]:
    try:
        resultado = json.loads(valor)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Lista JSON no válida en {contexto}: {exc}") from exc
    if not isinstance(resultado, list) or any(not isinstance(x, str) for x in resultado):
        raise ValueError(f"Se esperaba lista JSON de strings en {contexto}")
    return resultado


def sha256(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def producir(seleccion: Path, datos: Path, salida: Path) -> dict:
    ruta_resumen = seleccion / "02_resumen_seleccion.json"
    resumen2 = json.loads(ruta_resumen.read_text(encoding="utf-8-sig"))
    huellas = resumen2.get("fuentes_sha256", {})
    for archivo in FUENTES:
        ruta = datos / archivo
        if not ruta.is_file():
            raise FileNotFoundError(f"Para comprobar procedencia falta el original: {ruta}")
        if sha256(ruta) != huellas.get(archivo):
            raise ValueError(
                f"Cambió '{archivo}' desde el paso 2. Vuelve a ejecutar los pasos 1 y 2; "
                "no reutilices resultados anteriores con datos distintos."
            )

    elegibles = leer_csv(seleccion / "02_elegibles_provisionales.csv")
    auditoria = leer_csv(seleccion / "02_competencias_para_auditar.csv")
    inventario = leer_csv(seleccion / "02_inventario_y_prioridades.csv")
    if not elegibles or not auditoria or not inventario:
        raise ValueError("Las entradas del paso 2 están vacías")
    if len(elegibles) != int(resumen2["totales"]["elegibles_provisionales"]):
        raise ValueError("El número de elegibles no coincide con el resumen del paso 2")
    if len(auditoria) != int(resumen2["totales"]["competencias_asignadas_filas"]):
        raise ValueError("El número de asignaciones no coincide con el resumen del paso 2")
    if len(inventario) != int(resumen2["totales"]["registros_originales"]):
        raise ValueError("El inventario no coincide con el resumen del paso 2")

    def clave(fila: dict[str, str]) -> tuple[str, int, str]:
        try:
            return fila["origen"], int(fila["fila_csv"]), fila["id_registro"]
        except (KeyError, ValueError) as exc:
            raise ValueError(f"Identificador inválido: {fila}") from exc

    # Comprobar que cada elegible corresponde al inventario y no hay claves duplicadas.
    mapa_inventario = {}
    for fila in inventario:
        k = clave(fila)
        if k in mapa_inventario:
            raise ValueError(f"Clave repetida en inventario: {k}")
        mapa_inventario[k] = fila
    registros = []
    mapa_esperado = {}
    for fila in elegibles:
        k = clave(fila)
        if k in mapa_esperado:
            raise ValueError(f"Registro elegible duplicado: {k}")
        iv = mapa_inventario.get(k)
        if iv is None or iv["elegible_vectorizacion_provisional"] != "SI":
            raise ValueError(f"Elegibilidad incompatible con inventario: {k}")
        uris = cargar_json_lista(fila["uris_esco_json"], f"URIs {k}")
        etiquetas = cargar_json_lista(fila["etiquetas_esco_json"], f"etiquetas {k}")
        if not uris or len(uris) != len(etiquetas) or len(set(uris)) != len(uris):
            raise ValueError(f"URI/etiquetas vacías, diferentes o repetidas en: {k}")
        if len(uris) != int(fila["n_competencias_esco"]) or len(uris) != int(iv["n_competencias_esco"]):
            raise ValueError(f"Cantidad incoherente para {k}")
        if any(not u.strip().startswith("http") for u in uris):
            raise ValueError(f"URI inválida en {k}")
        limpias = [normalizar_texto(x) for x in etiquetas]
        if any(not x for x in limpias):
            raise ValueError(f"Etiqueta vacía en {k}")
        mapa_esperado[k] = list(zip(uris, etiquetas))
        registros.append({
            "origen": k[0], "fila_csv": k[1], "id_registro": k[2],
            "universidad": fila.get("universidad", ""), "carrera": fila.get("carrera", ""),
            "job_id": fila.get("job_id", ""), "titulo_oferta": fila.get("titulo_oferta", ""),
            "n_competencias_esco": len(uris),
            "uris_esco_json": json.dumps(uris, ensure_ascii=False),
            "etiquetas_esco_json": json.dumps(limpias, ensure_ascii=False),
            # Diagnóstico legible, NO entrada recomendada para el futuro encoder.
            "texto_concatenado_diagnostico": " ; ".join(limpias),
            "estado_revision": fila["estado_revision"],
            "elegibilidad": "PROVISIONAL_NO_VALIDADA_SEMANTICAMENTE",
            "representacion_recomendada": "EMBEDDING_POR_URI_Y_AGREGACION_POSTERIOR",
        })
    keys_iv_elegibles = {k for k, r in mapa_inventario.items()
                         if r["elegible_vectorizacion_provisional"] == "SI"}
    if keys_iv_elegibles != set(mapa_esperado):
        raise ValueError("Faltan o sobran registros respecto al inventario del paso 2")

    # Reconstruir relación ordenada de asignaciones, contrastando línea por línea
    # la fuente auditada con las listas de competencias de cada registro.
    asignaciones: dict[tuple[str, int, str], dict[int, dict]] = defaultdict(dict)
    etiquetas_por_uri: dict[str, set[str]] = defaultdict(set)
    uso_por_uri: dict[str, Counter] = defaultdict(Counter)
    for fila in auditoria:
        k = clave(fila)
        if k not in mapa_esperado:
            raise ValueError(f"Asignación huérfana (no elegible): {k}")
        try:
            pos = int(fila["posicion"])
        except ValueError as exc:
            raise ValueError(f"Posición inválida en {k}") from exc
        esperado = mapa_esperado[k]
        if pos < 1 or pos > len(esperado) or pos in asignaciones[k]:
            raise ValueError(f"Posición inexistente o repetida: {k}, {pos}")
        uri = fila["uri_esco"]
        etiqueta = fila["etiqueta_esco"]
        if (uri, etiqueta) != esperado[pos - 1]:
            raise ValueError(f"URI/etiqueta no coincide con selección: {k}, {pos}")
        if fila["estado_revision_registro"] != mapa_inventario[k]["estado_revision"]:
            raise ValueError(f"Estado de revisión inconsistente: {k}")
        limpio = normalizar_texto(etiqueta)
        asignaciones[k][pos] = {
            "origen": k[0], "fila_csv": k[1], "id_registro": k[2], "posicion": pos,
            "uri_esco": uri, "etiqueta_esco": etiqueta,
            "texto_para_embedding": limpio,
            "evidencia_original": fila.get("evidencia_original", ""),
            "estado_revision_registro": fila["estado_revision_registro"],
        }
        etiquetas_por_uri[uri].add(limpio)
        uso_por_uri[uri][k[0]] += 1
    for k, esperado in mapa_esperado.items():
        if set(asignaciones[k]) != set(range(1, len(esperado) + 1)):
            raise ValueError(f"Faltan posiciones ESCO para {k}")

    # Para reproducibilidad, no escoger silenciosamente una etiqueta
    # si la misma URI tiene dos textos distintos.
    inconsistentes = {u: vals for u, vals in etiquetas_por_uri.items() if len(vals) > 1}
    if inconsistentes:
        ejemplos = list(inconsistentes.items())[:3]
        raise ValueError(f"Una URI tiene etiquetas diferentes: {ejemplos}. Revisar antes de vectorizar")

    catalogo = []
    etiquetas_a_uris: dict[str, set[str]] = defaultdict(set)
    for uri in sorted(etiquetas_por_uri):
        etiqueta = next(iter(etiquetas_por_uri[uri]))
        etiquetas_a_uris[etiqueta.casefold()].add(uri)
        usos = uso_por_uri[uri]
        catalogo.append({
            "uri_esco": uri, "etiqueta_esco": etiqueta,
            "texto_para_embedding": etiqueta,
            "asignaciones": sum(usos.values()),
            "registros_academia": usos["academia"], "registros_mercado": usos["mercado"],
            "requiere_revision_semantica": "SI",
        })

    alertas = []
    for etiqueta, uris in sorted(etiquetas_a_uris.items()):
        if len(uris) > 1:
            alertas.append({
                "tipo": "ETIQUETA_COMPARTIDA_POR_VARIAS_URI",
                "valor": etiqueta,
                "uris_esco_json": json.dumps(sorted(uris), ensure_ascii=False),
                "detalle": "Mantener URI distintas; el texto puede producir vectores idénticos",
            })

    relaciones = [asignaciones[k][pos] for k in sorted(asignaciones)
                  for pos in sorted(asignaciones[k])]
    if len(relaciones) != sum(int(r["n_competencias_esco"]) for r in registros):
        raise ValueError("Falta alguna relación registro-competencia")
    conteos_origen = Counter(r["origen"] for r in registros)
    totales = resumen2["conteos"]
    if any(conteos_origen[o] != totales[o]["elegibles_provisionales"] for o in ("academia", "mercado")):
        raise ValueError("Los totales por origen no coinciden con el paso 2")

    salida.mkdir(parents=True, exist_ok=True)
    escribir_csv(salida / "03_catalogo_competencias_esco.csv", COL_CON, catalogo)
    escribir_csv(salida / "03_registros_preparados.csv", COL_REG, registros)
    escribir_csv(salida / "03_relaciones_trazables.csv", COL_LINK, relaciones)
    escribir_csv(salida / "03_alertas_representacion.csv", COL_ALERT, alertas)

    uri_a_origen = {u: {o for o in ("academia", "mercado") if uso_por_uri[u][o]}
                    for u in etiquetas_por_uri}
    resumen3 = {
        "etapa": "Obj2 / Actividad 3 / Etapa 1 / Paso 3",
        "estado": "PREPARACION_TEXTUAL_PROVISIONAL_NO_VALIDADA_SEMANTICAMENTE",
        "fuentes_sha256_verificadas": True,
        "fuentes_sha256": huellas,
        "insumos_paso2_sha256": {
            f: sha256(seleccion / f) for f in (
                "02_resumen_seleccion.json", "02_inventario_y_prioridades.csv",
                "02_elegibles_provisionales.csv", "02_competencias_para_auditar.csv")
        },
        "conteos": {
            "registros_academia": conteos_origen["academia"],
            "registros_mercado": conteos_origen["mercado"],
            "registros_totales_preparados": len(registros),
            "ofertas_sin_esco_no_incluidas": totales["mercado"]["sin_esco_no_vectorizables"],
            "asignaciones_registro_competencia": len(relaciones),
            "competencias_uris_unicas": len(catalogo),
            "uris_solo_academia": sum(x == {"academia"} for x in uri_a_origen.values()),
            "uris_solo_mercado": sum(x == {"mercado"} for x in uri_a_origen.values()),
            "uris_compartidas": sum(len(x) == 2 for x in uri_a_origen.values()),
            "uri_con_etiquetas_distintas": len(inconsistentes),
            "etiquetas_con_varias_uri": len(alertas),
        },
        "decision_textual": "Usar la etiqueta ESCO de cada URI como texto del futuro encoder; "
                            "agregar vectores por registro en paso posterior, sin mezclar evidencias",
        "normalizacion_textual": "Solo blancos consecutivos -> un espacio; sin lowercasing, lematización ni traducción",
        "nota": "La igualdad de nombres no implica igualdad de URI. Ninguna asignación ha sido aprobada semánticamente.",
    }
    (salida / "03_resumen_corpus.json").write_text(
        json.dumps(resumen3, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return resumen3


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    raiz = Path(__file__).resolve().parent
    parser.add_argument("--seleccion", type=Path, default=raiz / "salida_seleccion")
    parser.add_argument("--datos", type=Path, default=raiz.parent / "Act. 1")
    parser.add_argument("--salida", type=Path, default=raiz / "salida_textos")
    args = parser.parse_args()
    try:
        resumen = producir(args.seleccion, args.datos, args.salida)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        print("\nEn VS Code, verifica que este .py esté en Obj2/Act. 3/", file=sys.stderr)
        print("y que ahí exista salida_seleccion/ del paso 2; los CSV originales", file=sys.stderr)
        print("deben seguir en Obj2/Act. 1/.", file=sys.stderr)
        return 2
    print(json.dumps(resumen, ensure_ascii=False, indent=2))
    print(f"\nArchivos generados en: {args.salida.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
