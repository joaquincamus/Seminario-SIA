# -*- coding: utf-8 -*-
"""
OBJ2 / ACTIVIDAD 3 / PASO 09
Visualizacion descriptiva de particiones K-Means mediante PCA 2D.

Uso en Visual Studio Code: abre este archivo desde Obj2/Act. 3 y presiona
el boton triangular ▶ «Ejecutar archivo Python».

Entradas (rutas relativas a ESTE archivo, no al directorio de la terminal):
  salida_vectores_registros/05_vectores_registros.npy
  salida_vectores_registros/05_indice_registros.csv
  salida_seleccion_k/08_asignaciones_principales.csv
  salida_seleccion_k/08_asignaciones_conjunto_exploratorio.csv
  salida_seleccion_k/08_clusters_principales.csv
  salida_seleccion_k/08_clusters_conjunto_exploratorio.csv

Salida: salida_visualizacion_pca/
No reentrena K-Means. NO calcula similitud academia-mercado ni cobertura.
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # funciona desde el boton ▶ sin abrir ventanas bloqueantes
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from sklearn.decomposition import PCA

BASE = Path(__file__).resolve().parent
DIR_VEC = BASE / 'salida_vectores_registros'
DIR_K = BASE / 'salida_seleccion_k'
SALIDA = BASE / 'salida_visualizacion_pca'

ENTRADAS = {
    'matriz': DIR_VEC / '05_vectores_registros.npy',
    'indice': DIR_VEC / '05_indice_registros.csv',
    'asignaciones': DIR_K / '08_asignaciones_principales.csv',
    'asignaciones_conjunto': DIR_K / '08_asignaciones_conjunto_exploratorio.csv',
    'clusters': DIR_K / '08_clusters_principales.csv',
    'clusters_conjunto': DIR_K / '08_clusters_conjunto_exploratorio.csv',
}

EXPECTED_K = {'academia': 5, 'mercado': 3, 'conjunto': 4}
EXPECTED_N = {'academia': 46, 'mercado': 228, 'conjunto': 274}


def check(cond: bool, msg: str) -> None:
    if not bool(cond):
        raise ValueError(msg)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def leer_csv(path: Path) -> pd.DataFrame:
    # Todos los CSV originales de estos pasos usan ';'.
    return pd.read_csv(path, sep=';', encoding='utf-8-sig', dtype=str,
                       keep_default_na=False)


def entero_col(d: pd.DataFrame, name: str, desc: str) -> None:
    check(name in d.columns, f'{desc}: falta la columna {name!r}')
    try:
        d[name] = pd.to_numeric(d[name], errors='raise').astype(int)
    except Exception as e:
        raise ValueError(f'{desc}: {name!r} debe contener enteros: {e}') from e


def comprobar_asignacion(a: pd.DataFrame, idx: pd.DataFrame,
                         grupos: list[str], desc: str) -> pd.DataFrame:
    requeridas = ['fila_vector_0_based', 'id_registro', 'origen', 'grupo',
                  'k', 'cluster', 'etiqueta_propuesta_no_validada']
    check(set(requeridas).issubset(a.columns), f'{desc}: faltan columnas: {set(requeridas)-set(a.columns)}')
    for k in ['fila_vector_0_based', 'k', 'cluster']:
        entero_col(a, k, desc)
    n = len(idx)
    check(len(a) == n, f'{desc}: se esperaban {n} filas, aparecen {len(a)}')
    check(a['fila_vector_0_based'].is_unique, f'{desc}: hay filas_vector duplicadas')
    check(set(a['fila_vector_0_based']) == set(range(n)), f'{desc}: faltan o sobran indices de vector')
    a = a.sort_values('fila_vector_0_based').reset_index(drop=True)
    check((a['id_registro'].to_numpy() == idx['id_registro'].to_numpy()).all(),
          f'{desc}: el identificador del registro no coincide con la matriz del paso 5')
    check((a['origen'].to_numpy() == idx['origen'].to_numpy()).all(),
          f'{desc}: el origen no coincide con el indice del paso 5')
    check(set(a['grupo']) == set(grupos), f'{desc}: grupos inesperados {set(a["grupo"])}')
    for grupo in grupos:
        sub = a[a['grupo'] == grupo]
        check(len(sub) == EXPECTED_N[grupo], f'{desc}: se esperaban {EXPECTED_N[grupo]} para {grupo}')
        check((sub['k'] == EXPECTED_K[grupo]).all(),
              f'{desc}: K incorrecto para {grupo}; se esperaba {EXPECTED_K[grupo]}')
        check(set(sub['cluster']) == set(range(EXPECTED_K[grupo])),
              f'{desc}: IDs de clusters incompletos en {grupo}')
        if grupo != 'conjunto':
            check((sub['origen'] == grupo).all(), f'{desc}: registros de otro origen en {grupo}')
    return a


def comprobar_catalogo(clusters: pd.DataFrame, asignaciones: pd.DataFrame,
                        grupos: list[str], desc: str) -> dict:
    req = ['grupo', 'k', 'cluster', 'etiqueta_propuesta_no_validada', 'n_registros']
    check(set(req).issubset(clusters.columns), f'{desc}: faltan columnas')
    for c in ['k', 'cluster', 'n_registros']:
        entero_col(clusters, c, desc)
    labels = {}
    for _, r in clusters.iterrows():
        key = (r['grupo'], int(r['cluster']))
        check(key not in labels, f'{desc}: cluster duplicado {key}')
        check(r['grupo'] in grupos, f'{desc}: grupo inesperado {key}')
        check(r['k'] == EXPECTED_K[r['grupo']], f'{desc}: K incorrecto {key}')
        real = int(((asignaciones['grupo'] == r['grupo']) &
                    (asignaciones['cluster'] == r['cluster'])).sum())
        check(real == int(r['n_registros']),
              f'{desc}: tamaño distinto en {key}: archivo={r["n_registros"]}, real={real}')
        labels[key] = str(r['etiqueta_propuesta_no_validada']).strip()
    expected = {(g, c) for g in grupos for c in range(EXPECTED_K[g])}
    check(set(labels) == expected, f'{desc}: no se documentaron los clusters esperados')
    return labels


def preparar() -> tuple[np.ndarray, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict, dict]:
    faltan = [str(p) for p in ENTRADAS.values() if not p.exists()]
    if faltan:
        raise FileNotFoundError('Faltan entradas del paso 05 u 08:\n  ' +
                                '\n  '.join(faltan) +
                                '\nEjecuta los scripts 05 y 08 antes de este paso.')
    x = np.load(ENTRADAS['matriz'], allow_pickle=False)
    idx = leer_csv(ENTRADAS['indice'])
    check(x.ndim == 2 and x.shape[1] == 384, f'Matriz con forma inesperada: {x.shape}')
    check(len(x) == 274 and len(idx) == 274, 'Se esperan 274 registros en la matriz y el indice')
    check(np.isfinite(x).all(), 'La matriz contiene NaN o infinitos')
    norms = np.linalg.norm(x, axis=1)
    check(np.allclose(norms, 1.0, atol=2e-4), 'La matriz tiene vectores sin normalizar')
    entero_col(idx, 'fila_vector_0_based', '05_indice_registros')
    idx = idx.sort_values('fila_vector_0_based').reset_index(drop=True)
    check(idx['fila_vector_0_based'].tolist() == list(range(274)),
          'El indice 05 no corresponde a filas consecutivas 0..273')
    check(idx['id_registro'].is_unique, 'El indice 05 contiene identificadores duplicados')
    check(idx['origen'].value_counts().to_dict() == {'academia':46, 'mercado':228},
          'El indice 05 no tiene las 46 carreras y 228 ofertas esperadas')

    a = comprobar_asignacion(leer_csv(ENTRADAS['asignaciones']), idx,
                            ['academia', 'mercado'], '08_asignaciones_principales')
    b = comprobar_asignacion(leer_csv(ENTRADAS['asignaciones_conjunto']), idx,
                            ['conjunto'], '08_asignaciones_conjunto_exploratorio')
    l_main = comprobar_catalogo(leer_csv(ENTRADAS['clusters']), a,
                                ['academia', 'mercado'], '08_clusters_principales')
    l_mix = comprobar_catalogo(leer_csv(ENTRADAS['clusters_conjunto']), b,
                               ['conjunto'], '08_clusters_conjunto_exploratorio')
    return x, idx, a, b, l_main, l_mix


def proyectar(x: np.ndarray, filas: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    # PCA se reajusta para CADA panel: no se comparan las coordenadas entre paneles.
    pca = PCA(n_components=2, svd_solver='full')
    xy = pca.fit_transform(x[filas])
    return xy, pca.explained_variance_ratio_


def graficar(grupo: str, xy: np.ndarray, sub: pd.DataFrame, labels: dict,
              ratio: np.ndarray, ruta: Path) -> None:
    plt.rcParams['font.family'] = 'DejaVu Sans'
    fig, ax = plt.subplots(figsize=(12.8, 7.7))
    fig.patch.set_facecolor('#FFFFFF')
    ax.set_facecolor('#FAFBFD')
    cmap = plt.get_cmap('tab10')
    ks = sorted(sub['cluster'].unique())
    for k in ks:
        mask = sub['cluster'].to_numpy() == k
        ax.scatter(xy[mask, 0], xy[mask, 1], s=50, alpha=0.77,
                   edgecolors='white', linewidths=0.45, color=cmap(k),
                   label=f'C{k} · n={mask.sum()} · {labels[(grupo, k)]}')
    title = {
        'academia': 'Perfiles académicos · K=5 provisional (n=46)',
        'mercado': 'Ofertas laborales · K=3 provisional (n=228)',
    }[grupo]
    ax.set_title(title, fontsize=16, fontweight='bold', loc='left', pad=18)
    ax.set_xlabel(f'Componente principal 1 ({ratio[0]:.1%} de la varianza)')
    ax.set_ylabel(f'Componente principal 2 ({ratio[1]:.1%} de la varianza)')
    ax.grid(alpha=0.25, linestyle='--')
    ax.set_axisbelow(True)
    ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.135),
              fontsize=9, frameon=False, ncol=1 if grupo=='academia' else 2,
              markerscale=1.1)
    fig.text(.06, .018,
             f'PCA 2D: {ratio.sum():.1%} varianza explicada. Grupos obtenidos en 384D; '
             'la proyección 2D puede alterar las distancias. Sin validación semántica ni cobertura.',
             fontsize=8.3, color='#555555')
    fig.subplots_adjust(left=.09, right=.96, top=.87, bottom=.30 if grupo=='academia' else .26)
    fig.savefig(ruta, dpi=190, facecolor='white')
    plt.close(fig)


def graficar_conjunto(xy: np.ndarray, sub: pd.DataFrame, labels: dict,
                      ratio: np.ndarray, ruta: Path) -> None:
    fig, ax = plt.subplots(figsize=(12.8, 8.0))
    ax.set_facecolor('#FAFBFD')
    cmap = plt.get_cmap('tab10')
    for k in sorted(sub['cluster'].unique()):
        for origen, marker, size in [('mercado','o',48), ('academia','^',105)]:
            mask = ((sub['cluster'] == k) & (sub['origen'] == origen)).to_numpy()
            if not mask.any():
                continue
            ax.scatter(xy[mask,0], xy[mask,1], s=size, marker=marker,
                       color=cmap(k), edgecolors='white', linewidths=.65,
                       alpha=.80 if origen == 'mercado' else .93)
    cluster_handles = [Line2D([0], [0], color=plt.get_cmap('tab10')(k), marker='o',
                              linestyle='None', markersize=9,
                              label=f'C{k} · n={(sub["cluster"] == k).sum()} · {labels[("conjunto",k)]}')
                       for k in range(4)]
    origin_handles = [Line2D([0],[0],marker='^', color='gray', linestyle='None',
                             markersize=9, label='Carrera académica (46)'),
                      Line2D([0],[0],marker='o', color='gray', linestyle='None',
                             markersize=9, label='Oferta laboral (228)')]
    ax.set_title('Conjunto exploratorio · K=4 (n=274)', fontsize=16,
                 fontweight='bold', loc='left', pad=18)
    ax.set_xlabel(f'Componente principal 1 ({ratio[0]:.1%} de la varianza)')
    ax.set_ylabel(f'Componente principal 2 ({ratio[1]:.1%} de la varianza)')
    ax.grid(alpha=.25, linestyle='--')
    ax.set_axisbelow(True)
    l1 = ax.legend(handles=cluster_handles, loc='upper center',
                   bbox_to_anchor=(.5,-.13), fontsize=9, frameon=False, ncol=2)
    ax.add_artist(l1)
    fig.legend(handles=origin_handles, loc='lower center', bbox_to_anchor=(.5,.085),
               frameon=False, ncol=2, fontsize=9)
    fig.text(.06,.018,
             f'PCA 2D: {ratio.sum():.1%} varianza explicada. '
             'Grupo conjunto solo exploratorio; muestra 228 ofertas vs. 46 carreras. '
             'La cercanía 2D NO indica cobertura.',
             fontsize=8.2, color='#555555')
    fig.subplots_adjust(left=.09, right=.96, top=.88, bottom=.30)
    fig.savefig(ruta, dpi=190, facecolor='white')
    plt.close(fig)


def graficar_origen(xy: np.ndarray, sub: pd.DataFrame, ratio: np.ndarray, ruta: Path) -> None:
    fig, ax = plt.subplots(figsize=(11.5, 7.2))
    ax.set_facecolor('#FAFBFD')
    for origen, marker, s, color, name in [
        ('mercado','o',45,'#3D79B4','Ofertas laborales (228)'),
        ('academia','^',95,'#E58E42','Carreras académicas (46)')
    ]:
        mask = (sub['origen'] == origen).to_numpy()
        ax.scatter(xy[mask,0], xy[mask,1], color=color, s=s, marker=marker,
                   alpha=.77, edgecolors='white', linewidths=.6, label=name)
    ax.set_title('Vista global: procedencia de registros (PCA conjunto)',
                 fontsize=15, fontweight='bold', loc='left', pad=18)
    ax.set_xlabel(f'Componente principal 1 ({ratio[0]:.1%} de la varianza)')
    ax.set_ylabel(f'Componente principal 2 ({ratio[1]:.1%} de la varianza)')
    ax.grid(alpha=.25, linestyle='--')
    ax.set_axisbelow(True)
    ax.legend(loc='upper center', bbox_to_anchor=(.5,-.12), ncol=2, frameon=False)
    fig.text(.07,.022,
             'Misma proyección PCA que en el gráfico del conjunto K=4. '
             'Visualización descriptiva: no es un análisis de brechas ni de cobertura.',
             fontsize=8.3, color='#555555')
    fig.subplots_adjust(left=.10,right=.97,top=.86,bottom=.22)
    fig.savefig(ruta, dpi=190, facecolor='white')
    plt.close(fig)


def main() -> None:
    x, idx, a, b, labels, labels_conj = preparar()
    SALIDA.mkdir(parents=True, exist_ok=True)
    fila_csv = []
    estad = []
    print('PASO 09 - ENTRADAS VERIFICADAS')
    print(f'  Matriz: {x.shape[0]} registros x {x.shape[1]} dimensiones')
    print('  Academia K=5; mercado K=3; conjunto K=4 (solo exploratorio)')
    for grupo, tabla, lmap, destino in [
        ('academia', a, labels, '09_pca_academia_k5.png'),
        ('mercado', a, labels, '09_pca_mercado_k3.png'),
        ('conjunto', b, labels_conj, '09_pca_conjunto_k4_exploratorio.png')
    ]:
        sub = tabla[tabla['grupo'] == grupo].sort_values('fila_vector_0_based').reset_index(drop=True)
        filas = sub['fila_vector_0_based'].to_numpy(dtype=int)
        xy, ratio = proyectar(x, filas)
        for i, r in sub.iterrows():
            fila_csv.append({
                'grupo_proyeccion': grupo,
                'tipo_analisis': 'EXPLORATORIO_NO_PRINCIPAL' if grupo=='conjunto' else 'PRINCIPAL_PROVISIONAL',
                'fila_vector_0_based': int(r['fila_vector_0_based']),
                'origen': r['origen'],
                'id_registro': r['id_registro'],
                'universidad': r.get('universidad',''),
                'carrera': r.get('carrera',''),
                'job_id': r.get('job_id',''),
                'titulo_oferta': r.get('titulo_oferta',''),
                'k': int(r['k']),
                'cluster': int(r['cluster']),
                'etiqueta_propuesta_no_validada': r['etiqueta_propuesta_no_validada'],
                'pca_1': float(xy[i,0]),
                'pca_2': float(xy[i,1]),
            })
        estad.append({'grupo':grupo, 'n':len(sub), 'k':EXPECTED_K[grupo],
                      'pca_varianza_1':float(ratio[0]),
                      'pca_varianza_2':float(ratio[1]),
                      'pca_varianza_acumulada':float(ratio.sum()),
                      'pca_reajustado_en_poblacion': grupo,
                      'advertencia':'No comparar coordenadas de PCA ajustados en diferentes poblaciones'})
        if grupo == 'conjunto':
            graficar_conjunto(xy, sub, lmap, ratio, SALIDA/destino)
            graficar_origen(xy, sub, ratio, SALIDA/'09_pca_conjunto_por_origen.png')
        else:
            graficar(grupo, xy, sub, lmap, ratio, SALIDA/destino)
        print(f'  {grupo:<9} PCA 2D varianza explicada: {ratio.sum():.1%}; '
              f'gráfico: {destino}')

    pd.DataFrame(fila_csv).to_csv(SALIDA/'09_coordenadas_pca.csv',
                                  sep=';', index=False, encoding='utf-8-sig',
                                  float_format='%.9f')
    pd.DataFrame(estad).to_csv(SALIDA/'09_diagnostico_pca.csv',
                               sep=';', index=False, encoding='utf-8-sig',
                               float_format='%.9f')
    meta = {
        'paso': 9,
        'estado': 'PROYECCIONES_DESCRIPTIVAS_SIN_VALIDACION_SEMANTICA',
        'poblaciones': estad,
        'metodo': 'PCA(n_components=2, svd_solver=full), ajustado separadamente en cada poblacion',
        'entrada_matriz': '05_vectores_registros.npy (embeddings agregados L2, 384D)',
        'reutiliza_clustering': 'Paso 08; no reentrena KMeans',
        'conteo_filas_coordenadas': len(fila_csv),
        'entradas_sha256': {p.name: sha256(p) for p in ENTRADAS.values()},
        'alertas': [
            'PCA 2D puede distorsionar distancias y vecindades en 384 dimensiones.',
            'Cada poblacion usa su propio PCA; no comparar coordenadas entre paneles.',
            'La particion conjunta es solo exploratoria, con 228 ofertas vs 46 carreras.',
            'Los nombres de clusters son provisionales y ESCO no esta validado humanamente.',
            'No se ha estimado cobertura, brecha curricular ni similitud programa-oferta.'
        ]
    }
    (SALIDA/'09_resumen_visualizacion.json').write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')
    print('\nPASO 09 FINALIZADO CORRECTAMENTE')
    print(f'  Archivos generados en: {SALIDA}')
    print('  Gráficos: academia, mercado, conjunto K=4 y conjunto por origen')
    print('  Tablas: 09_coordenadas_pca.csv y 09_diagnostico_pca.csv')
    print('  Importante: PCA visualiza; no valida clusters ni calcula cobertura curricular.')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, FileNotFoundError, KeyError) as exc:
        print('\nERROR EN EL PASO 09:', exc)
        print('Revisa que 09_visualizar_clusters_pca.py este dentro de Obj2/Act. 3/ '
              'y que ahi existan salida_vectores_registros/ y salida_seleccion_k/.')
        sys.exit(1)
