import os
import pandas as pd
import requests
import io
import pymupdf
from PIL import Image
from google import genai
import time
import urllib3
import re

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Credenciales externas: nunca incrustar claves en el repositorio.
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "").strip()
if not GOOGLE_API_KEY:
    raise RuntimeError("Configura GOOGLE_API_KEY como variable de entorno antes de ejecutar este script.")
cliente = genai.Client(api_key=GOOGLE_API_KEY)
ARCHIVO_CSV = "Perfiles_Extraidos_Coquimbo.csv"
ARCHIVO_EXCEL = "Lista_Carreras (1).xlsx"

def procesar_con_ia(prompt, imagenes=None, max_reintentos=4):
    """Función unificada que maneja los reintentos y envía el contenido a la IA"""
    contents = []
    if imagenes:
        contents.append(imagenes)
    contents.append(prompt)
    
    for intento in range(max_reintentos):
        try:
            res = cliente.models.generate_content(model='gemini-3.6-flash', contents=contents)
            return res.text.replace("\n", ", ").strip()
        except Exception as e:
            if "503" in str(e) or "429" in str(e):
                espera = 15 * (intento + 1)
                print(f"    [!] Servidor IA saturado. Reintentando en {espera}s...")
                time.sleep(espera)
            else:
                raise e
    return ""

def extraer_malla_inteligente(url, carrera, universidad):
    """Detecta automáticamente si es PDF, Imagen o Web, y extrae los ramos"""
    headers = {'User-Agent': 'Mozilla/5.0'}
    respuesta = requests.get(url, headers=headers, timeout=45, verify=False)
    
    # El script detecta qué tipo de archivo nos entregó el link
    tipo_contenido = respuesta.headers.get('Content-Type', '').lower()
    
    if 'pdf' in tipo_contenido or '.pdf' in str(url).lower():
        print("  -> Formato PDF detectado. Aplicando motor de Visión Artificial...")
        doc = pymupdf.open(stream=respuesta.content, filetype="pdf")
        pagina = doc.load_page(0) 
        matriz_zoom = pymupdf.Matrix(2.0, 2.0) 
        pixmap = pagina.get_pixmap(matrix=matriz_zoom)
        imagen = Image.open(io.BytesIO(pixmap.tobytes("png")))
        
        prompt = """Eres un experto en mallas curriculares. Extrae de esta imagen ÚNICAMENTE 
        la lista de todas las asignaturas (ramos). Devuelve estrictamente los nombres separados por comas. Cero introducciones."""
        return procesar_con_ia(prompt, imagenes=imagen)
        
    elif 'image' in tipo_contenido:
        print("  -> Formato Imagen detectado. Aplicando motor de Visión Artificial...")
        imagen = Image.open(io.BytesIO(respuesta.content))
        
        prompt = """Eres un experto en mallas curriculares. Extrae de esta imagen ÚNICAMENTE 
        la lista de todas las asignaturas (ramos). Devuelve estrictamente los nombres separados por comas. Cero introducciones."""
        return procesar_con_ia(prompt, imagenes=imagen)
        
    else:
        print("  -> Formato HTML/Web detectado. Aplicando motor de Texto NLP...")
        html_clean = re.sub(r'<script.*?</script>', '', respuesta.text, flags=re.DOTALL)
        html_clean = re.sub(r'<style.*?</style>', '', html_clean, flags=re.DOTALL)
        texto_web = re.sub(r'<[^>]+>', ' ', html_clean)
        texto_web = re.sub(r'\s+', ' ', texto_web).strip()[:15000]
        
        prompt = f"""Extrae ÚNICAMENTE la lista de asignaturas de '{carrera}' de '{universidad}'.
        Devuelve estrictamente los nombres separados por comas. Cero introducciones.
        --- TEXTO ---
        {texto_web}"""
        return procesar_con_ia(prompt)

# --- FLUJO PRINCIPAL ---
print("Cargando bases de datos...")
df_csv = pd.read_csv(ARCHIVO_CSV, encoding='utf-8-sig')
df_excel = pd.read_excel(ARCHIVO_EXCEL)
df_excel.columns = df_excel.columns.str.strip()

def le_faltan_asignaturas(texto):
    if pd.isna(texto): return True
    return str(texto).strip() == "" or "Información no encontrada" in str(texto)

filas_a_reparar = df_csv[df_csv['Asignaturas'].apply(le_faltan_asignaturas)].index.tolist()
print(f"Se encontraron {len(filas_a_reparar)} carreras sin asignaturas. Iniciando rescate definitivo...\n")

cambios = 0
for idx in filas_a_reparar:
    carrera = df_csv.at[idx, 'Carrera']
    ies = df_csv.at[idx, 'Universidad']
    print(f"Rescatando: {carrera} - {ies}")
    
    match = df_excel[(df_excel['Nombre Carrera'].str.strip() == carrera.strip()) & 
                     (df_excel['Nombre IES'].str.strip() == ies.strip())]
    
    if not match.empty:
        url_malla = match.iloc[0]['URL Malla Curricular']
        
        try:
            nuevas_asignaturas = extraer_malla_inteligente(url_malla, carrera, ies)
            
            if nuevas_asignaturas and len(nuevas_asignaturas) > 15:
                df_csv.at[idx, 'Asignaturas'] = nuevas_asignaturas
                cambios += 1
                print("  [OK] ¡Asignaturas inyectadas con éxito!")
                df_csv.to_csv(ARCHIVO_CSV, index=False, encoding='utf-8-sig')
            else:
                print("  [X] La IA no detectó ramos útiles.")
        except Exception as e:
            print(f"  [Error] Fallo en la extracción: {e}")
    else:
        print("  [X] URL no encontrada en Excel original.")
        
    time.sleep(10)

print(f"\n¡Proceso finalizado! Se inyectaron {cambios} mallas directamente en '{ARCHIVO_CSV}'.")