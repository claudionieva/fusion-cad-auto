"""
core/modelo.py
Lógica de modelado 3D usando la API de Fusion 360.
Soporta params desde formulario (Nivel 1) y desde batch CSV (Nivel 2).
"""

import adsk.core
import adsk.fusion
import traceback
from . import exportador


def crear_modelo(inputs):
    """Llamado desde el formulario interactivo."""
    app    = adsk.core.Application.get()
    ui     = app.userInterface
    design = app.activeProduct
    try:
        params = _leer_inputs(inputs)
        _registrar_parametros(design, params)
        _modelar(design, params)
        if params['exportar_stl']:
            ruta = exportador.exportar_stl(app, design, params['tipo'])
            msg_export = f'<br><br>STL guardado en:<br>{ruta}'
        else:
            msg_export = ''
        ui.messageBox(
            f'✅ Pieza generada: <b>{params["tipo"]}</b><br>'
            f'Largo {params["largo"]*10:.1f}mm · '
            f'Ancho {params["ancho"]*10:.1f}mm · '
            f'Alto {params["alto"]*10:.1f}mm{msg_export}',
            'Generador Paramétrico',
            adsk.core.MessageBoxButtonTypes.OKButtonType,
            adsk.core.MessageBoxIconTypes.InformationIconType
        )
    except Exception:
        ui.messageBox(f'Error en el modelado:\n{traceback.format_exc()}')


def crear_modelo_desde_params(design, params):
    """Llamado desde el batch processor con dict de params."""
    _registrar_parametros(design, params)
    _modelar(design, params)


def _leer_inputs(inputs):
    return {
        'tipo':         inputs.itemById('tipo_pieza').selectedItem.name,
        'largo':        inputs.itemById('largo').value,
        'ancho':        inputs.itemById('ancho').value,
        'alto':         inputs.itemById('alto').value,
        'tiene_filete': inputs.itemById('tiene_filete').value,
        'radio_filete': inputs.itemById('radio_filete').value,
        'tolerancia':   inputs.itemById('tolerancia').value,
        'exportar_stl': inputs.itemById('exportar_stl').value,
    }


def _registrar_parametros(design, params):
    up = design.userParameters
    _set_param(up, 'gen_largo',      params['largo'],      'cm')
    _set_param(up, 'gen_ancho',      params['ancho'],      'cm')
    _set_param(up, 'gen_alto',       params['alto'],       'cm')
    _set_param(up, 'gen_tolerancia', params['tolerancia'], 'cm')
    if params.get('tiene_filete'):
        _set_param(up, 'gen_filete', params['radio_filete'], 'cm')


def _set_param(up, nombre, valor, unidad):
    ex = up.itemByName(nombre)
    if ex:
        ex.expression = str(valor)
    else:
        up.add(nombre, adsk.core.ValueInput.createByReal(valor), unidad, f'Generador: {nombre}')


def _modelar(design, params):
    root = design.rootComponent
    tipo = params['tipo'].lower()
    if 'difusor' in tipo:
        return _construir_difusor(root, params)
    elif 'clip' in tipo:
        return _construir_clip(root, params)
    elif 'soporte' in tipo:
        return _construir_soporte(root, params)
    else:
        return _construir_caja(root, params)


def _construir_caja(root, params):
    sketch = _crear_sketch_rect(root, params['largo'], params['ancho'], 'Perfil_Caja')
    extr   = _extruir(root, sketch, params['alto'], 'Cuerpo_Caja')
    if params.get('tiene_filete') and params.get('radio_filete', 0) > 0:
        _aplicar_filete_bordes_vert(root, extr, params['radio_filete'])
    return extr


def _construir_difusor(root, params):
    sketch = _crear_sketch_rect(root, params['largo'], params['ancho'], 'Perfil_Difusor')
    extr   = _extruir(root, sketch, params['alto'], 'Cuerpo_Difusor')
    if params.get('tiene_filete') and params.get('radio_filete', 0) > 0:
        _aplicar_filete_todos(root, extr, params['radio_filete'])
    return extr


