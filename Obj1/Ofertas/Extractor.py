import csv
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from groq import APIError, Groq, RateLimitError

# ==============================================================================
# CONFIGURACIÓN DE ENTORNO Y RUTAS
# ==============================================================================
load_dotenv()

BASE_DIR = Path(r"C:\Users\dilan\OneDrive\Escritorio\Resultados Tesis\Ofertas\Codigos Scraper\Prueba 2")
BASE_DIR.mkdir(parents=True, exist_ok=True)

INPUT_DATASET_PATH: str = str(BASE_DIR / "dataset_consolidado_mineria.json")
CHECKPOINT_PATH: str = str(BASE_DIR / ".checkpoint_evaluacion.json")
OUTPUT_CSV_PATH: str = str(BASE_DIR / "resumen_clasificacion.csv")
OUTPUT_JSON_PATH: str = str(BASE_DIR / "dataset_competencias_clasificado.json")
ERROR_LOG_PATH: str = str(BASE_DIR / "vacantes_no_procesadas.log")

MODEL_NAME: str = "qwen/qwen3.8-27b"
BASE_TEMPERATURE: float = 0.0
MAX_OUTPUT_TOKENS: int = 800
MAX_INPUT_CHAR_LIMIT: int = 8000
CHECKPOINT_INTERVAL: int = 5
PACING_SLEEP_BETWEEN_CALLS: float = 2.5
COOLDOWN_SLEEP_ALL_KEYS_EXHAUSTED: float = 35.0

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)

# ==============================================================================
# GESTOR DE ROTACIÓN DE API KEYS
# ==============================================================================
class KeyPoolManager:
    """Administra la rotación activa y pasiva entre múltiples credenciales de Groq."""

    def __init__(self):
        self.keys: List[str] = []
        for env_var in ["GROQ_API_KEY_1", "GROQ_API_KEY_2", "GROQ_API_KEY_3", "GROQ_API_KEY"]:
            val = os.getenv(env_var)
            if val and val.strip() and val not in self.keys:
                self.keys.append(val.strip())

        if not self.keys:
            raise ValueError(
                "No se encontraron claves de API válidas en .env (GROQ_API_KEY_1, GROQ_API_KEY_2, GROQ_API_KEY_3)."
            )

        self.current_index: int = 0
        logging.info(f"Pool de API Keys inicializado con {len(self.keys)} clave(s) activa(s).")

    def get_current_client(self) -> Groq:
        return Groq(api_key=self.keys[self.current_index])

    def rotate_key(self) -> None:
        prev = self.current_index
        self.current_index = (self.current_index + 1) % len(self.keys)
        logging.warning(
            f"[ROTACIÓN API] Alternando cliente: Clave #{prev + 1} -> Clave #{self.current_index + 1}."
        )

    def total_keys(self) -> int:
        return len(self.keys)


