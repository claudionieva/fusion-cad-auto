"""
core/formulario.py
Panel lateral Fusion 360 — Nivel 1 (individual) + Nivel 2 (batch CSV).
"""

import adsk.core, adsk.fusion
import traceback, json, os, importlib

_DIR_CONFIG = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'config'))
_FAMILIAS   = None


def _cargar_familias():
    global _FAMILIAS
    if _FAMILIAS is not None:
        return _FAMILIAS
    try:
        with open(os.path.join(_DIR_CONFIG, 'familias.json'), encoding='utf-8') as f:
            _FAMILIAS = json.load(f)['familias']
    except Exception:
        _FAMILIAS = []
    return _FAMILIAS


def crear_inputs(inputs):
    familias = _cargar_familias()
    defaults = familias[0]['params_default'] if familias else {}

    # Tipo de pieza
    grp_tipo = inputs.addGroupCommandInput('grp_tipo', 'Tipo de pieza')
    grp_tipo.isExpanded = True
    tipo_dd = grp_tipo.children.addDropDownCommandInput('tipo_pieza', 'Familia',
        adsk.core.DropDownStyles.TextListDropDownStyle)
    for i, f in enumerate(familias):
        tipo_dd.listItems.add(f['nombre'], i == 0, '')
    grp_tipo.children.addTextBoxCommandInput('desc_familia', '',
        f'<i>{familias[0]["descripcion"] if familias else ""}</i>', 2, True)

    # Dimensiones
    grp_dim = inputs.addGroupCommandInput('grp_dim', 'Dimensiones')
    grp_dim.isExpanded = True
    d = grp_dim.children
    d.addValueInput('largo', 'Largo', 'mm', adsk.core.ValueInput.createByReal(defaults.get('largo', 100) / 10))
    d.addValueInput('ancho', 'Ancho', 'mm', adsk.core.ValueInput.createByReal(defaults.get('ancho', 60) / 10))
    d.addValueInput('alto',  'Alto',  'mm', adsk.core.ValueInput.createByReal(defaults.get('alto', 30) / 10))

    # Opciones
    grp_opt = inputs.addGroupCommandInput('grp_opt', 'Opciones')
    grp_opt.isExpanded = True
    o = grp_opt.children
    o.addBoolValueInput('tiene_filete', 'Redondear bordes', True, '', True)
    o.addValueInput('radio_filete', 'Radio del filete', 'mm',
        adsk.core.ValueInput.createByReal(defaults.get('filete', 2.0) / 10))
    o.addBoolValueInput('exportar_stl', 'Exportar STL automáticamente', True, '', True)

    # Tolerancias
    grp_tol = inputs.addGroupCommandInput('grp_tol', 'Tolerancias')
    grp_tol.isExpanded = False
    grp_tol.children.addValueInput('tolerancia', 'Tolerancia general', 'mm',
        adsk.core.ValueInput.createByReal(defaults.get('tolerancia', 0.2) / 10))

    # Batch CSV (Nivel 2)
    grp_batch = inputs.addGroupCommandInput('grp_batch', 'Generacion en lote (CSV)')
    grp_batch.isExpanded = False
    b = grp_batch.children
    b.addTextBoxCommandInput('batch_info', '',
        'Pega la ruta de tu CSV para generar multiples piezas.<br>'
        '<b>Columnas:</b> tipo, largo, ancho, alto, filete, tolerancia', 3, True)
    b.addStringValueInput('ruta_csv', 'Ruta del CSV', '')

    inputs.addTextBoxCommandInput('info', '',
        '<b>Tip:</b> Si dejás la ruta CSV vacía, genera la pieza del formulario.', 2, True)


def _validar(inputs):
    largo = inputs.itemById('largo').value
    ancho = inputs.itemById('ancho').value
    alto  = inputs.itemById('alto').value
    if largo <= 0 or ancho <= 0 or alto <= 0:
        return False, 'Todas las dimensiones deben ser mayores a 0.'
    if max(largo, ancho, alto) > 100:
        return False, 'Dimension maxima: 1000mm.'
    if inputs.itemById('tiene_filete').value:
        if inputs.itemById('radio_filete').value >= min(largo, ancho, alto) / 2:
            return False, 'Filete muy grande para estas dimensiones.'
    return True, ''


class _InputChanged(adsk.core.InputChangedEventHandler):
    def notify(self, args):
        try:
            inputs   = args.inputs
            changed  = args.input
            familias = _cargar_familias()
            if changed.id == 'tipo_pieza':
                idx     = changed.selectedItem.index
                familia = familias[idx] if idx < len(familias) else None
                if familia:
                    p = familia['params_default']
                    inputs.itemById('largo').value        = p.get('largo', 100) / 10
                    inputs.itemById('ancho').value        = p.get('ancho', 60)  / 10
                    inputs.itemById('alto').value         = p.get('alto', 30)   / 10
                    inputs.itemById('radio_filete').value = p.get('filete', 2.0)/ 10
                    inputs.itemById('tolerancia').value   = p.get('tolerancia', 0.2) / 10
                    inputs.itemById('desc_familia').text  = f'<i>{familia["descripcion"]}</i>'
            inputs.itemById('radio_filete').isVisible = inputs.itemById('tiene_filete').value
        except Exception:
            pass


class _Validate(adsk.core.ValidateInputsEventHandler):
    def notify(self, args):
        ok, msg = _validar(args.inputs)
        args.areInputsValid = ok
        if not ok:
            args.validationMessage = msg


class _Execute(adsk.core.CommandEventHandler):
    def __init__(self, modelo_mod):
        super().__init__()
        self._mod = modelo_mod

    def notify(self, args):
        try:
            inputs   = args.command.commandInputs
            ruta_csv = inputs.itemById('ruta_csv').value.strip()

            if ruta_csv:
                # Modo Batch — Nivel 2
                batch = importlib.import_module('core.batch')
                importlib.reload(batch)
                app = adsk.core.Application.get()
                ui  = app.userInterface
                ui.messageBox('Procesando CSV, esto puede tardar...', 'Generacion en lote')
                exitosos, fallidos, reporte = batch.ejecutar_batch(ruta_csv)
                ruta_rep = batch.generar_reporte(exitosos, fallidos, reporte, ruta_csv)
                ui.messageBox(
                    f'Batch completado\n\nExitosos: {exitosos}\nFallidos: {fallidos}\n\nReporte en:\n{ruta_rep}',
                    'Generacion en lote'
                )
            else:
                # Modo individual — Nivel 1
                self._mod.crear_modelo(inputs)

        except Exception:
            adsk.core.Application.get().userInterface.messageBox(
                f'Error:\n{traceback.format_exc()}')


def conectar_handlers(cmd, modelo_mod):
    h_input = _InputChanged()
    h_valid = _Validate()
    h_exec  = _Execute(modelo_mod)
    cmd.inputChanged.add(h_input)
    cmd.validateInputs.add(h_valid)
    cmd.execute.add(h_exec)
    return [h_input, h_valid, h_exec]
