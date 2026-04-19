"""
core/batch.py
Generación en lote desde un archivo CSV.
Lee múltiples combinaciones de parámetros y genera cada pieza automáticamente.
"""

import adsk.core
import adsk.fusion
import traceback
import csv
import os
import datetime
from . import modelo
from . import exportador


# ═══════════════════════════════════════════════════════
# LECTURA DEL CSV
# ═══════════════════════════════════════════════════════

COLUMNAS_REQUERIDAS = {'tipo', 'largo', 'ancho', 'alto'}
COLUMNAS_OPCIONALES = {'filete': 2.0, 'tolerancia': 0.2, 'exportar': 'stl'}


def leer_csv(ruta):
    """
    Lee el CSV y retorna (filas_validas, errores).
    Cada fila válida es un dict con los parámetros de la pieza.
    """
    filas   = []
    errores = []

    if not os.path.exists(ruta):
        return [], [f'Archivo no encontrado: {ruta}']

    try:
        with open(ruta, encoding='utf-8-sig', newline='') as f:
            reader = csv.DictReader(f)

            # Verificar columnas requeridas
            if not reader.fieldnames:
                return [], ['El CSV está vacío o no tiene encabezados.']

            cols_presentes = {c.strip().lower() for c in reader.fieldnames}
            cols_faltantes = COLUMNAS_REQUERIDAS - cols_presentes
            if cols_faltantes:
                return [], [f'Columnas faltantes en el CSV: {", ".join(cols_faltantes)}']

            for i, fila in enumerate(reader, start=2):
                fila_limpia = {k.strip().lower(): v.strip() for k, v in fila.items() if k}
                ok, resultado = _validar_fila(fila_limpia, i)
                if ok:
                    filas.append(resultado)
                else:
                    errores.append(resultado)

    except Exception as e:
        return [], [f'Error al leer el CSV: {e}']

    return filas, errores


def _validar_fila(fila, numero):
    """Valida y convierte una fila del CSV. Retorna (ok, dict_params o msg_error)."""
    try:
        params = {
            'tipo':         fila.get('tipo', 'Caja simple'),
            'largo':        float(fila['largo'])        / 10,  # mm → cm
            'ancho':        float(fila['ancho'])        / 10,
            'alto':         float(fila['alto'])         / 10,
            'radio_filete': float(fila.get('filete', COLUMNAS_OPCIONALES['filete'])) / 10,
            'tolerancia':   float(fila.get('tolerancia', COLUMNAS_OPCIONALES['tolerancia'])) / 10,
            'tiene_filete': float(fila.get('filete', 2.0)) > 0,
            'exportar_stl': True,
            'formatos':     fila.get('exportar', 'stl').lower().split('+'),
        }

        # Validaciones básicas
        if params['largo'] <= 0 or params['ancho'] <= 0 or params['alto'] <= 0:
            return False, f'Fila {numero}: dimensiones deben ser mayores a 0.'
        if max(params['largo'], params['ancho'], params['alto']) > 100:
            return False, f'Fila {numero}: dimensión máxima 1000mm.'

        return True, params

    except ValueError as e:
        return False, f'Fila {numero}: valor inválido — {e}'
    except KeyError as e:
        return False, f'Fila {numero}: columna faltante — {e}'


# ═══════════════════════════════════════════════════════
# EJECUCIÓN BATCH
# ═══════════════════════════════════════════════════════

def ejecutar_batch(ruta_csv, progreso_callback=None):
    """
    Lee el CSV y genera cada pieza en Fusion.
    progreso_callback(actual, total, nombre) — para actualizar la UI.
    Retorna (exitosos, fallidos, reporte)
    """
    app    = adsk.core.Application.get()
    design = app.activeProduct

    filas, errores_csv = leer_csv(ruta_csv)

    if not filas:
        return 0, 0, {'errores_csv': errores_csv, 'piezas': []}

    total    = len(filas)
    exitosos = 0
    fallidos = 0
    reporte  = {'errores_csv': errores_csv, 'piezas': []}

    for i, params in enumerate(filas):
        nombre = f'{params["tipo"]}_{i+1}'
        if progreso_callback:
            progreso_callback(i + 1, total, nombre)

        try:
            # Limpiar el diseño antes de cada pieza
            _limpiar_cuerpos(design)

            # Generar la pieza
            modelo.crear_modelo_desde_params(design, params)

            # Exportar en los formatos pedidos
            rutas = exportador.exportar_batch(
                app, design,
                nombre_pieza=nombre,
                formatos=params['formatos']
            )

            reporte['piezas'].append({
                'nombre': nombre,
                'estado': 'ok',
                'rutas':  rutas
            })
            exitosos += 1

        except Exception as e:
            reporte['piezas'].append({
                'nombre': nombre,
                'estado': 'error',
                'error':  str(e)
            })
            fallidos += 1

    return exitosos, fallidos, reporte


def _limpiar_cuerpos(design):
    """Elimina todos los cuerpos del diseño para empezar limpio."""
    root = design.rootComponent
    cuerpos = root.bRepBodies
    for i in range(cuerpos.count - 1, -1, -1):
        cuerpos.item(i).deleteMe()


# ═══════════════════════════════════════════════════════
# REPORTE
# ═══════════════════════════════════════════════════════

def generar_reporte(exitosos, fallidos, reporte, ruta_csv):
    """Genera un archivo de reporte TXT con el resultado del batch."""
    carpeta = os.path.join(os.path.expanduser('~'), 'Documents', 'FusionCAD', 'Reportes')
    os.makedirs(carpeta, exist_ok=True)

    ts     = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    ruta   = os.path.join(carpeta, f'reporte_batch_{ts}.txt')
    total  = exitosos + fallidos

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(f'REPORTE BATCH — {ts}\n')
        f.write(f'CSV: {ruta_csv}\n')
        f.write(f'{'─'*50}\n')
        f.write(f'Total: {total} | Exitosos: {exitosos} | Fallidos: {fallidos}\n\n')

        if reporte.get('errores_csv'):
            f.write('ERRORES EN EL CSV:\n')
            for e in reporte['errores_csv']:
                f.write(f'  ⚠ {e}\n')
            f.write('\n')

        f.write('PIEZAS GENERADAS:\n')
        for p in reporte['piezas']:
            estado = '✓' if p['estado'] == 'ok' else '✗'
            f.write(f'  {estado} {p["nombre"]}\n')
            if p['estado'] == 'ok':
                for fmt, ruta_stl in p.get('rutas', {}).items():
                    f.write(f'      {fmt.upper()}: {ruta_stl}\n')
            else:
                f.write(f'      Error: {p["error"]}\n')

    return ruta
