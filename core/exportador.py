"""
core/exportador.py
Exportación automática de modelos: STL, STEP, F3D.
"""

import adsk.core
import adsk.fusion
import os
import datetime


# Carpeta base de exportación (en Documentos del usuario)
def _carpeta_base():
    return os.path.join(os.path.expanduser('~'), 'Documents', 'FusionCAD')


def _timestamp():
    return datetime.datetime.now().strftime('%Y%m%d_%H%M%S')


def exportar_stl(app, design, nombre_pieza='pieza', refinamiento='medio'):
    """
    Exporta el modelo activo como STL binario.
    Retorna la ruta del archivo generado.

    refinamiento: 'bajo' | 'medio' | 'alto'
    """
    niveles = {
        'bajo':  adsk.fusion.MeshRefinementSettings.MeshRefinementLow,
        'medio': adsk.fusion.MeshRefinementSettings.MeshRefinementMedium,
        'alto':  adsk.fusion.MeshRefinementSettings.MeshRefinementHigh,
    }

    carpeta = os.path.join(_carpeta_base(), 'STL')
    os.makedirs(carpeta, exist_ok=True)

    nombre = _limpiar_nombre(nombre_pieza)
    ruta   = os.path.join(carpeta, f'{nombre}_{_timestamp()}.stl')

    exp_mgr  = design.exportManager
    stl_opts = exp_mgr.createSTLExportOptions(design.rootComponent)
    stl_opts.filename       = ruta
    stl_opts.meshRefinement = niveles.get(refinamiento, niveles['medio'])
    stl_opts.isBinaryFormat = True
    exp_mgr.execute(stl_opts)

    return ruta


def exportar_step(app, design, nombre_pieza='pieza'):
    """Exporta como STEP (para intercambio con otros programas CAD)."""
    carpeta = os.path.join(_carpeta_base(), 'STEP')
    os.makedirs(carpeta, exist_ok=True)

    nombre = _limpiar_nombre(nombre_pieza)
    ruta   = os.path.join(carpeta, f'{nombre}_{_timestamp()}.step')

    exp_mgr   = design.exportManager
    step_opts = exp_mgr.createSTEPExportOptions(ruta)
    exp_mgr.execute(step_opts)

    return ruta


def exportar_f3d(app, design, nombre_pieza='pieza'):
    """Exporta como F3D (formato nativo de Fusion, incluye historial)."""
    carpeta = os.path.join(_carpeta_base(), 'F3D')
    os.makedirs(carpeta, exist_ok=True)

    nombre = _limpiar_nombre(nombre_pieza)
    ruta   = os.path.join(carpeta, f'{nombre}_{_timestamp()}.f3d')

    exp_mgr  = design.exportManager
    f3d_opts = exp_mgr.createFusionArchiveExportOptions(ruta)
    exp_mgr.execute(f3d_opts)

    return ruta


def exportar_batch(app, design, nombre_pieza, formatos=None):
    """
    Exporta en múltiples formatos de una vez.
    formatos: lista con 'stl', 'step', 'f3d' (default: solo stl)
    Retorna dict {formato: ruta}
    """
    if formatos is None:
        formatos = ['stl']

    rutas = {}
    for fmt in formatos:
        try:
            if fmt == 'stl':
                rutas['stl']  = exportar_stl(app, design, nombre_pieza)
            elif fmt == 'step':
                rutas['step'] = exportar_step(app, design, nombre_pieza)
            elif fmt == 'f3d':
                rutas['f3d']  = exportar_f3d(app, design, nombre_pieza)
        except Exception as e:
            rutas[fmt] = f'ERROR: {e}'

    return rutas


def _limpiar_nombre(nombre):
    """Elimina caracteres inválidos para nombres de archivo."""
    invalidos = r'\/:*?"<>| '
    for c in invalidos:
        nombre = nombre.replace(c, '_')
    return nombre
