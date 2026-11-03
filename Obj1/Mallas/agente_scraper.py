import pandas as pd
import requests
from google import genai
import time
import json
import urllib3
import os
import io
from bs4 import BeautifulSoup
import pypdf

# Ocultar advertencias de certificados web
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Credenciales externas: nunca incrustar claves en el repositorio.
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "").strip()
if not GOOGLE_API_KEY:
    raise RuntimeError("Configura GOOGLE_API_KEY como variable de entorno antes de ejecutar este script.")
cliente = genai.Client(api_key=GOOGLE_API_KEY)
ARCHIVO_SALIDA = "Perfiles_Extraidos_Coquimbo.csv"

def extraer_texto_fuente(url):
    if pd.isna(url) or url == "Sin URL":
        return "No hay información disponible."
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        respuesta = requests.get(url, headers=headers, timeout=15, verify=False)
        
        # Extracción para PDFs (Texto)
        if ".pdf" in url.lower():
            pdf_file = io.BytesIO(respuesta.content)
            reader = pypdf.PdfReader(pdf_file)
            texto_pdf = ""
            for page in reader.pages:
                texto_pdf += page.extract_text() + "\n"
            return texto_pdf[:15000] # Límite de caracteres para la API
            
        # Extracción para Páginas Web (HTML)
        else:
            soup = BeautifulSoup(respuesta.text, 'html.parser')
            return soup.get_text(separator=' ', strip=True)[:15000]
            
    except Exception as e:
        return "Error al acceder a la fuente de datos."

def agente_ia_extractor(carrera, universidad, texto_perfil, texto_malla, max_reintentos=4):
    """Envía el texto en bruto a la IA y le pide que devuelva un formato JSON estructurado."""
    prompt_maestro = f"""
    Eres un Agente Experto. Extrae la información de '{carrera}' de la '{universidad}'.
    1. Del 'Texto del Perfil' extrae el Perfil de Egreso.
    2. Del 'Texto de la Malla' extrae la lista de asignaturas.
    
    Responde ÚNICAMENTE en este formato JSON:
    {{
        "perfil_egreso": "texto...",
        "asignaturas": ["ramo 1", "ramo 2"]
    }}
    
    --- TEXTO DEL PERFIL ---
    {texto_perfil}
    
    --- TEXTO DE LA MALLA ---
    {texto_malla}
    """
    
    for intento in range(max_reintentos):
        try:
            respuesta = cliente.models.generate_content(
                model='gemini-3.6-flash',
                contents=prompt_maestro,
            )
            # Limpiamos el texto para asegurar que sea un JSON válido
            json_limpio = respuesta.text.replace("```json", "").replace("```", "").strip()
            datos = json.loads(json_limpio)
            
            # Formateamos las asignaturas como una lista separada por comas
            asignaturas_raw = datos.get("asignaturas", [])
            if isinstance(asignaturas_raw, list):
                datos["asignaturas"] = ", ".join(asignaturas_raw)
            else:
                datos["asignaturas"] = str(asignaturas_raw)
                
            return datos
            
        except Exception as e:
            error_msg = str(e)
            if "503" in error_msg or "429" in error_msg: # Manejo de saturación de API de Google
                tiempo_espera = 15 * (intento + 1)
                print(f"  [!] Cuota Google. Pausa de {tiempo_espera}s (Intento {intento+1})...")
                time.sleep(tiempo_espera)
            else:
                print(f"  [!] Error de IA: {error_msg}")
                break
                
    return {"perfil_egreso": "Información no encontrada", "asignaturas": ""}

# =========================================================
# FLUJO PRINCIPAL INCREMENTAL
# =========================================================

# 1. Cargar el Excel base
df = pd.read_excel("Lista_Carreras (1).xlsx") # O el nombre del archivo excel en ese momento
df_validas = df[df['Incluir'].astype(str).str.strip().str.upper() == 'SI'].copy()

# 2. Revisar qué carreras ya fueron procesadas para no repetir trabajo
carreras_procesadas = set()
if os.path.exists(ARCHIVO_SALIDA):
    try:
        df_existente = pd.read_csv(ARCHIVO_SALIDA) 
        for _, row in df_existente.iterrows():
            if "Información no encontrada" not in str(row.get('Perfil_Egreso', '')):
                carreras_procesadas.add(f"{row['Carrera']} - {row['Universidad']}")
    except Exception as e:
        print(f"ERROR LEYENDO TU CSV (Revisa el formato): {e}")

print(f"Iniciando Motor Gemini + Lector PDF. {len(carreras_procesadas)} carreras listas.\n")

# 3. Iterar sobre las carreras que faltan
for index, row in df_validas.iterrows():
    carrera = row['Nombre Carrera']
    ies = row['Nombre IES']
    identificador = f"{carrera} - {ies}"
    
    if identificador in carreras_procesadas:
        print(f"Saltando (Ya lista): {identificador}")
        continue
        
    print(f"Procesando: {identificador}")
    
    texto_perfil = extraer_texto_fuente(row['URL Perfil de Egreso'])
    texto_malla = extraer_texto_fuente(row['URL Malla Curricular']) if row['URL Malla Curricular'] != row['URL Perfil de Egreso'] else texto_perfil
    
    datos = agente_ia_extractor(carrera, ies, texto_perfil, texto_malla)
    
    # 4. Guardar incrementalmente fila por fila
    df_nuevo = pd.DataFrame([{
        "Universidad": ies,
        "Carrera": carrera,
        "Perfil_Egreso": datos.get("perfil_egreso", ""),
        "Asignaturas": datos.get("asignaturas", "")
    }])
    
    if not os.path.exists(ARCHIVO_SALIDA):
        df_nuevo.to_csv(ARCHIVO_SALIDA, index=False, encoding='utf-8-sig')
    else:
        df_nuevo.to_csv(ARCHIVO_SALIDA, mode='a', header=False, index=False, encoding='utf-8-sig')
    
    time.sleep(15) # Pausa de cortesía obligatoria

print("\n¡Proceso finalizado! Revisa tu archivo CSV.")