"""
core/modelo.py
Lógica de modelado 3D usando la API de Fusion 360.
Toma los valores del formulario y construye la geometría.
"""

import adsk.core
import adsk.fusion
import traceback
from . import exportador


# ═══════════════════════════════════════════════════════
# ENTRADA PRINCIPAL
# ═══════════════════════════════════════════════════════

def crear_modelo(inputs):
    """
    Lee los inputs del formulario y construye la pieza en Fusion.
    Llamado desde el ExecuteHandler del formulario.
    """
    app    = adsk.core.Application.get()
    ui     = app.userInterface
    design = app.activeProduct

    try:
        params = _leer_inputs(inputs)
        _registrar_parametros(design, params)
        cuerpo = _modelar(design, params)

        if params['exportar_stl']:
            ruta = exportador.exportar_stl(app, design, params['tipo'])
            msg_export = f'\n\nSTL guardado en:\n{ruta}'
        else:
            msg_export = ''

        ui.messageBox(
            f'✅  Pieza generada: <b>{params["tipo"]}</b><br>'
            f'Largo {params["largo"]*10:.1f} mm · '
            f'Ancho {params["ancho"]*10:.1f} mm · '
            f'Alto {params["alto"]*10:.1f} mm'
            f'{msg_export}',
            'Generador Paramétrico',
            adsk.core.MessageBoxButtonTypes.OKButtonType,
            adsk.core.MessageBoxIconTypes.InformationIconType
        )

    except Exception:
        ui.messageBox(f'Error en el modelado:\n{traceback.format_exc()}')


# ═══════════════════════════════════════════════════════
# LECTURA DE INPUTS
# ═══════════════════════════════════════════════════════

def _leer_inputs(inputs):
    """Extrae y devuelve todos los valores del formulario como dict."""
    return {
        'tipo':         inputs.itemById('tipo_pieza').selectedItem.name,
        'largo':        inputs.itemById('largo').value,          # en cm (unidad interna)
        'ancho':        inputs.itemById('ancho').value,
        'alto':         inputs.itemById('alto').value,
        'tiene_filete': inputs.itemById('tiene_filete').value,
        'radio_filete': inputs.itemById('radio_filete').value,
        'tolerancia':   inputs.itemById('tolerancia').value,
        'exportar_stl': inputs.itemById('exportar_stl').value,
    }


# ═══════════════════════════════════════════════════════
# PARÁMETROS DE USUARIO (editables desde Fusion)
# ═══════════════════════════════════════════════════════

def _registrar_parametros(design, params):
    """
    Registra los valores como UserParameters de Fusion.
    Esto permite modificarlos después desde Change Parameters.
    """
    up = design.userParameters
    _set_param(up, 'gen_largo',      params['largo'],      'cm')
    _set_param(up, 'gen_ancho',      params['ancho'],      'cm')
    _set_param(up, 'gen_alto',       params['alto'],       'cm')
    _set_param(up, 'gen_tolerancia', params['tolerancia'], 'cm')
    if params['tiene_filete']:
        _set_param(up, 'gen_filete', params['radio_filete'], 'cm')


def _set_param(up, nombre, valor, unidad):
    ex = up.itemByName(nombre)
    if ex:
        ex.expression = str(valor)
    else:
        up.add(nombre, adsk.core.ValueInput.createByReal(valor), unidad, f'Generador: {nombre}')


# ═══════════════════════════════════════════════════════
# MODELADO
# ═══════════════════════════════════════════════════════

def _modelar(design, params):
    """Construye la geometría según el tipo de pieza."""
    root = design.rootComponent
    tipo = params['tipo'].lower()

    # Despachar al constructor correspondiente
    if 'difusor' in tipo:
        return _construir_difusor(root, params)
    elif 'clip' in tipo:
        return _construir_clip(root, params)
    elif 'soporte' in tipo:
        return _construir_soporte(root, params)
    else:
        return _construir_caja(root, params)   # default