# ==============================================================================
# SYSTEM PROMPT CON VALIDACIÓN SINTÁCTICA ESTRICTA
# ==============================================================================
SYSTEM_PROMPT = """Actúa como Evaluador Metodológico y Analista de Mercado Laboral para Ingeniería y Minería en Chile.

Tu labor consta de tres etapas metodológicas:

1. EVALUACIÓN DISCIPLINAR ('es_ingenieria_valida'):
   Evalúa si el cargo corresponde a una carrera profesional universitaria válida según el catálogo oficial de la Región de Coquimbo y macrozona norte.

   CATÁLOGO DE DISCIPLINAS VÁLIDAS ('es_ingenieria_valida': true):
   a) Carreras Universitarias Regionales (Región de Coquimbo):
      - INGENIERÍA CIVIL (Plan común, Estructural u Obras Civiles)
      - INGENIERÍA CIVIL AMBIENTAL
      - INGENIERÍA CIVIL DE MINAS / INGENIERÍA CIVIL EN MINAS / INGENIERÍA DE MINAS / INGENIERÍA EN MINAS
      - INGENIERÍA CIVIL EN COMPUTACIÓN E INFORMÁTICA / INGENIERÍA EN INFORMÁTICA / INGENIERÍA EN TECNOLOGÍAS DE INFORMACIÓN / INGENIERÍA CIVIL INFORMÁTICA Y SISTEMAS INTELIGENTES
      - INGENIERÍA CIVIL INDUSTRIAL / INGENIERÍA INDUSTRIAL
      - INGENIERÍA CIVIL MECÁNICA / INGENIERÍA MECÁNICA / INGENIERÍA EN MANTENIMIENTO INDUSTRIAL
      - INGENIERÍA CIVIL METALÚRGICA / INGENIERÍA METALÚRGICA / INGENIERÍA DE PROCESOS
      - INGENIERÍA CIVIL HIDRÁULICA / RECURSOS HÍDRICOS
      - INGENIERÍA CIVIL QUÍMICA / INGENIERÍA EN QUÍMICA INDUSTRIAL
      - INGENIERÍA COMERCIAL
      - INGENIERÍA ELÉCTRICA / INGENIERÍA EN ELECTRICIDAD Y ELECTRÓNICA INDUSTRIAL / AUTOMATIZACIÓN Y CONTROL
      - INGENIERÍA EN ADMINISTRACIÓN DE EMPRESAS / INGENIERÍA EN LOGÍSTICA
      - INGENIERÍA EN BIOTECNOLOGÍA MENCIÓN ALIMENTOS O PROCESOS SUSTENTABLES
      - INGENIERÍA EN CIBERSEGURIDAD / TELECOMUNICACIONES Y SERVICIOS DIGITALES
      - INGENIERÍA EN ENERGÍA

   b) Información, Control de Gestión y Analítica de Negocio (Minería 4.0):
      - INGENIERÍA EN INFORMACIÓN Y CONTROL DE GESTIÓN
      - Cargos profesionales de datos y planificación: Business Planning, Business Intelligence (BI), Data Engineering, Analytics Engineer, Analista de Datos/BI aplicados a la toma de decisiones mineras o industriales.

   c) Geociencias y Caracterización Espacial Minera:
      - INGENIERÍA EN GEOMENSURA Y GEOMÁTICA
      - GEOLOGÍA (Geología de mina, Geología económica, Geología estructural)
      - GEOTECNIA Y GEOMETALURGIA aplicadas a procesos mineros.

   d) Seguridad, Salud Ocupacional y Medio Ambiente:
      - INGENIERÍA EN PREVENCIÓN DE RIESGOS Y MEDIOAMBIENTE / INGENIERÍA EN MEDIOAMBIENTE Y SUSTENTABILIDAD / INGENIERÍA HSE profesional.

   CARGOS INVÁLIDOS ('es_ingenieria_valida': false):
   - Únicamente oficios de terreno no profesionales: operador de camión de extracción (CAEX), operador de pala/grúa, perforista, soldador, electromecánico de taller de oficio, mantenedor mecánico de nivel medio, ayudante de patio o administrativos básicos (secretaría, recepcionista, digitador).

2. CLASIFICACIÓN DE TRAYECTORIA ('categoria_trayectoria'):
   - 'PRACTICA_MEMORIA': Prácticas profesionales, memorias de título, tesis o convocatorias para estudiantes universitarios en curso.
   - 'JUNIOR_TRAINEE': Recién egresados, ingenieros trainee, graduados, o roles con <= 2 años de experiencia profesional requerida (o donde mayor experiencia sea solo deseable/valorada).
   - 'SEMI_SENIOR': Exige de forma obligatoria y excluyente entre 2 y 5 años de experiencia profesional.
   - 'SENIOR_LIDERAZGO': Exige más de 5 años de experiencia obligatoria, cargos de jefatura, superintendencias, líderes de proyecto o gerencias.
   - 'NO_APLICA': Únicamente para cargos donde 'es_ingenieria_valida' sea false.

3. EXTRACCIÓN DE COMPETENCIAS TÉCNICAS:
   - Si 'es_ingenieria_valida' == true: Extrae hasta un MÁXIMO de 10 competencias técnicas clave (herramientas de software, metodologías de gestión, normativas técnicas, análisis cuantitativo y procesos minero-industriales). Aplica a todas las trayectorias.
   - Ignora habilidades blandas genéricas ("puntualidad", "compromiso", "ganas de aprender", "proactividad").
   - 'fragmento_contextual': Cita textual corta de máximo 15 palabras donde se menciona el requisito.
   - 'justificacion': Máximo 20 palabras justificando la inclusión disciplinar y la trayectoria.
   - Si 'es_ingenieria_valida' == false: 'competencias_extraidas' debe ser una lista vacía [].

REGLA SINTÁCTICA CRÍTICA:
Genera JSON estrictamente válido. Cada elemento del array 'competencias_extraidas' DEBE iniciar obligatoriamente con comillas dobles en la clave "id": {"id": 1, ...}. JAMÁS omitas la comilla inicial (NO generes {id": 1).

ESQUEMA JSON OBLIGATORIO:
{
  "evaluacion_cargo": {
    "es_ingenieria_valida": boolean,
    "disciplina_detectada": string or null,
    "categoria_trayectoria": "PRACTICA_MEMORIA" | "JUNIOR_TRAINEE" | "SEMI_SENIOR" | "SENIOR_LIDERAZGO" | "NO_APLICA",
    "anios_experiencia_detectados": number or null,
    "justificacion": string
  },
  "competencias_extraidas": [
    {
      "id": 1,
      "habilidad_cruda": "string",
      "fragmento_contextual": "string",
      "categoria": "Herramienta/Software" | "Conocimiento Técnico" | "Gestión/Metodología"
    }
  ]
}
"""


