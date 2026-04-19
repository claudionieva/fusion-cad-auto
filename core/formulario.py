"""
core/formulario.py
Panel lateral Fusion 360 — Nivel 1 + Nivel 2 (batch) + Nivel 3 (IA).
Fix: comando reutilizable sin reiniciar Fusion.
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


def _leer_api_key():
    ruta = os.path.join(os.path.expanduser('~'), 'Documents', 'FusionCAD', '.api_key')
    if os.path.exists(ruta):
        return open(ruta).read().strip()
    return ''


def _guardar_api_key(key):
    carpeta = os.path.join(os.path.expanduser('~'), 'Documents', 'FusionCAD')
    os.makedirs(carpeta, exist_ok=True)
    with open(os.path.join(carpeta, '.api_key'), 'w') as f:
        f.write(key)


# ═══════════════════════════════════════════════════════
# FORMULARIO
# ═══════════════════════════════════════════════════════

def crear_inputs(inputs):
    familias = _cargar_familias()
    defaults = familias[0]['params_default'] if familias else {}

    # Nivel 3 — IA
    grp_ia = inputs.addGroupCommandInput('grp_ia', 'Generar con IA (describí la pieza)')
    grp_ia.isExpanded = True
    ia = grp_ia.children
    ia.addTextBoxCommandInput('ia_desc', 'Descripcion', '', 4, False)
    ia.addStringValueInput('ia_key', 'API Key', _leer_api_key())
    ia.addTextBoxCommandInput('ia_info', '',
        '<i>Describí la pieza en texto libre y la IA genera el codigo.<br>'
        'Ej: "caja 10x5x3cm con tapa a presion y 4 orificios de 3mm"</i>', 3, True)

    # Nivel 1 — Formulario
    grp_tipo = inputs.addGroupCommandInput('grp_tipo', 'Tipo de pieza (formulario)')
    grp_tipo.isExpanded = False
    tipo_dd = grp_tipo.children.addDropDownCommandInput('tipo_pieza', 'Familia',
        adsk.core.DropDownStyles.TextListDropDownStyle)
    for i, f in enumerate(familias):
        tipo_dd.listItems.add(f['nombre'], i == 0, '')
    grp_tipo.children.addTextBoxCommandInput('desc_familia', '',
        f'<i>{familias[0]["descripcion"] if familias else ""}</i>', 2, True)

    grp_dim = inputs.addGroupCommandInput('grp_dim', 'Dimensiones')
    grp_dim.isExpanded = False
    d = grp_dim.children
    d.addValueInput('largo', 'Largo', 'mm', adsk.core.ValueInput.createByReal(defaults.get('largo', 100) / 10))
    d.addValueInput('ancho', 'Ancho', 'mm', adsk.core.ValueInput.createByReal(defaults.get('ancho', 60) / 10))
    d.addValueInput('alto',  'Alto',  'mm', adsk.core.ValueInput.createByReal(defaults.get('alto', 30) / 10))

    grp_opt = inputs.addGroupCommandInput('grp_opt', 'Opciones')
    grp_opt.isExpanded = False
    o = grp_opt.children
    o.addBoolValueInput('tiene_filete', 'Redondear bordes', True, '', True)
    o.addValueInput('radio_filete', 'Radio del filete', 'mm',
        adsk.core.ValueInput.createByReal(defaults.get('filete', 2.0) / 10))
    o.addBoolValueInput('exportar_stl', 'Exportar STL automaticamente', True, '', True)

    grp_tol = inputs.addGroupCommandInput('grp_tol', 'Tolerancias')
    grp_tol.isExpanded = False
    grp_tol.children.addValueInput('tolerancia', 'Tolerancia general', 'mm',
        adsk.core.ValueInput.createByReal(defaults.get('tolerancia', 0.2) / 10))

    # Nivel 2 — Batch
    grp_batch = inputs.addGroupCommandInput('grp_batch', 'Generacion en lote (CSV)')
    grp_batch.isExpanded = False
    b = grp_batch.children
    b.addTextBoxCommandInput('batch_info', '',
        'Pega la ruta de tu CSV para generar multiples piezas.<br>'
        '<b>Columnas:</b> tipo, largo, ancho, alto, filete, tolerancia', 3, True)
    b.addStringValueInput('ruta_csv', 'Ruta del CSV', '')


# ═══════════════════════════════════════════════════════
# VALIDACIÓN
# ═══════════════════════════════════════════════════════

def _validar(inputs):
    ia_desc = inputs.itemById('ia_desc').text.strip()
    if ia_desc:
        if not inputs.itemById('ia_key').value.strip():
            return False, 'Ingresa tu API Key de Anthropic.'
        return True, ''
    if inputs.itemById('ruta_csv').value.strip():
        return True, ''
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


# ═══════════════════════════════════════════════════════
# HANDLERS
# ═══════════════════════════════════════════════════════

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


class _ExecutePreview(adsk.core.CommandEventHandler):
    """Permite que el comando se pueda volver a abrir después de ejecutar."""
    def notify(self, args):
        args.isValidResult = True


class _Execute(adsk.core.CommandEventHandler):
    def __init__(self, modelo_mod):
        super().__init__()
        self._mod = modelo_mod

    def notify(self, args):
        try:
            inputs   = args.command.commandInputs
            app      = adsk.core.Application.get()
            ui       = app.userInterface
            design   = app.activeProduct

            ia_desc  = inputs.itemById('ia_desc').text.strip()
            ruta_csv = inputs.itemById('ruta_csv').value.strip()

            if ia_desc:
                # Nivel 3 — IA
                api_key = inputs.itemById('ia_key').value.strip()
                _guardar_api_key(api_key)

                ia = importlib.import_module('core.ia_generador')
                importlib.reload(ia)

                ui.messageBox('Consultando a Claude AI...\nEsto tarda unos segundos.', 'Nivel 3 — IA')

                codigo, error = ia.generar_codigo(ia_desc, api_key)
                if error:
                    ui.messageBox(f'Error al generar codigo:\n{error}', 'Error IA')
                    return

                valido, msg_val = ia.validar_codigo(codigo)
                if not valido:
                    ui.messageBox(f'Codigo rechazado:\n{msg_val}', 'Error validacion')
                    return

                ok, err_exec = ia.ejecutar_codigo(codigo, design)
                if not ok:
                    ia.guardar_historial(ia_desc, codigo, False)
                    ui.messageBox(f'Error al ejecutar:\n{err_exec}', 'Error ejecucion')
                    return

                ia.guardar_historial(ia_desc, codigo, True)

                exp = importlib.import_module('core.exportador')
                importlib.reload(exp)
                ruta_stl = exp.exportar_stl(app, design, 'IA_pieza')

                ui.messageBox(
                    f'Pieza generada con IA\n\n'
                    f'Descripcion: {ia_desc[:80]}\n\n'
                    f'STL en:\n{ruta_stl}',
                    'Nivel 3 — Exito'
                )

            elif ruta_csv:
                # Nivel 2 — Batch
                batch = importlib.import_module('core.batch')
                importlib.reload(batch)
                ui.messageBox('Procesando CSV...', 'Generacion en lote')
                exitosos, fallidos, reporte = batch.ejecutar_batch(ruta_csv)
                ruta_rep = batch.generar_reporte(exitosos, fallidos, reporte, ruta_csv)
                ui.messageBox(
                    f'Batch completado\n\nExitosos: {exitosos}\nFallidos: {fallidos}\n\nReporte en:\n{ruta_rep}',
                    'Generacion en lote'
                )

            else:
                # Nivel 1 — Formulario
                self._mod.crear_modelo(inputs)

            # Liberar el hilo para que el comando se pueda volver a abrir
            adsk.doEvents()

        except Exception:
            adsk.core.Application.get().userInterface.messageBox(
                f'Error:\n{traceback.format_exc()}')


class _Destroy(adsk.core.CommandEventHandler):
    """Limpia el estado al cerrar el panel."""
    def notify(self, args):
        try:
            for m in ['core.ia_generador', 'core.batch', 'core.exportador']:
                if m in __import__('sys').modules:
                    del __import__('sys').modules[m]
        except Exception:
            pass


def conectar_handlers(cmd, modelo_mod):
    h_input   = _InputChanged()
    h_valid   = _Validate()
    h_exec    = _Execute(modelo_mod)
    h_preview = _ExecutePreview()
    h_destroy = _Destroy()

    cmd.inputChanged.add(h_input)
    cmd.validateInputs.add(h_valid)
    cmd.execute.add(h_exec)
    cmd.executePreview.add(h_preview)
    cmd.destroy.add(h_destroy)

    return [h_input, h_valid, h_exec, h_preview, h_destroy]