def _construir_clip(root, params):
    largo   = params['largo']
    ancho   = params['ancho']
    alto    = params['alto']
    tol     = params.get('tolerancia', 0.02)
    espesor = max(0.03, ancho * 0.15)
    plano_xz = root.xZConstructionPlane
    sketch   = root.sketches.add(plano_xz)
    sketch.name = 'Perfil_Clip'
    lines = sketch.sketchCurves.sketchLines
    lines.addByTwoPoints(adsk.core.Point3D.create(0, 0, 0), adsk.core.Point3D.create(0, 0, alto))
    lines.addByTwoPoints(adsk.core.Point3D.create(0, 0, 0), adsk.core.Point3D.create(ancho+tol*2, 0, 0))
    lines.addByTwoPoints(adsk.core.Point3D.create(ancho+tol*2, 0, 0), adsk.core.Point3D.create(ancho+tol*2, 0, alto))
    lines.addByTwoPoints(adsk.core.Point3D.create(0, 0, alto), adsk.core.Point3D.create(espesor, 0, alto))
    lines.addByTwoPoints(adsk.core.Point3D.create(ancho+tol*2, 0, alto), adsk.core.Point3D.create(ancho+tol*2-espesor, 0, alto))
    if sketch.profiles.count == 0:
        sketch.deleteMe()
        return _construir_caja(root, params)
    prof     = sketch.profiles.item(0)
    extrudes = root.features.extrudeFeatures
    ext_in   = extrudes.createInput(prof, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    ext_in.setDistanceExtent(False, adsk.core.ValueInput.createByReal(largo))
    extr      = extrudes.add(ext_in)
    extr.name = 'Cuerpo_Clip'
    if params.get('tiene_filete') and params.get('radio_filete', 0) > 0:
        _aplicar_filete_bordes_vert(root, extr, params['radio_filete'])
    return extr


def _construir_soporte(root, params):
    extr = _construir_caja(root, params)
    _agregar_agujeros_montaje(root, extr, params)
    return extr


def _agregar_agujeros_montaje(root, extr, params):
    try:
        largo  = params['largo']
        ancho  = params['ancho']
        margen = 0.5
        radio  = 0.15
        cara_sup = None
        for cara in extr.bodies.item(0).faces:
            if isinstance(cara.geometry, adsk.core.Plane):
                if abs(cara.geometry.normal.z - 1.0) < 0.01:
                    cara_sup = cara
                    break
        if not cara_sup:
            return
        sketch = root.sketches.add(cara_sup)
        sketch.name = 'Agujeros_Montaje'
        circulos = sketch.sketchCurves.sketchCircles
        for x, y in [(margen, margen), (largo-margen, margen),
                     (margen, ancho-margen), (largo-margen, ancho-margen)]:
            circulos.addByCenterRadius(adsk.core.Point3D.create(x, y, 0), radio)
        extrudes = root.features.extrudeFeatures
        for i in range(sketch.profiles.count):
            prof   = sketch.profiles.item(i)
            ext_in = extrudes.createInput(prof, adsk.fusion.FeatureOperations.CutFeatureOperation)
            ext_in.setAllExtent(adsk.fusion.ExtentDirections.NegativeExtentDirection)
            extrudes.add(ext_in)
    except Exception:
        pass


def _crear_sketch_rect(root, largo, ancho, nombre):
    sketch = root.sketches.add(root.xYConstructionPlane)
    sketch.name = nombre
    sketch.sketchCurves.sketchLines.addTwoPointRectangle(
        adsk.core.Point3D.create(0, 0, 0),
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
    aristas = adsk.core.ObjectCollection.create()
    for a in extr.bodies.item(0).edges:
        if _es_vertical(a):
            aristas.add(a)
    _filetear(root, aristas, radio)


def _aplicar_filete_todos(root, extr, radio):
    aristas = adsk.core.ObjectCollection.create()
    for a in extr.bodies.item(0).edges:
        aristas.add(a)
    _filetear(root, aristas, radio)


def _filetear(root, aristas, radio):
    if aristas.count == 0:
        return
    try:
        fil_in = root.features.filletFeatures.createInput()
        fil_in.isRollingBallCorner = True
        fil_in.addConstantRadiusEdgeSet(aristas, adsk.core.ValueInput.createByReal(radio), True)
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