# ==============================================================================
# EVALUADOR DE VACANTES CON DESESTABILIZACIÓN TÉRMICA ANTE ERRORES 400
# ==============================================================================
class GroqJobEvaluatorV4:
    """Ejecutor de inferencia con mitigación dinámica de errores sintácticos."""

    def __init__(self, key_manager: KeyPoolManager, model: str):
        self.key_manager: KeyPoolManager = key_manager
        self.model: str = model

    def evaluate_job(self, titulo: str, empresa: str, texto_bruto: str) -> Dict[str, Any]:
        texto_sanitizado = texto_bruto[:MAX_INPUT_CHAR_LIMIT] if len(texto_bruto) > MAX_INPUT_CHAR_LIMIT else texto_bruto
        user_content = f"TÍTULO: {titulo}\nEMPRESA: {empresa}\n\nDESCRIPCIÓN DE LA VACANTE:\n{texto_sanitizado}"

        intentos_totales = 0
        max_intentos = self.key_manager.total_keys() * 2
        temperatura_actual = BASE_TEMPERATURE

        while intentos_totales < max_intentos:
            client = self.key_manager.get_current_client()
            try:
                response = client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_content}
                    ],
                    temperature=temperatura_actual,
                    max_tokens=MAX_OUTPUT_TOKENS,
                    response_format={"type": "json_object"}
                )

                content = response.choices[0].message.content
                parsed_json = json.loads(content)

                if "evaluacion_cargo" not in parsed_json or "competencias_extraidas" not in parsed_json:
                    raise ValueError("El JSON generado carece de las llaves raíz estructurales.")

                return parsed_json

            except RateLimitError as e:
                logging.warning(f"[RateLimit 429 en Clave #{self.key_manager.current_index + 1}]: {e}")
                self.key_manager.rotate_key()
                intentos_totales += 1

                if intentos_totales % self.key_manager.total_keys() == 0:
                    logging.warning(
                        f"Todas las API keys alcanzaron cuota de ventana. "
                        f"Pausando {COOLDOWN_SLEEP_ALL_KEYS_EXHAUSTED}s de enfriamiento pasivo..."
                    )
                    time.sleep(COOLDOWN_SLEEP_ALL_KEYS_EXHAUSTED)

            except (APIError, json.JSONDecodeError, ValueError) as ex:
                error_str = str(ex)
                intentos_totales += 1

                # Si el error es de sintaxis JSON de Groq, rompemos el determinismo del token malformado
                if "json_validate_failed" in error_str or "Failed to generate JSON" in error_str:
                    temperatura_actual = min(0.3, temperatura_actual + 0.15)
                    logging.warning(
                        f"[Sintaxis 400 detectada en Clave #{self.key_manager.current_index + 1}]. "
                        f"Ajustando temperatura a {temperatura_actual:.2f} para recalcular probabilidades de tokens..."
                    )
                    # Forzamos rotación de clave para cambiar el contexto de sesión
                    self.key_manager.rotate_key()
                else:
                    logging.warning(f"[Fallo transitorio en Clave #{self.key_manager.current_index + 1}]: {ex}")

                time.sleep(3.0)
                if intentos_totales >= max_intentos:
                    raise ex

        raise RuntimeError(f"Agotados {max_intentos} intentos en todas las API Keys sin obtener respuesta válida.")


