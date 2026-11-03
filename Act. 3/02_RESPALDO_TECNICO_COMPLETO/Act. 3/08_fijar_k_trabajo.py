#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OBJ2 / ACT. 3 / PASO 08 — Fijar particiones de trabajo PROVISIONALES.

EJECUCIÓN EN VS CODE: abrir este archivo dentro de DESARROLLO/Obj2/Act. 3/
y pulsar ▶ (Run Python File). Las rutas se resuelven desde __file__.

No reajusta K-Means: reutiliza EXACTAMENTE las asignaciones del paso 06
inspeccionadas en el paso 07, correspondientes a la semilla 42.
NO calcula cobertura ni similitud academia–mercado; NO valida mapeos ESCO.
Las etiquetas de grupo son propuestas editables y NO resultados validados.

Solo biblioteca estándar; no requiere bibliotecas adicionales.
"""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

# ---------- Configuración: decisiones metodológicas provisionales ----------
ACT3 = Path(__file__).resolve().parent
DIR05 = ACT3 / 'salida_vectores_registros'
DIR06 = ACT3 / 'salida_evaluacion_kmeans'
DIR07 = ACT3 / 'salida_inspeccion_clusters'
SALIDA = ACT3 / 'salida_seleccion_k'
DELIMITADOR = ';'

# Estas tres decisiones se pueden volver a evaluar tras revisión humana.
K_PRINCIPALES = {'academia': 5, 'mercado': 3}
K_CONJUNTO_EXPLORATORIO = 4  # NO es la partición principal.

# Nombre interpretativo sugerido, sujeto a revisión humana de ESCO.
ETIQUETAS = {
    ('academia', 5, 0): 'Ingeniería de minas y planificación minera',
    ('academia', 5, 1): 'Gestión, administración e ingeniería industrial',
    ('academia', 5, 2): 'Informática y otras ingenierías (grupo heterogéneo)',
    ('academia', 5, 3): 'Electricidad, control y mecánica',
    ('academia', 5, 4): 'Medioambiente y prevención de riesgos',
    ('mercado', 3, 0): 'Datos y analítica',
    ('mercado', 3, 1): 'Operaciones, mantenimiento y calidad',
    ('mercado', 3, 2): 'Gestión y coordinación de proyectos',
    ('conjunto', 4, 0): 'Datos y analítica (comparación exploratoria)',
    ('conjunto', 4, 1): 'Operaciones, calidad y mantenimiento (exploratorio)',
    ('conjunto', 4, 2): 'Minería y planificación minera (exploratorio)',
    ('conjunto', 4, 3): 'Proyectos de ingeniería (exploratorio)',
}
# -------------------------------------------------------------------------


def leer_csv(ruta: Path, columnas: set[str]) -> list[dict[str, str]]:
    if not ruta.is_file():
        raise FileNotFoundError(f'No se encuentra: {ruta}')
    with ruta.open('r', encoding='utf-8-sig', newline='') as fh:
        lector = csv.DictReader(fh, delimiter=DELIMITADOR)
        disponibles = set(lector.fieldnames or [])
        if not columnas <= disponibles:
            raise ValueError(f'{ruta.name}: columnas faltantes {sorted(columnas-disponibles)}; revisa el separador ;')
        filas = list(lector)
    if not filas or any(None in f or any(v is None for v in f.values()) for f in filas):
        raise ValueError(f'{ruta.name}: CSV vacío o irregular')
    return filas


def guardar_csv(ruta: Path, filas: list[dict], columnas: list[str]) -> None:
    with ruta.open('w', encoding='utf-8-sig', newline='') as fh:
        writer = csv.DictWriter(fh, fieldnames=columnas, delimiter=DELIMITADOR, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(filas)


def sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with ruta.open('rb') as fh:
        for bloque in iter(lambda: fh.read(1024*1024), b''):
            h.update(bloque)
    return h.hexdigest()


def num_entero(valor: str, contexto: str) -> int:
    try:
        return int(valor)
    except (ValueError, TypeError) as exc:
        raise ValueError(f'Valor entero inválido: {contexto}={valor!r}') from exc


def clave_registro(fila: dict) -> tuple:
    return (fila['origen'], str(fila['fila_csv']), fila['id_registro'])


def cargar_y_verificar():
    rutas = {
        '05_indice_registros.csv': DIR05 / '05_indice_registros.csv',
        '06_asignaciones_exploratorias.csv': DIR06 / '06_asignaciones_exploratorias.csv',
        '06_metricas_por_k.csv': DIR06 / '06_metricas_por_k.csv',
        '07_asignaciones_candidatos.csv': DIR07 / '07_asignaciones_candidatos.csv',
        '07_perfiles_clusters.csv': DIR07 / '07_perfiles_clusters.csv',
        '07_competencias_por_cluster.csv': DIR07 / '07_competencias_por_cluster.csv',
        '07_panorama_candidatos.csv': DIR07 / '07_panorama_candidatos.csv',
        '07_resumen_inspeccion.json': DIR07 / '07_resumen_inspeccion.json',
    }
    for ruta in rutas.values():
        if not ruta.is_file():
            raise FileNotFoundError(f'Falta {ruta}. Ejecuta el paso 05, 06 o 07 correspondiente.')

    # Verificar que el paso 07 partió de las mismas salidas 05/06 que usaremos.
    resumen07 = json.loads(rutas['07_resumen_inspeccion.json'].read_text(encoding='utf-8-sig'))
    entradas07 = resumen07.get('entradas_sha256', {})
    for nombre in ('05_indice_registros.csv', '06_asignaciones_exploratorias.csv', '06_metricas_por_k.csv'):
        esperado = entradas07.get(nombre)
        if esperado and sha256(rutas[nombre]) != esperado:
            raise ValueError(f'{nombre} difiere del archivo usado para generar el paso 07')

    indice = leer_csv(rutas['05_indice_registros.csv'], {'fila_vector_0_based','origen','fila_csv','id_registro'})
    metricas = leer_csv(rutas['06_metricas_por_k.csv'], {'grupo','k','estado','silueta_coseno','estabilidad_ari_media', 'cluster_mas_pequeno'})
    asignaciones06 = leer_csv(rutas['06_asignaciones_exploratorias.csv'], {'grupo','k','fila_vector_0_based','cluster_provisional', 'origen','fila_csv','id_registro'})
    asignaciones07 = leer_csv(rutas['07_asignaciones_candidatos.csv'], {'grupo','k','fila_vector_0_based','cluster_provisional', 'origen','fila_csv','id_registro'})
    perfiles = leer_csv(rutas['07_perfiles_clusters.csv'], {'grupo','k','cluster_provisional','n_registros','n_academia','n_mercado','top_3_etiquetas_distintivas_descriptivas'})
    competencias = leer_csv(rutas['07_competencias_por_cluster.csv'], {'grupo','k','cluster_provisional','tipo_ranking','puesto','uri_esco','etiqueta_esco','diferencia_prevalencia'})
    panorama = leer_csv(rutas['07_panorama_candidatos.csv'], {'grupo','k','n_registros','silueta_coseno','estabilidad_ari_media','cluster_mas_pequeno','clusters_menores_5'})

    if len(indice) != 274 or Counter(f['origen'] for f in indice) != {'academia': 46, 'mercado': 228}:
        raise ValueError('El índice de entrada no corresponde a 46 perfiles y 228 ofertas (274 registros).')
    indices_esperados = set(range(len(indice)))
    for pos, row in enumerate(indice):
        if num_entero(row['fila_vector_0_based'], 'fila_vector_0_based') != pos:
            raise ValueError(f'Índice 05 no alineado en fila {pos}.')
        if row['origen'] not in ('academia', 'mercado'):
            raise ValueError(f'Origen inesperado en índice 05: {row["origen"]}')
    if len({clave_registro(r) for r in indice}) != len(indice):
        raise ValueError('Identificadores de registro duplicados en el índice 05.')

    metrica_por_key = {(r['grupo'], num_entero(r['k'], 'k')): r for r in metricas}
    panorama_por_key = {(r['grupo'], num_entero(r['k'], 'k')): r for r in panorama}
    perfil_por_key = {(r['grupo'], num_entero(r['k'], 'k'), num_entero(r['cluster_provisional'], 'cluster')): r for r in perfiles}
    combos = [('academia', 5), ('mercado', 3), ('conjunto', K_CONJUNTO_EXPLORATORIO)]
    combo_keys = set(combos)

    # Confirmar que las filas seleccionadas de paso 07 coinciden con paso 06.
    asign06 = defaultdict(dict)
    for r in asignaciones06:
        key = (r['grupo'], num_entero(r['k'], 'k'))
        if key not in combo_keys:
            continue
        idx = num_entero(r['fila_vector_0_based'], 'fila_vector_0_based')
        if idx in asign06[key]:
            raise ValueError(f'Registro duplicado en asignaciones 06 para {key}, fila {idx}')
        asign06[key][idx] = (num_entero(r['cluster_provisional'], 'cluster'), clave_registro(r))

    asign07 = defaultdict(dict)
    for r in asignaciones07:
        key = (r['grupo'], num_entero(r['k'], 'k'))
        if key not in combo_keys:
            continue
        idx = num_entero(r['fila_vector_0_based'], 'fila_vector_0_based')
        if idx in asign07[key]:
            raise ValueError(f'Registro duplicado en asignaciones 07 para {key}, fila {idx}')
        asign07[key][idx] = r

    for grupo, k in combos:
        key = (grupo, k)
        esperados = indices_esperados if grupo == 'conjunto' else {i for i,r in enumerate(indice) if r['origen'] == grupo}
        if set(asign07[key]) != esperados or set(asign06[key]) != esperados:
            raise ValueError(f'{grupo} K={k}: registros ausentes, extra o duplicados.')
        if key not in metrica_por_key or metrica_por_key[key]['estado'] != 'OK' or key not in panorama_por_key:
            raise ValueError(f'{grupo} K={k}: métricas faltantes o incorrectas.')
        conteo = Counter()
        for idx, r in asign07[key].items():
            if clave_registro(r) != clave_registro(indice[idx]):
                raise ValueError(f'{grupo} K={k}: fila {idx} difiere del índice 05.')
            cid = num_entero(r['cluster_provisional'], 'cluster')
            if not 0 <= cid < k or asign06[key][idx] != (cid, clave_registro(r)):
                raise ValueError(f'{grupo} K={k}: asignación 07 no coincide con 06.')
            conteo[cid] += 1
        if len(conteo) != k or sum(conteo.values()) != len(esperados):
            raise ValueError(f'{grupo} K={k}: faltan clusters o hay tamaños inconsistentes')
        if min(conteo.values()) != num_entero(metrica_por_key[key]['cluster_mas_pequeno'], 'mínimo'):
            raise ValueError(f'{grupo} K={k}: tamaño mínimo no coincide con métricas')
        for cid in range(k):
            pr = perfil_por_key.get((grupo,k,cid))
            if not pr or num_entero(pr['n_registros'], 'n_registros') != conteo[cid]:
                raise ValueError(f'{grupo} K={k}: tamaños no coinciden con 07_perfiles_clusters.')
    return rutas, indice, metricas, metrica_por_key, panorama, panorama_por_key, perfiles, perfil_por_key, competencias, asign07


def main() -> None:
    (rutas, indice, metricas, met, panorama, pano, perfiles, perfiles_idx, competencias, asign) = cargar_y_verificar()
    SALIDA.mkdir(parents=True, exist_ok=True)
    principal = []
    conjunto = []
    clusters_principales = []
    clusters_conjunto = []
    competencias_top = []
    combos = [('academia', K_PRINCIPALES['academia']), ('mercado', K_PRINCIPALES['mercado']), ('conjunto', K_CONJUNTO_EXPLORATORIO)]
    for grupo, k in combos:
        es_principal = grupo != 'conjunto'
        destino = principal if es_principal else conjunto
        destino_cluster = clusters_principales if es_principal else clusters_conjunto
        for idx, r in sorted(asign[(grupo,k)].items()):
            cid = int(r['cluster_provisional'])
            destino.append({
                'tipo_analisis': 'PRINCIPAL_PROVISIONAL' if es_principal else 'EXPLORATORIO_NO_PRINCIPAL',
                'grupo': grupo, 'k': k, 'cluster': cid,
                'etiqueta_propuesta_no_validada': ETIQUETAS[(grupo,k,cid)],
                'fila_vector_0_based': idx,
                'origen': r['origen'], 'fila_csv': r['fila_csv'],
                'id_registro': r['id_registro'],
                'universidad': r.get('universidad',''), 'carrera': r.get('carrera',''),
                'job_id': r.get('job_id',''), 'titulo_oferta': r.get('titulo_oferta',''),
                'n_competencias_esco': r.get('n_competencias_esco',''),
                'similitud_coseno_centroide': r.get('similitud_coseno_centroide',''),
                'estado': 'PENDIENTE_REVISION_SEMANTICA'
            })
        for cid in range(k):
            p = perfiles_idx[(grupo,k,cid)]
            destino_cluster.append({
                'tipo_analisis': 'PRINCIPAL_PROVISIONAL' if es_principal else 'EXPLORATORIO_NO_PRINCIPAL',
                'grupo': grupo, 'k': k, 'cluster': cid,
                'etiqueta_propuesta_no_validada': ETIQUETAS[(grupo,k,cid)],
                'n_registros': p['n_registros'], 'n_academia': p['n_academia'], 'n_mercado': p['n_mercado'],
                'top_3_etiquetas_distintivas': p['top_3_etiquetas_distintivas_descriptivas'],
                'ejemplos_de_registros': p.get('ejemplos_de_registros',''),
                'alertas': p.get('alertas',''),
                'validacion_humana': 'PENDIENTE',
            })
        for c in competencias:
            if c['grupo'] == grupo and int(c['k']) == k and c['tipo_ranking'] == 'distintiva_vs_resto_poblacion' and int(c['puesto']) <= 5:
                competencias_top.append({
                    'grupo': grupo, 'k': k, 'cluster': c['cluster_provisional'],
                    'etiqueta_propuesta_no_validada': ETIQUETAS[(grupo,k,int(c['cluster_provisional']))],
                    'puesto_distintivo': c['puesto'], 'uri_esco': c['uri_esco'],
                    'etiqueta_esco': c['etiqueta_esco'],
                    'registros_con_competencia_cluster': c.get('registros_con_competencia_cluster',''),
                    'registros_del_cluster': c.get('registros_del_cluster',''),
                    'proporcion_dentro': c.get('proporcion_dentro',''),
                    'proporcion_fuera': c.get('proporcion_fuera',''),
                    'diferencia_prevalencia': c['diferencia_prevalencia'],
                    'advertencia': 'DISTINTIVIDAD_DE_ESCO_NO_ES_COBERTURA'
                })

    # Tabla comparativa completa: evitar ocultar K de mejor silueta.
    comparacion = []
    for r in panorama:
        g = r['grupo']; k = int(r['k'])
        if g not in ('academia','mercado','conjunto'):
            continue
        if (g,k) in (('academia',5),('mercado',3)):
            decision = 'SELECCION_PRINCIPAL_PROVISIONAL'
        elif (g,k) == ('conjunto',4):
            decision = 'SOLO_EXPLORATORIO'
        else:
            decision = 'ALTERNATIVA_NO_SELECCIONADA'
        comparacion.append({
            'grupo': g, 'k': k, 'n_registros': r['n_registros'],
            'silueta_coseno': r['silueta_coseno'],
            'estabilidad_ari_media': r['estabilidad_ari_media'],
            'estabilidad_ari_min': r.get('estabilidad_ari_min',''),
            'cluster_mas_pequeno': r['cluster_mas_pequeno'],
            'cluster_mas_grande': r['cluster_mas_grande'],
            'clusters_menores_5': r['clusters_menores_5'],
            'decision': decision
        })

    columnas_asig = list(principal[0].keys())
    guardar_csv(SALIDA/'08_asignaciones_principales.csv', principal, columnas_asig)
    guardar_csv(SALIDA/'08_asignaciones_conjunto_exploratorio.csv', conjunto, columnas_asig)
    columnas_clusters = list(clusters_principales[0].keys())
    guardar_csv(SALIDA/'08_clusters_principales.csv', clusters_principales, columnas_clusters)
    guardar_csv(SALIDA/'08_clusters_conjunto_exploratorio.csv', clusters_conjunto, columnas_clusters)
    guardar_csv(SALIDA/'08_comparacion_k.csv', comparacion, list(comparacion[0]))
    guardar_csv(SALIDA/'08_competencias_distintivas.csv', competencias_top, list(competencias_top[0]))

    # Plantilla humana independiente y persistente: no se sobreescribe si ya existe.
    plantilla = SALIDA/'08_revision_humana_clusters.csv'
    if not plantilla.exists():
        revision = [{
            'grupo': c['grupo'], 'k': c['k'], 'cluster': c['cluster'],
            'etiqueta_propuesta_no_validada': c['etiqueta_propuesta_no_validada'],
            'decision_humana': 'PENDIENTE',
            'etiqueta_validada': '', 'evidencia_revisada': '', 'observaciones': '',
            'responsable_revision': '', 'fecha_revision': ''
        } for c in clusters_principales]
        guardar_csv(plantilla, revision, list(revision[0]))
        plantilla_estado = 'CREADA'
    else:
        plantilla_estado = 'CONSERVADA_SIN_SOBRESCRIBIR'

    # Resumen legible en Markdown.
    informe = [
        '# Obj2 · Actividad 3 — Paso 08: selección de K de trabajo', '',
        '## Alcance',
        'Decisión **provisional y reproducible** sobre particiones existentes del paso 06, interpretadas en paso 07.',
        'El programa no ejecuta K-Means, no mide cobertura curricular ni valida la normalización ESCO original.',
        'La semilla de referencia para las asignaciones ya calculadas es 42; los IDs de clusters solo valen dentro de cada población y K.', '',
        '## Decisiones', '',
        '| Población | Uso | K | Silueta coseno | ARI medio | Tamaños |',
        '|---|---|---:|---:|---:|---|',
    ]
    for grupo,k in combos:
        r = met[(grupo,k)]
        tamaños = [int(perfiles_idx[(grupo,k,i)]['n_registros']) for i in range(k)]
        uso = 'Principal provisional' if grupo != 'conjunto' else 'Exploratorio solamente'
        informe.append(f"| {grupo} | {uso} | {k} | {float(r['silueta_coseno']):.3f} | {float(r['estabilidad_ari_media']):.3f} | {', '.join(map(str,tamaños))} |")
    informe += [
        '', '### Academia: K=5',
        'Entre K=5, 7 y 8, se escoge K=5 como solución de trabajo por estabilidad alta,',
        'mínimo seis carreras por grupo y mejor legibilidad interpretativa. K=7 y K=8',
        'tienen mayor silueta, pero crean respectivamente 3 y 4 clusters de menos de cinco carreras.',
        'Se debe revisar especialmente el grupo académico heterogéneo de informática y otras ingenierías.',
        '', '### Mercado: K=3',
        'K=2 tiene mayor silueta (aprox. 0,283), pero concentra 181 ofertas en un solo grupo.',
        'K=3 reduce la silueta (aprox. 0,212), a cambio de separar de manera exploratoria',
        'analítica, operaciones/mantenimiento y gestión de proyectos. El ARI medio permanece alto',
        '(aprox. 0,972) y ningún grupo es pequeño. **No** debe presentarse como K matemáticamente óptimo.',
        '', '### Conjunto: K=4 solo exploratorio',
        'Permite diferenciar una familia minera (7 carreras y 21 ofertas), pero su estabilidad',
        'es menor que la de K=3 y contiene 228 ofertas frente a 46 carreras.',
        'No se usará para inferir cobertura ni emparejamiento currículo-empleo.',
        '', '## Clusters principales y etiquetas de trabajo', '',
        '| Población | Cluster (local) | n | Nombre propuesto, **no validado** |',
        '|---|---:|---:|---|',
    ]
    for r in clusters_principales:
        informe.append(f"| {r['grupo']} | {r['cluster']} | {r['n_registros']} | {r['etiqueta_propuesta_no_validada']} |")
    informe += [
        '', '## Limitaciones obligatorias',
        '- Los mapeos ESCO originales siguen pendientes de revisión humana; estas etiquetas pueden cambiar.',
        '- 14 ofertas sin competencias ESCO siguen fuera de la matriz; 228 de 242 ofertas fueron representadas.',
        '- Los promedios de embeddings no ponderan competencias y no equivalen a porcentajes de cobertura.',
        '- Las competencias distintivas se ordenan por diferencia de prevalencia en el propio conjunto; no prueban pertinencia laboral.',
        '- Los clusters principales se ajustaron separadamente. Sus números no son equivalentes ni comparables entre academia y mercado.',
        '- Las agrupaciones están condicionadas por el extractor ESCO, su límite de competencias y la composición de la muestra.',
        '', '## Revisión humana pendiente',
        'Completar `08_revision_humana_clusters.csv`: confirmar/corregir etiquetas, auditar evidencias originales',
        'y justificar la utilidad para el objetivo de la tesis. No borrar registros solo por pertenecer a un grupo.',
        '', '## Siguiente paso',
        'Visualización descriptiva, preferentemente mapas PCA/UMAP distinguiendo origen, con la advertencia',
        'de que las proyecciones 2D pueden distorsionar distancias. La cobertura deberá modelarse aparte.',
    ]
    (SALIDA/'08_informe_decision_k.md').write_text('\n'.join(informe)+'\n', encoding='utf-8')

    resumen = {
        'etapa': 'Obj2 / Act. 3 / Paso 08',
        'estado': 'K_DE_TRABAJO_PROVISIONALES_PENDIENTES_VALIDACION_HUMANA',
        'decisiones': {'academia': {'k':5,'tipo':'PRINCIPAL_PROVISIONAL'},
                       'mercado': {'k':3,'tipo':'PRINCIPAL_PROVISIONAL'},
                       'conjunto': {'k':4,'tipo':'EXPLORATORIO_NO_PRINCIPAL'}},
        'n_registros_principales': len(principal),
        'n_registros_conjunto_exploratorio': len(conjunto),
        'n_clusters_principales': len(clusters_principales),
        'n_clusters_conjunto_exploratorio': len(clusters_conjunto),
        'n_competencias_distintivas_exportadas': len(competencias_top),
        'plantilla_revision': plantilla_estado,
        'semilla_de_particiones_reutilizadas': 42,
        'entradas_sha256': {nombre:sha256(p) for nombre,p in rutas.items()},
        'alertas': [
            'No es una selección automática de K ni una validación humana de los clusters.',
            'Los 14 anuncios sin ESCO no se representaron; no inferir ausencia de competencias.',
            'Las asignaciones de clusters de poblaciones diferentes NO son directamente comparables.',
            'No se calculó cobertura curricular ni similitud academia-mercado.',
        ]
    }
    (SALIDA/'08_resumen_decision_k.json').write_text(json.dumps(resumen,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

    print('\nPASO 08 — K DE TRABAJO PROVISIONALES')
    for grupo,k in combos:
        r = met[(grupo,k)]
        uso = 'PRINCIPAL PROVISIONAL' if grupo != 'conjunto' else 'SOLO EXPLORATORIO'
        print(f"  {grupo:8s} K={k} ({uso}) | silueta={float(r['silueta_coseno']):.3f} | ARI={float(r['estabilidad_ari_media']):.3f}")
    print('\nPASO 08 FINALIZADO CORRECTAMENTE')
    print(f'  Asignaciones principales: {len(principal)} (46 académicas + 228 laborales)')
    print(f'  Clusters principales: {len(clusters_principales)} (5 + 3)')
    print(f'  Conjunto exploratorio: {len(conjunto)} registros, {len(clusters_conjunto)} clusters')
    print(f'  Plantilla de revisión humana: {plantilla_estado}')
    print(f'  Salida: {SALIDA}')
    print('  IMPORTANTE: nombres y K provisionales. Sin cobertura curricular ni validación ESCO.')


if __name__ == '__main__':
    try:
        main()
    except (FileNotFoundError, ValueError, KeyError, OSError, json.JSONDecodeError) as error:
        print(f'\nERROR EN PASO 08: {error}')
        print('Verifica que 08_fijar_k_trabajo.py esté en Obj2/Act. 3/ y que existan')
        print('salida_vectores_registros/, salida_evaluacion_kmeans/ y salida_inspeccion_clusters/.')
        raise
