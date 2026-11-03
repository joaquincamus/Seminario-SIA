import hashlib
import json
import logging
import os
import re
import time
import urllib.parse
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

from seleniumbase import SB

# CONFIGURACIÓN GENERAL Y RUTAS

RUTA_BRAVE: str = r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"
OUTPUT_FILE: str = "dataset_consolidado_mineria.json"
META_OFERTAS_POR_QUERY: int = 75
INCREMENTAL_SAVE_INTERVAL: int = 10
FECHA_CORTE_MINIMA: date = date(2024, 9, 1)  # Septiembre 2024

DICCIONARIO_PRUEBAS: Dict[int, Dict[str, str]] = {
    1: {
        "name": "query_01_trainee_junior",
        "query": '("Ingeniero Trainee" OR "Ingeniera Trainee" OR "Ingeniero Junior" OR "Ingeniero Graduado" OR "Programa Graduados") AND (Minería OR Minera)'
    },
    2: {
        "name": "query_02_gestion_control",
        "query": '("Control de Gestión" OR "Ingeniero de Gestión" OR "Ingeniero Industrial" OR "Analista de Gestión") AND (Minería OR Minera)'
    },
    3: {
        "name": "query_03_procesos_operaciones",
        "query": '("Ingeniero de Procesos" OR "Ingeniero de Optimización" OR "Ingeniero de Operaciones" OR "Mejora Continua") AND (Minería OR Minera)'
    },
    4: {
        "name": "query_04_analitica_planificacion",
        "query": '("Analista de Datos" OR "Ingeniero de Planificación" OR "Analytics Engineer" OR "Business Intelligence") AND (Minería OR Minera)'
    },
    5: {
        "name": "query_05_proyectos_estudios",
        "query": '("Ingeniero de Proyectos" OR "Ingeniero de Estudios" OR "Ingeniero Oficina Técnica") AND (Minería OR Minera)'
    }
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)


# ==============================================================================
# UTILIDADES: NORMALIZACIÓN Y PARSEO DE FECHAS
# ==============================================================================
class DateParser:
    """Parsea representaciones relativas y absolutas de fecha en LinkedIn (ES)."""

    @staticmethod
    def parse_linkedin_date(raw_text: str, datetime_attr: Optional[str] = None) -> Optional[date]:
        """
        Calcula la fecha estimada resolviendo el atributo datetime ISO
        o calculando el delta a partir de expresiones relativas en español.
        """
        if datetime_attr:
            try:
                clean_iso = datetime_attr.strip().split("T")[0]
                return datetime.strptime(clean_iso, "%Y-%m-%d").date()
            except (ValueError, TypeError):
                pass

        if not raw_text or not isinstance(raw_text, str):
            return None

        texto: str = raw_text.strip().lower()
        hoy: date = date.today()

        if any(w in texto for w in ["segundo", "minuto", "hora", "ahora", "instante"]):
            return hoy

        match_numero = re.search(r"hace\s+(\d+)\s*(día|dia|semana|mes|año)", texto)
        if match_numero:
            cantidad: int = int(match_numero.group(1))
            unidad: str = match_numero.group(2)

            if "día" in unidad or "dia" in unidad:
                return hoy - timedelta(days=cantidad)
            elif "semana" in unidad:
                return hoy - timedelta(weeks=cantidad)
            elif "mes" in unidad:
                return hoy - timedelta(days=cantidad * 30)
            elif "año" in unidad:
                return hoy - timedelta(days=cantidad * 365)

        match_singular = re.search(r"hace\s+(un|una|1)\s*(día|dia|semana|mes|año)", texto)
        if match_singular:
            unidad = match_singular.group(2)
            if "día" in unidad or "dia" in unidad:
                return hoy - timedelta(days=1)
            elif "semana" in unidad:
                return hoy - timedelta(weeks=1)
            elif "mes" in unidad:
                return hoy - timedelta(days=30)
            elif "año" in unidad:
                return hoy - timedelta(days=365)

        return None