# ==============================================================================
# PIPELINE Y CONTROL DE CHECKPOINT
# ==============================================================================
class MiningEvaluationPipelineV4:
    """Controla la lectura, checkpointing robusto y exportación de artefactos."""

    def __init__(self, input_path: str, output_csv: str, output_json: str, checkpoint_path: str):
        self.input_path: str = input_path
        self.output_csv: str = output_csv
        self.output_json: str = output_json
        self.checkpoint_path: str = checkpoint_path

        self.key_manager: KeyPoolManager = KeyPoolManager()
        self.evaluator: GroqJobEvaluatorV4 = GroqJobEvaluatorV4(
            key_manager=self.key_manager,
            model=MODEL_NAME
        )
        self.procesadas_por_id: Dict[str, Dict[str, Any]] = {}
        self._cargar_checkpoint()

    def _cargar_checkpoint(self) -> None:
        """Carga el checkpoint filtrando registros corruptos sin fallar por NoneType."""
        if os.path.exists(self.checkpoint_path):
            try:
                with open(self.checkpoint_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    procesadas_crudas = data.get("procesadas", {})

                self.procesadas_por_id = {}
                descartadas_error = 0

                for job_id, item in procesadas_crudas.items():
                    item_str = json.dumps(item, ensure_ascii=False)
                    if "Error 400" in item_str or "Error persistente" in item_str:
                        descartadas_error += 1
                        continue
                    self.procesadas_por_id[job_id] = item

                logging.info(
                    f"Reanudación exitosa: {len(self.procesadas_por_id)} vacantes válidas cargadas desde el checkpoint."
                )
                if descartadas_error > 0:
                    logging.info(f"Se purgaron {descartadas_error} registros con errores antiguos del checkpoint.")

            except Exception as e:
                logging.warning(f"Error al leer checkpoint ({e}). Comenzando desde cero.")

    def persistir_estado(self) -> None:
        """Persiste atómicamente el estado en disco sin incluir ofertas fallidas."""
        temp_checkpoint = f"{self.checkpoint_path}.tmp"
        with open(temp_checkpoint, "w", encoding="utf-8") as f:
            json.dump({"procesadas": self.procesadas_por_id}, f, ensure_ascii=False, indent=2)
        os.replace(temp_checkpoint, self.checkpoint_path)

        self._exportar_csv_consolidado()
        self._exportar_json_ingenieria()

    def _exportar_csv_consolidado(self) -> None:
        fieldnames = [
            "job_id",
            "titulo",
            "empresa",
            "ubicacion",
            "es_ingenieria_valida",
            "disciplina_detectada",
            "categoria_trayectoria",
            "anios_experiencia_detectados",
            "justificacion",
            "total_competencias_extraidas",
            "queries_origen"
        ]

        temp_csv = f"{self.output_csv}.tmp"
        with open(temp_csv, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
            writer.writeheader()

            for item in self.procesadas_por_id.values():
                eval_data = item.get("evaluacion_cargo", {})
                skills = item.get("competencias_extraidas", [])

                anios = eval_data.get("anios_experiencia_detectados")
                anios_str = "N/A" if anios is None else str(anios)

                writer.writerow({
                    "job_id": item.get("job_id"),
                    "titulo": item.get("titulo"),
                    "empresa": item.get("empresa"),
                    "ubicacion": item.get("ubicacion"),
                    "es_ingenieria_valida": "SÍ" if eval_data.get("es_ingenieria_valida") else "NO",
                    "disciplina_detectada": eval_data.get("disciplina_detectada") or "No identificada",
                    "categoria_trayectoria": eval_data.get("categoria_trayectoria") or "NO_APLICA",
                    "anios_experiencia_detectados": anios_str,
                    "justificacion": eval_data.get("justificacion") or "",
                    "total_competencias_extraidas": len(skills),
                    "queries_origen": ", ".join(item.get("queries_origen", []))
                })
        os.replace(temp_csv, self.output_csv)

    def _exportar_json_ingenieria(self) -> None:
        ofertas_ingenieria = [
            oferta for oferta in self.procesadas_por_id.values()
            if oferta.get("evaluacion_cargo", {}).get("es_ingenieria_valida") is True
        ]

        payload = {
            "metadata": {
                "fecha_generacion": datetime.now().isoformat(),
                "modelo_evaluador": MODEL_NAME,
                "total_ofertas_evaluadas": len(self.procesadas_por_id),
                "total_ofertas_ingenieria": len(ofertas_ingenieria)
            },
            "ofertas_ingenieria": ofertas_ingenieria
        }

        temp_json = f"{self.output_json}.tmp"
        with open(temp_json, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(temp_json, self.output_json)

    def run(self) -> None:
        if not os.path.exists(self.input_path):
            raise FileNotFoundError(f"No existe el archivo de entrada: '{self.input_path}'")

        Path(self.output_csv).parent.mkdir(parents=True, exist_ok=True)

        with open(self.input_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        ofertas_raw: List[Dict[str, Any]] = raw_data.get("ofertas", [])
        total_ofertas: int = len(ofertas_raw)
        logging.info(f"Dataset cargado. Total de ofertas a procesar: {total_ofertas}")

        procesadas_en_sesion: int = 0

        for idx, oferta in enumerate(ofertas_raw, start=1):
            job_id = oferta.get("job_id")
            if not job_id:
                continue

            if job_id in self.procesadas_por_id:
                continue

            titulo = oferta.get("titulo", "Sin título")
            empresa = oferta.get("empresa", "Sin empresa")
            texto_bruto = oferta.get("texto_bruto", "")

            logging.info(f"[{idx}/{total_ofertas}] Analizando: {titulo[:35]} | {empresa[:20]}")

            try:
                analisis = self.evaluator.evaluate_job(
                    titulo=titulo,
                    empresa=empresa,
                    texto_bruto=texto_bruto
                )

                registro_completo = {
                    **oferta,
                    "evaluacion_cargo": analisis.get("evaluacion_cargo"),
                    "competencias_extraidas": analisis.get("competencias_extraidas")
                }

                self.procesadas_por_id[job_id] = registro_completo
                procesadas_en_sesion += 1

                eval_c = registro_completo["evaluacion_cargo"]
                es_ing = eval_c["es_ingenieria_valida"]
                trayectoria = eval_c["categoria_trayectoria"]
                n_skills = len(registro_completo.get("competencias_extraidas", []))

                if es_ing:
                    logging.info(f"   -> [INGENIERÍA: {trayectoria}] Competencias extraídas: {n_skills}")
                else:
                    logging.info(f"   -> [DESCARTADO: No Ingeniería] {eval_c['justificacion'][:55]}")

                if procesadas_en_sesion % CHECKPOINT_INTERVAL == 0:
                    self.persistir_estado()
                    logging.info(f"Checkpoint sincronizado ({len(self.procesadas_por_id)}/{total_ofertas}).")

                time.sleep(PACING_SLEEP_BETWEEN_CALLS)

            except RateLimitError as rle:
                # Caso exclusivo: cuota real agotada en todas las cuentas
                logging.error(f"\n[CUOTA EXCEDIDA EN TODAS LAS CLAVES]: {rle}")
                self.persistir_estado()
                print("\a", end="", flush=True)
                logging.error("Límite de API alcanzado en todo el pool. Actualiza las claves en .env y relanza el script.")
                sys.exit(0)

            except Exception as ex:
                # Si falló por formato u otro error tras todos los intentos dinámicos, NO guardamos el registro
                # en el checkpoint para no corromperlo, lo anotamos en el log de incidencias y seguimos adelante.
                logging.error(f"\n[OMISIÓN RESILIENTE] Vacante {job_id} omitida tras agotar reintentos: {ex}")
                with open(ERROR_LOG_PATH, "a", encoding="utf-8") as lf:
                    lf.write(f"{datetime.now().isoformat()} | {job_id} | {titulo} | {ex}\n")
                self.persistir_estado()
                continue

        self.persistir_estado()
        self._imprimir_resumen_metricas()

    def _imprimir_resumen_metricas(self) -> None:
        total = len(self.procesadas_por_id)
        ingenieria = [o for o in self.procesadas_por_id.values() if o.get("evaluacion_cargo", {}).get("es_ingenieria_valida")]
        total_ing = len(ingenieria)
        no_ing = total - total_ing

        distribucion: Dict[str, int] = {}
        for o in self.procesadas_por_id.values():
            cat = o.get("evaluacion_cargo", {}).get("categoria_trayectoria", "DESCONOCIDO")
            distribucion[cat] = distribucion.get(cat, 0) + 1

        total_skills = sum(len(o.get("competencias_extraidas", [])) for o in self.procesadas_por_id.values())

        print("\n" + "=" * 75)
        print("RESUMEN DE EVALUACIÓN Y EXTRACCIÓN (V4.1)")
        print("=" * 75)
        print(f"Total vacantes procesadas          : {total}")
        print(f"Vacantes de Ingeniería válidas     : {total_ing} ({total_ing / total * 100:.1f}%)" if total else 0)
        print(f"Cargos No Profesionales / Oficios  : {no_ing} ({no_ing / total * 100:.1f}%)" if total else 0)
        print("\nDistribución por Nivel de Trayectoria:")
        for cat, cant in sorted(distribucion.items()):
            print(f"  * {cat:<20}: {cant} vacantes")
        print(f"\nTotal competencias extraídas       : {total_skills}")
        print(f"CSV consolidado (100% registros)   : {self.output_csv}")
        print(f"JSON de ofertas de ingeniería      : {self.output_json}")
        print(f"Log de vacantes no procesadas      : {ERROR_LOG_PATH}")
        print("=" * 75)


if __name__ == "__main__":
    pipeline = MiningEvaluationPipelineV4(
        input_path=INPUT_DATASET_PATH,
        output_csv=OUTPUT_CSV_PATH,
        output_json=OUTPUT_JSON_PATH,
        checkpoint_path=CHECKPOINT_PATH
    )
    pipeline.run()