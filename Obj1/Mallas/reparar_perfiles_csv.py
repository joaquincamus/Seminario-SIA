#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reparación controlada EN LA MISMA carpeta Tesis_Perfiles.

Mantiene agente_scraper.py original intacto.
Lee Lista_Carreras (1).xlsx + Perfiles_Extraidos_Coquimbo.csv (48 o 46),
excluye las 2 carreras identificadas, detecta automáticamente perfiles inválidos,
recupera SOLO los 5 perfiles pendientes, y prepara vista previa para revisión.
No modifica CSV canónico salvo ejecutar --aplicar después de revisar.
"""
from __future__ import annotations
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import unicodedata
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Tag

try:
    import pandas as pd
except ImportError as exc:
    raise SystemExit("Dependencias: python -m pip install pandas openpyxl beautifulsoup4 requests") from exc

ROOT = Path(__file__).resolve().parent
EXCLUSIONES = {
    ('UNIVERSIDAD CENTRAL DE CHILE', 'INGENIERIA CIVIL INDUSTRIAL'),
    ('UNIVERSIDAD DEL ALBA', 'INGENIERIA INDUSTRIAL'),
}
REPARACIONES = {
    ('IP DE CHILE', 'INGENIERIA EN ADMINISTRACION DE EMPRESAS'): 'PERFIL_DE_EGRESO',
    ('IP AIEP', 'INGENIERIA EN INFORMATICA'): 'PERFIL_PROFESIONAL',
    ('IP AIEP', 'INGENIERIA EN MECANICA AUTOMOTRIZ Y AUTOTRONICA'): 'PERFIL_PROFESIONAL',
    ('IP AIEP', 'INGENIERIA EN MINAS'): 'PERFIL_PROFESIONAL',
    ('IP AIEP', 'INGENIERIA INDUSTRIAL'): 'PERFIL_PROFESIONAL',
}
ERROR_PATTERNS = [
    r'no\s+(?:se\s+)?(?:encuentra|dispone|especifica)',
    r'no\s+(?:est[aá]\s+)?disponible',
    r'informaci[oó]n\s+no\s+encontrada',
    r'no\s+hay\s+informaci[oó]n',
    r'error\s+al\s+acceder',
    r'texto\s+proporcionado',
]
SECTION_PATTERN = re.compile(r'\bperfil\s+(?:profesional|de\s+egreso)\b', re.I)
END_PATTERN = re.compile(
    r'^(?:campo\s+laboral|malla\s+curricular|descargar\s+malla|\u00bf?quieres\s+obtener\s+m[aá]s|'
    r'continuidad\s+de\s+estudios|inscr[ií]bete|admisio[nó]|aranceles|contacto|'
    r'la\s+oportunidad\s+de\s+tu\s+vida|postula\s+aqu[ií]|\u00bf?d[oó]nde\s+trabajar)', re.I)
HEADINGS = ('h1','h2','h3','h4','h5','h6')
FIELDS = ['Universidad','Carrera','Perfil_Egreso','Asignaturas']

def normalizar(s: str) -> str:
    s = unicodedata.normalize('NFKD', str(s))
    return ' '.join(''.join(c for c in s if not unicodedata.combining(c)).upper().split())


def clave(uni: str, car: str) -> tuple[str, str]:
    return normalizar(uni), normalizar(car)


def id_programa(k: tuple[str, str]) -> str:
    return 'PRG_' + hashlib.sha256('||'.join(k).encode()).hexdigest()[:14].upper()


def perfil_valido(texto: str) -> bool:
    limpio = re.sub(r'\s+', ' ', str(texto or '')).strip()
    if len(limpio) < 120 or len(limpio.split()) < 18:
        return False
    if any(re.search(exp, limpio, re.I) for exp in ERROR_PATTERNS):
        return False
    if re.match(r'^(?:perfil\s+(?:profesional|de\s+egreso)\s*)?no\b', limpio, re.I):
        return False
    return True


def limpiar_html(html: str) -> BeautifulSoup:
    soup = BeautifulSoup(html, 'html.parser')
    for tag in soup(['script', 'style', 'noscript', 'template', 'svg']):
        tag.decompose()
    return soup


def titulo_corresponde(soup: BeautifulSoup, carrera: str) -> bool:
    """Control anti-cruce: buscar tokens significativos en h1 o título; tolera variantes.

    Se permite prefijos generales de institución, pero no una ingeniería diferente.
    """
    titulos = [t.get_text(' ', strip=True) for t in soup.find_all('h1')]
    if soup.title:
        titulos.append(soup.title.get_text(' ', strip=True))
    if not titulos:
        return True  # El origen sigue requiriendo revisión manual.
    tokens = [t for t in normalizar(carrera).split() if t not in
              {'INGENIERIA', 'EN', 'DE', 'Y', 'CON', 'LA', 'MENCION', 'INDUSTRIAL'}]
    if not tokens:
        tokens = ['INDUSTRIAL']
    for titulo in titulos:
        norm_title = normalizar(titulo)
        if sum(tok in norm_title.split() for tok in tokens) >= max(1, len(tokens) - 1):
            return True
    return False


def recortar_parrafos_desde_encabezado(heading: Tag) -> str:
    """Solo párrafos posteriores al encabezado, hasta el siguiente encabezado/sección.

    Evita que menú, campo laboral y pie de página ingresen al perfil.
    """
    paragraphs: list[str] = []
    for node in heading.next_elements:
        if isinstance(node, Tag):
            if node is not heading and node.name in HEADINGS:
                break
            if node.name in ('p', 'li'):
                # Descartar menús, navegación y botones.
                if node.find_parent(['nav', 'header', 'footer', 'form']):
                    continue
                text = re.sub(r'\s+', ' ', node.get_text(' ', strip=True)).strip()
                if END_PATTERN.match(text):
                    break
                if len(text) >= 42 and text not in paragraphs:
                    paragraphs.append(text)
        if len(paragraphs) >= 12:
            break
    result = '\n'.join(paragraphs)
    return result if perfil_valido(result) else ''


def fallback_lineas(soup: BeautifulSoup) -> str:
    """Secciones por líneas como respaldo de sitios con estructura no semántica."""
    lines = [re.sub(r'\s+', ' ', x).strip() for x in soup.get_text('\n', strip=True).splitlines()]
    lines = [x for x in lines if x]
    candidates = []
    for i, line in enumerate(lines):
        if len(line) > 100 or not SECTION_PATTERN.search(line):
            continue
        if len(line) > 95 or re.match(r'^(?:ver|descargar|conocer|más|mas)\b', line, re.I):
            continue
        chunk = []
        for nxt in lines[i + 1:i + 24]:
            if END_PATTERN.match(nxt) or (len(nxt) < 100 and SECTION_PATTERN.search(nxt)):
                break
            if len(nxt) >= 40 and nxt not in chunk:
                chunk.append(nxt)
            if len(' '.join(chunk)) >= 2400:
                break
        content = '\n'.join(chunk)
        if perfil_valido(content):
            candidates.append(content)
    return max(candidates, key=len, default='')


def extraer_perfil_html(html: str, carrera: str, tipo: str) -> str:
    """Extrae el apartado completo sin producir redacción generada por IA.

    La clasificación del apartado («Profesional» vs «Egreso») permanece
    explícita en META. No presupone equivalencia entre ambos documentos.
    """
    soup = limpiar_html(html)
    if not titulo_corresponde(soup, carrera):
        raise ValueError(f'Identidad de carrera no coincide con título HTML: {carrera}')
    head_candidates = [h for h in soup.find_all(HEADINGS)
                       if SECTION_PATTERN.search(h.get_text(' ', strip=True))]
    if tipo == 'PERFIL_PROFESIONAL':
        head_candidates = [h for h in head_candidates if re.search('profesional',h.get_text(' ', strip=True),re.I)]
    elif tipo == 'PERFIL_DE_EGRESO':
        head_candidates = [h for h in head_candidates if re.search('egreso',h.get_text(' ', strip=True),re.I)]
    results = [recortar_parrafos_desde_encabezado(h) for h in head_candidates]
    results = [s for s in results if perfil_valido(s)]
    if results:
        return max(results, key=len)
    return fallback_lineas(soup)


def obtener_html(url: str, offline: bool, filename_local: Path | None, timeout: int) -> tuple[str, str]:
    if filename_local and filename_local.is_file():
        return filename_local.read_text(encoding='utf-8'), 'HTML_LOCAL_VERIFICABLE'
    if offline:
        raise RuntimeError('Sin red y sin HTML local aportado')
    try:
        import requests
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
    except ImportError as exc:
        raise RuntimeError('Se requieren requests y urllib3. Revise requirements.txt') from exc
    parsed = urlparse(url)
    if parsed.scheme != 'https' or not parsed.netloc:
        raise ValueError('URL de perfil debe ser HTTPS institucional')
    client = requests.Session()
    retries = Retry(total=3, backoff_factor=1, status_forcelist=[429,500,502,503,504],
                    allowed_methods=['GET'])
    client.mount('https://', HTTPAdapter(max_retries=retries))
    response = client.get(url, headers={'User-Agent': 'Mozilla/5.0 (compatible; TesisCurricular/2.0)'},
                          timeout=timeout, verify=True)
    response.raise_for_status()
    mime = response.headers.get('Content-Type', '').lower()
    if 'text/html' not in mime and 'application/xhtml' not in mime and '<html' not in response.text[:500].lower():
        raise RuntimeError(f'Página de perfil no es HTML: {mime!r}')
    if len(response.content) < 350:
        raise RuntimeError('HTML sospechosamente pequeño')
    return response.text, 'WEB_INSTITUCIONAL'




def sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def read_master(path: Path) -> tuple[list[dict], dict]:
    if path.suffix.lower() == '.csv':
        with path.open(encoding='utf-8-sig',newline='') as f:
            # Entrada CSV permitida solo para pruebas o exportación del Excel.
            sample=f.read(2048);f.seek(0)
            sep=';' if ';' in sample.splitlines()[0] else ','
            rows=list(csv.DictReader(f,delimiter=sep))
    else:
        rows=pd.read_excel(path,dtype=str).fillna('').to_dict('records')
    necessary={'Nombre Carrera','Nombre IES','Incluir','URL Perfil de Egreso','URL Malla Curricular'}
    if not rows or not necessary <= set(rows[0]):
        raise ValueError(f'Columnas de maestro requeridas: {sorted(necessary)}')
    mapping={clave(r['Nombre IES'],r['Nombre Carrera']):r for r in rows}
    if len(mapping)!=len(rows):
        raise ValueError('Excel maestro contiene programas duplicados')
    for k in EXCLUSIONES:
        if k not in mapping:
            raise ValueError(f'Carrera excluida no encontrada en maestro: {k}')
        r=mapping[k]
        if normalizar(r['Incluir']) != 'NO':
            raise ValueError(f'El maestro todavía incluye una carrera descartada: {k}')
    inc=[r for r in rows if normalizar(r['Incluir']) in {'SI','SÍ'}]
    if len(inc)!=46:
        raise ValueError(f'Se esperaban 46 carreras incluidas, Excel indica {len(inc)}')
    if not set(REPARACIONES)<=set(clave(r['Nombre IES'],r['Nombre Carrera']) for r in inc):
        raise ValueError('Falta una de las cinco carreras recuperables en maestro')
    return inc,mapping


def read_csv_rows(path: Path) -> list[dict]:
    if not path.is_file():
        raise FileNotFoundError(f'Falta archivo CSV histórico: {path}')
    with path.open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f)
        if not reader.fieldnames or not set(FIELDS)<=set(reader.fieldnames):
            raise ValueError('El CSV debe conservar Universidad,Carrera,Perfil_Egreso,Asignaturas')
        rows=list(reader)
    if len(rows) not in {46,48}:
        raise ValueError(f'Se esperan 48 registros históricos o 46 ya depurados; encontrados {len(rows)}')
    if len({clave(r['Universidad'],r['Carrera']) for r in rows})!=len(rows):
        raise ValueError('CSV contiene carreras duplicadas: revisar antes de reparar')
    return rows


def write_csv(path: Path, rows:list[dict], fields:list[str]):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp')
    with tmp.open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore')
        writer.writeheader();writer.writerows(rows)
    os.replace(tmp,path)


def validate_final(rows:list[dict], included:list[dict]):
    if len(rows)!=46:
        raise ValueError(f'Salida incompleta: {len(rows)} filas; deberían ser 46')
    keys=[clave(r['Universidad'],r['Carrera']) for r in rows]
    if len(keys)!=len(set(keys)):
        raise ValueError('Carreras duplicadas en salida')
    if set(keys)!={clave(m['Nombre IES'],m['Nombre Carrera']) for m in included}:
        raise ValueError('Las 46 carreras no coinciden con el maestro actualizado')
    if set(keys)&EXCLUSIONES:
        raise ValueError('Se ha conservado una carrera excluida')
    for r in rows:
        if not perfil_valido(r['Perfil_Egreso']):
            raise ValueError(f'Perfil sin validar: {r["Universidad"]} - {r["Carrera"]}')
        if not str(r['Asignaturas']).strip():
            raise ValueError(f'Asignaturas vacías: {r["Universidad"]} - {r["Carrera"]}')


def prepare(args):
    inc,master_map=read_master(args.maestro)
    source=args.csv.read_bytes()
    hist=read_csv_rows(args.csv)
    orig_map={clave(r['Universidad'],r['Carrera']):r for r in hist}
    reviewdir=args.csv.parent/'_REVISION_REPARACION'
    reviewdir.mkdir(parents=True,exist_ok=True)
    out=[];control=[]
    for m in inc:
        key=clave(m['Nombre IES'],m['Nombre Carrera'])
        if key not in orig_map:
            raise ValueError(f'No se puede unir contra el CSV original: {key}')
        old=orig_map[key]
        profile=str(old['Perfil_Egreso']).strip()
        status='CONSERVADO_HISTORICO';error='';url=str(m['URL Perfil de Egreso']).strip()
        doc_type=REPARACIONES.get(key,'PERFIL_HISTORICO_NO_REVALIDADO')
        profile_valid=perfil_valido(profile)
        if key in REPARACIONES and not profile_valid:
            try:
                if not url.lower().startswith('https://'):
                    raise ValueError('URL no corresponde a sitio HTTPS')
                host=urlparse(url).hostname or ''
                official='aiep.cl' if key[0]=='IP AIEP' else 'ipchile.cl'
                if host!=official and not host.endswith('.'+official):
                    raise ValueError(f'URL no pertenece al dominio oficial {official}')
                htmlpath=args.html_locales/(id_programa(key)+'.html') if args.html_locales else None
                html,_=obtener_html(url,args.sin_red,htmlpath,args.timeout)
                profile=extraer_perfil_html(html,m['Nombre Carrera'],doc_type)
                if not perfil_valido(profile):
                    raise ValueError('Apartado recuperado insuficiente o inválido')
                status='RECUPERADO_PENDIENTE_REVISION_HUMANA'
            except Exception as exc:
                profile=''
                status='PENDIENTE_RECUPERAR'
                error=str(exc)[:400]
        elif not profile_valid:
            profile=''
            status='OTRO_PERFIL_INVALIDO'
            error='No corresponde a los cinco casos previstos; requiere revisión específica'
        elif key in REPARACIONES:
            status='PERFIL_YA_PRESENTE_CONSERVADO'
        out.append({'Universidad':m['Nombre IES'],'Carrera':m['Nombre Carrera'],
                    'Perfil_Egreso':profile,'Asignaturas':old['Asignaturas']})
        control.append({'Universidad':m['Nombre IES'],'Carrera':m['Nombre Carrera'],
                        'Estado':status,'Tipo_documento':doc_type,'URL':url,
                        'Longitud_perfil':len(profile),'Error':error})
    assert len(out)==46
    preview=reviewdir/'Perfiles_Extraidos_Coquimbo_REVISION.csv'
    controlpath=reviewdir/'Control_Reparacion_Perfiles.csv'
    manifest=reviewdir/'control_integridad.json'
    write_csv(preview,out,FIELDS)
    write_csv(controlpath,control,list(control[0]))
    missing=[r for r in control if r['Estado'] in {'PENDIENTE_RECUPERAR','OTRO_PERFIL_INVALIDO'}]
    ready=not missing
    if ready:
        validate_final(out,inc)
    manifest.write_text(json.dumps({
        'origen_sha256':sha_bytes(source),
        'maestro_sha256':sha_bytes(args.maestro.read_bytes()),
        'propuesta_sha256':sha_bytes(preview.read_bytes()),
        'salida_validable':ready,
        'carreras':len(out),
        'perfiles_recuperados':sum(r['Estado']=='RECUPERADO_PENDIENTE_REVISION_HUMANA' for r in control),
        'pendientes':len(missing),
        'fecha_utc':datetime.now(timezone.utc).isoformat(),
    },ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'CSV de 46 carreras para revisión: {preview}')
    print(f'Control de perfiles: {controlpath}')
    print(f'Perfiles recuperados esta vez: {sum(r["Estado"]=="RECUPERADO_PENDIENTE_REVISION_HUMANA" for r in control)}')
    print(f'Perfiles pendientes: {len(missing)}')
    if missing:
        for r in missing: print(' -',r['Universidad'],r['Carrera'],':',r['Error'])
        print('NO SE REEMPLAZÓ el archivo original. Corrija pendientes y repita.')
        return 2
    print('LISTO PARA REVISION HUMANA: compruebe los cinco textos y sus URLs en el control.')
    print('Para aplicar después de revisar: python reparar_perfiles_csv.py --aplicar')
    return 0


def apply(args):
    inc,_=read_master(args.maestro)
    reviewdir=args.csv.parent/'_REVISION_REPARACION'
    preview=reviewdir/'Perfiles_Extraidos_Coquimbo_REVISION.csv'
    manifest=reviewdir/'control_integridad.json'
    controlpath=reviewdir/'Control_Reparacion_Perfiles.csv'
    if not (preview.is_file() and manifest.is_file() and controlpath.is_file()):
        raise ValueError('No existe propuesta lista. Primero ejecute el reparador sin --aplicar')
    m=json.loads(manifest.read_text(encoding='utf-8'))
    if not m['salida_validable']:
        raise ValueError('Existen perfiles pendientes. No se permite reemplazar el CSV histórico')
    if sha_bytes(args.csv.read_bytes())!=m['origen_sha256']:
        raise ValueError('El CSV original cambió después de preparar la propuesta. Regenere revisión')
    if sha_bytes(args.maestro.read_bytes())!=m['maestro_sha256']:
        raise ValueError('El Excel maestro cambió. Regenere revisión')
    if sha_bytes(preview.read_bytes())!=m['propuesta_sha256']:
        raise ValueError('La propuesta fue modificada después de generarse. Regenere revisión')
    rows=read_csv_rows(preview)
    validate_final(rows,inc)
    backup_dir=args.csv.parent/'_RESPALDO_ANTES_REPARACION'
    backup_dir.mkdir(parents=True,exist_ok=True)
    backup=backup_dir/('Perfiles_Extraidos_Coquimbo_'+m['origen_sha256'][:12]+'.csv')
    if not backup.exists():
        shutil.copy2(args.csv,backup)
    # El destino conserva su nombre original y columnas originales.
    # Se escribe con archivo temporal para evitar truncamiento en fallos.
    write_csv(args.csv,rows,FIELDS)
    if sha_bytes(args.csv.read_bytes())!=m['propuesta_sha256']:
        raise RuntimeError('Integridad final no coincide: restaurar desde el respaldo')
    print(f'[APLICADO] CSV original actualizado con 46 programas: {args.csv}')
    print(f'[RESPALDO] Original anterior conservado en: {backup}')
    print('IMPORTANTE: regenerar ESCO, NLP y clustering; sus CSV anteriores ya no corresponden.')
    return 0


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--maestro',type=Path,default=ROOT/'Lista_Carreras (1).xlsx')
    parser.add_argument('--csv',type=Path,default=ROOT/'Perfiles_Extraidos_Coquimbo.csv')
    parser.add_argument('--html-locales',type=Path,default=None,
                        help='Carpeta opcional con HTML institucional guardado, nombrado por Programa_ID')
    parser.add_argument('--sin-red',action='store_true')
    parser.add_argument('--timeout',type=int,default=35)
    parser.add_argument('--aplicar',action='store_true',help='Reemplaza el CSV tras revisión humana y controles')
    args=parser.parse_args(argv)
    try:
        return apply(args) if args.aplicar else prepare(args)
    except Exception as exc:
        print('[ERROR] '+str(exc),file=sys.stderr)
        return 1


if __name__=='__main__':
    sys.exit(main())