# ── Constructor genérico: caja sólida ──────────────────

def _construir_caja(root, params):
    sketch = _crear_sketch_rect(root, params['largo'], params['ancho'], 'Perfil_Caja')
    extr   = _extruir(root, sketch, params['alto'], 'Cuerpo_Caja')

    if params['tiene_filete'] and params['radio_filete'] > 0:
        _aplicar_filete_bordes_vert(root, extr, params['radio_filete'])

    return extr


# ── Constructor: difusor (lámina delgada) ──────────────

def _construir_difusor(root, params):
    sketch = _crear_sketch_rect(root, params['largo'], params['ancho'], 'Perfil_Difusor')
    extr   = _extruir(root, sketch, params['alto'], 'Cuerpo_Difusor')

    # Filete suave en todos los bordes del difusor
    if params['tiene_filete'] and params['radio_filete'] > 0:
        _aplicar_filete_todos(root, extr, params['radio_filete'])

    return extr


# ── Constructor: clip (perfil en U simple) ─────────────

def _construir_clip(root, params):
    """
    Construye un clip básico en perfil U.
    El ancho define la abertura, el alto la profundidad del canal.
    """
    largo = params['largo']
    ancho = params['ancho']
    alto  = params['alto']
    tol   = params['tolerancia']
    espesor = max(0.03, ancho * 0.15)   # ~15% del ancho, mínimo 3mm

    # Sketch del perfil en U en plano XZ
    plano_xz = root.xZConstructionPlane
    sketch    = root.sketches.add(plano_xz)
    sketch.name = 'Perfil_Clip'
    lines = sketch.sketchCurves.sketchLines

    # Pared izquierda
    lines.addByTwoPoints(
        adsk.core.Point3D.create(0,         0, 0),
        adsk.core.Point3D.create(0,         0, alto)
    )
    # Base
    lines.addByTwoPoints(
        adsk.core.Point3D.create(0,         0, 0),
        adsk.core.Point3D.create(ancho + tol*2, 0, 0)
    )
    # Pared derecha
    lines.addByTwoPoints(
        adsk.core.Point3D.create(ancho + tol*2, 0, 0),
        adsk.core.Point3D.create(ancho + tol*2, 0, alto)
    )
    # Tapa izquierda
    lines.addByTwoPoints(
        adsk.core.Point3D.create(0,         0, alto),
        adsk.core.Point3D.create(espesor,   0, alto)
    )
    # Tapa derecha
    lines.addByTwoPoints(
        adsk.core.Point3D.create(ancho + tol*2,           0, alto),
        adsk.core.Point3D.create(ancho + tol*2 - espesor, 0, alto)
    )

    # Extruir el perfil a lo largo del eje Y
    prof = sketch.profiles.item(0)
    if sketch.profiles.count == 0:
        # Fallback: caja simple si el perfil U no cerró
        sketch.deleteMe()
        return _construir_caja(root, params)

    extrudes = root.features.extrudeFeatures
    ext_in   = extrudes.createInput(prof, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    ext_in.setDistanceExtent(False, adsk.core.ValueInput.createByReal(largo))
    extr = extrudes.add(ext_in)
    extr.name = 'Cuerpo_Clip'

    if params['tiene_filete'] and params['radio_filete'] > 0:
        _aplicar_filete_bordes_vert(root, extr, params['radio_filete'])

    return extr


# ── Constructor: soporte de montaje ───────────────────

def _construir_soporte(root, params):
    """Caja con agujeros de montaje en las esquinas."""
    extr = _construir_caja(root, params)

    # Agregar agujeros de montaje (diámetro 3mm, en las 4 esquinas)
    _agregar_agujeros_montaje(root, extr, params)

    return extr


def _agregar_agujeros_montaje(root, extr, params):
    """Perfora 4 agujeros de 3mm en las esquinas del soporte."""
    try:
        largo   = params['largo']
        ancho   = params['ancho']
        alto    = params['alto']
        margen  = 0.5   # 5mm del borde
        radio   = 0.15  # 1.5mm → agujero 3mm de diámetro

        cara_sup = None
        cuerpo   = extr.bodies.item(0)
        for cara in cuerpo.faces:
            if isinstance(cara.geometry, adsk.core.Plane):
                normal = cara.geometry.normal
                if abs(normal.z - 1.0) < 0.01:
                    cara_sup = cara
                    break

        if not cara_sup:
            return

        # Sketch sobre la cara superior
        sketch = root.sketches.add(cara_sup)
        sketch.name = 'Agujeros_Montaje'
        circulos = sketch.sketchCurves.sketchCircles

        esquinas = [
            (margen, margen),
            (largo - margen, margen),
            (margen, ancho - margen),
            (largo - margen, ancho - margen),
        ]
        for x, y in esquinas:
            circulos.addByCenterRadius(
                adsk.core.Point3D.create(x, y, 0), radio
            )

        # Corte a través de todo el cuerpo
        extrudes = root.features.extrudeFeatures
        for i in range(sketch.profiles.count):
            prof   = sketch.profiles.item(i)
            ext_in = extrudes.createInput(prof, adsk.fusion.FeatureOperations.CutFeatureOperation)
            ext_in.setAllExtent(adsk.fusion.ExtentDirections.NegativeExtentDirection)
            extrudes.add(ext_in)

    except Exception:
        pass   # los agujeros son opcionales — no frenar el flujo


# ═══════════════════════════════════════════════════════
# UTILIDADES DE GEOMETRÍA
# ═══════════════════════════════════════════════════════

def _crear_sketch_rect(root, largo, ancho, nombre):
    sketch = root.sketches.add(root.xYConstructionPlane)
    sketch.name = nombre
    sketch.sketchCurves.sketchLines.addTwoPointRectangle(
        adsk.core.Point3D.create(0,     0,    0),
        adsk.core.Point3D.create(largo, ancho, 0)
    )
    return sketch


def _extruir(root, sketch, alto, nombre):
    prof     = sketch.profiles.item(0)
    extrudes = root.features.extrudeFeatures
    ext_in   = extrudes.createInput(prof, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    ext_in.setDistanceExtent(False, adsk.core.ValueInput.createByReal(alto))
    extr      = extrudes.add(ext_in)
    extr.name = nombre
    return extr


def _aplicar_filete_bordes_vert(root, extr, radio):
    """Filete solo en aristas verticales (paralelas a Z)."""
    aristas = adsk.core.ObjectCollection.create()
    for arista in extr.bodies.item(0).edges:
        if _es_vertical(arista):
            aristas.add(arista)
    _filetear(root, aristas, radio)


def _aplicar_filete_todos(root, extr, radio):
    """Filete en todas las aristas del cuerpo."""
    aristas = adsk.core.ObjectCollection.create()
    for arista in extr.bodies.item(0).edges:
        aristas.add(arista)
    _filetear(root, aristas, radio)


def _filetear(root, aristas, radio):
    if aristas.count == 0:
        return
    try:
        fil_in = root.features.filletFeatures.createInput()
        fil_in.isRollingBallCorner = True
        fil_in.addConstantRadiusEdgeSet(
            aristas,
            adsk.core.ValueInput.createByReal(radio),
            True
        )
        root.features.filletFeatures.add(fil_in)
    except Exception:
        pass


def _es_vertical(arista):
    try:
        g = arista.geometry
        if isinstance(g, adsk.core.Line3D):
            dx = abs(g.startPoint.x - g.endPoint.x)
            dy = abs(g.startPoint.y - g.endPoint.y)
            dz = abs(g.startPoint.z - g.endPoint.z)
            return dz > 0.001 and dx < 0.001 and dy < 0.001
    except Exception:
        pass
    return False