# ==============================================================================
# GESTIÓN DE DATOS Y PERSISTENCIA RESILIENTE
# ==============================================================================
class DatasetManager:
    """Maneja el estado en memoria, la deduplicación y el guardado incremental."""

    def __init__(self, filepath: str):
        self.filepath: str = filepath
        self.ofertas_por_url: Dict[str, Dict[str, Any]] = {}
        self.descartadas_antiguedad: int = 0
        self.descartadas_error: int = 0
        self.nuevas_extracciones_contador: int = 0

        self._cargar_archivo_existente()

    @staticmethod
    def generar_job_id(url_base: str) -> str:
        """Genera un hash determinista a partir de la URL base limpia."""
        return hashlib.sha256(url_base.strip().lower().encode("utf-8")).hexdigest()[:16]

    def _cargar_archivo_existente(self) -> None:
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data.get("ofertas", []):
                        self.ofertas_por_url[item["url_base"]] = item
                logging.info(f"Reanudación: Se cargaron {len(self.ofertas_por_url)} ofertas previas de '{self.filepath}'.")
            except Exception as e:
                logging.warning(f"No se pudo cargar el archivo preexistente ({e}). Iniciando base limpia.")

    def existe_url(self, url_base: str) -> bool:
        return url_base in self.ofertas_por_url

    def asociar_query_a_existente(self, url_base: str, query_id: str) -> None:
        """Asocia la query actual a una oferta ya raspada sin volver a navegar."""
        if query_id not in self.ofertas_por_url[url_base]["queries_origen"]:
            self.ofertas_por_url[url_base]["queries_origen"].append(query_id)
            logging.info(f"[SOLAPAMIENTO] Oferta ya extraída. Se vinculó query '{query_id}' -> ID {self.ofertas_por_url[url_base]['job_id']}")

    def registrar_oferta(self, registro: Dict[str, Any]) -> None:
        self.ofertas_por_url[registro["url_base"]] = registro
        self.nuevas_extracciones_contador += 1

        if self.nuevas_extracciones_contador % INCREMENTAL_SAVE_INTERVAL == 0:
            logging.info(f"Checkpoint automático ({self.nuevas_extracciones_contador} nuevas). Guardando...")
            self.persistir_disco()

    def calcular_matriz_solapamiento(self) -> Dict[str, Any]:
        """Calcula métricas de solapamiento entre las consultas de origen."""
        distribucion_solapamiento: Dict[int, int] = {}
        concurrencia_por_query: Dict[str, int] = {}

        for oferta in self.ofertas_por_url.values():
            n_queries = len(oferta["queries_origen"])
            distribucion_solapamiento[n_queries] = distribucion_solapamiento.get(n_queries, 0) + 1

            for q in oferta["queries_origen"]:
                concurrencia_por_query[q] = concurrencia_por_query.get(q, 0) + 1

        return {
            "total_ofertas_unicas_persistidas": len(self.ofertas_por_url),
            "desglose_por_cantidad_de_queries": {
                f"presente_en_{k}_queries": v for k, v in sorted(distribucion_solapamiento.items())
            },
            "ofertas_totales_detectadas_por_query": concurrencia_por_query
        }

    def persistir_disco(self) -> None:
        """Sobrescribe de forma atómica y segura el archivo JSON maestro."""
        payload = {
            "metadata": {
                "fecha_actualizacion": datetime.now().isoformat(),
                "estadisticas_globales": {
                    "total_unicas": len(self.ofertas_por_url),
                    "descartadas_por_antiguedad": self.descartadas_antiguedad,
                    "descartadas_por_error_dom": self.descartadas_error
                },
                "analisis_solapamiento": self.calcular_matriz_solapamiento()
            },
            "ofertas": list(self.ofertas_por_url.values())
        }

        temp_file = f"{self.filepath}.tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        os.replace(temp_file, self.filepath)
        logging.info(f"Sincronización exitosa en '{self.filepath}'.")


# ==============================================================================
# PIPELINE PRINCIPAL DE SCRAPING
# ==============================================================================
def ejecutar_pipeline_mineria() -> None:
    dataset = DatasetManager(filepath=OUTPUT_FILE)

    with SB(uc=True, test=True, locale_code="es", binary_location=RUTA_BRAVE) as sb:
        for idx_query, cfg in DICCIONARIO_PRUEBAS.items():
            query_id: str = cfg["name"]
            query_str: str = cfg["query"]
            query_encoded: str = urllib.parse.quote(query_str)
            search_url: str = f"https://cl.linkedin.com/jobs/search?keywords={query_encoded}&location=Chile"

            logging.info("=" * 70)
            logging.info(f"INICIANDO ITERACIÓN [{idx_query}/5]: {query_id}")
            logging.info(f"Target URL: {search_url}")
            logging.info("=" * 70)

            sb.open(search_url)
            time.sleep(3)

            if sb.is_element_visible('button[action-type="ACCEPT"]'):
                sb.click('button[action-type="ACCEPT"]')
                time.sleep(1)

            # ------------------------------------------------------------------
            # 1. BÚSQUEDA Y COLECTA DE ENLACES (SCROLL INFINITO)
            # ------------------------------------------------------------------
            urls_candidatas_query: Set[str] = set()
            scroll_attempts: int = 0
            max_scroll_attempts: int = 25  # Ampliado para cubrir la meta de 75
            colchon_seguridad: int = META_OFERTAS_POR_QUERY + 35  # Meta: 110 candidatos

            while len(urls_candidatas_query) < colchon_seguridad and scroll_attempts < max_scroll_attempts:
                sb.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)

                if sb.is_element_visible("button.infinite-scroller__show-more-button--visible"):
                    try:
                        sb.click("button.infinite-scroller__show-more-button--visible")
                        time.sleep(2)
                    except Exception:
                        pass

                elements = sb.find_elements("a.base-card__full-link")
                for elem in elements:
                    href = elem.get_attribute("href")
                    if href:
                        urls_candidatas_query.add(href.split("?")[0])

                scroll_attempts += 1
                logging.info(f"[{query_id}] Scroll {scroll_attempts}/{max_scroll_attempts} - Candidatas únicas: {len(urls_candidatas_query)}")

            # ------------------------------------------------------------------
            # 2. PROCESAMIENTO, DEDUPLICACIÓN Y FILTRO TEMPORAL
            # ------------------------------------------------------------------
            ofertas_procesadas_esta_query: int = 0

            for url_base in urls_candidatas_query:
                if ofertas_procesadas_esta_query >= META_OFERTAS_POR_QUERY:
                    logging.info(f"Meta alcanzada ({META_OFERTAS_POR_QUERY} ofertas) para {query_id}.")
                    break

                # Deduplicación global en memoria previa a la navegación
                if dataset.existe_url(url_base):
                    dataset.asociar_query_a_existente(url_base, query_id)
                    ofertas_procesadas_esta_query += 1
                    continue

                try:
                    sb.open(url_base)
                    time.sleep(2.5)

                    if sb.is_element_visible("button.show-more-less-html__button"):
                        try:
                            sb.click("button.show-more-less-html__button")
                            time.sleep(0.5)
                        except Exception:
                            pass

                    if not sb.is_element_visible("div.show-more-less-html__markup"):
                        dataset.descartadas_error += 1
                        logging.warning(f"Markup ausente en {url_base}. Descartada.")
                        continue

                    titulo: str = sb.get_text("h1.top-card-layout__title") if sb.is_element_visible("h1.top-card-layout__title") else "Sin Título"
                    empresa: str = sb.get_text("a.topcard__org-name-link") if sb.is_element_visible("a.topcard__org-name-link") else "Sin Empresa"
                    ubicacion: str = sb.get_text("span.topcard__flavor--bullet") if sb.is_element_visible("span.topcard__flavor--bullet") else "Chile"
                    texto_bruto: str = sb.get_text("div.show-more-less-html__markup")

                    fecha_declarada: str = "No especificada"
                    datetime_attr: Optional[str] = None

                    if sb.is_element_visible("span.posted-time-ago__text"):
                        fecha_declarada = sb.get_text("span.posted-time-ago__text")
                    elif sb.is_element_visible("time"):
                        fecha_declarada = sb.get_text("time")
                        datetime_attr = sb.get_attribute("time", "datetime")

                    fecha_estimada: Optional[date] = DateParser.parse_linkedin_date(
                        raw_text=fecha_declarada,
                        datetime_attr=datetime_attr
                    )

                    # Filtro temporal estricto (>= Septiembre 2024)
                    if fecha_estimada is not None and fecha_estimada < FECHA_CORTE_MINIMA:
                        dataset.descartadas_antiguedad += 1
                        logging.info(f"[DESCARTE FECHA] {fecha_estimada.isoformat()} anterior a corte ({FECHA_CORTE_MINIMA}). Cargo: '{titulo[:25]}'")
                        continue

                    fecha_iso_str: str = fecha_estimada.isoformat() if fecha_estimada else "DESCONOCIDA"

                    registro_oferta: Dict[str, Any] = {
                        "job_id": dataset.generar_job_id(url_base),
                        "url_base": url_base,
                        "queries_origen": [query_id],
                        "titulo": titulo.strip(),
                        "empresa": empresa.strip(),
                        "ubicacion": ubicacion.strip(),
                        "fecha_declarada": fecha_declarada.strip(),
                        "fecha_estimada_iso": fecha_iso_str,
                        "texto_bruto": texto_bruto.strip()
                    }

                    dataset.registrar_oferta(registro_oferta)
                    ofertas_procesadas_esta_query += 1
                    logging.info(f"[{ofertas_procesadas_esta_query}/{META_OFERTAS_POR_QUERY}] Éxito ({query_id}): {titulo[:30]} | {empresa[:20]}")

                except Exception as ex:
                    dataset.descartadas_error += 1
                    logging.error(f"Fallo inesperado al procesar URL {url_base}: {ex}")

            # Persistencia forzada al terminar cada consulta
            dataset.persistir_disco()

    # --------------------------------------------------------------------------
    # RESUMEN DE EJECUCIÓN
    # --------------------------------------------------------------------------
    stats = dataset.calcular_matriz_solapamiento()
    print("\n" + "=" * 65)
    print("RESUMEN DE EXTRACCIÓN (ITERACIÓN V2)")
    print("=" * 65)
    print(f"Total de vacantes únicas consolidadas : {stats['total_ofertas_unicas_persistidas']}")
    print(f"Descartes por antigüedad (< Sep 2024)  : {dataset.descartadas_antiguedad}")
    print(f"Descartes por error de carga / DOM     : {dataset.descartadas_error}")
    print("\nMatriz de Distribución de Solapamiento:")
    for k, v in stats["desglose_por_cantidad_de_queries"].items():
        print(f"  * {k}: {v} vacantes")
    print("\nVolumen de detección por Query:")
    for q_name, total in stats["ofertas_totales_detectadas_por_query"].items():
        print(f"  * {q_name}: {total} menciones")
    print(f"\nArchivo generado: {OUTPUT_FILE}")
    print("=" * 65)


if __name__ == "__main__":
    ejecutar_pipeline_mineria()