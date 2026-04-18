"""
core/formulario.py
Panel lateral de Fusion 360 — campos, validación y handlers.
Este archivo vive en GitHub y se descarga automáticamente.
"""

import adsk.core
import adsk.fusion
import traceback
import json
import os

# Ruta al JSON de familias (en el cache local)
_DIR_CACHE  = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'config')
_FAMILIAS   = None   # se carga lazy


def _cargar_familias():
    global _FAMILIAS
    if _FAMILIAS is not None:
        return _FAMILIAS
    ruta = os.path.normpath(os.path.join(_DIR_CACHE, 'familias.json'))
    try:
        with open(ruta, encoding='utf-8') as f:
            _FAMILIAS = json.load(f)['familias']
    except Exception:
        _FAMILIAS = []
    return _FAMILIAS


# ═══════════════════════════════════════════════════════
# CONSTRUCCIÓN DEL FORMULARIO
# ═══════════════════════════════════════════════════════

def crear_inputs(inputs):
    """
    Construye todos los campos del panel lateral.
    Llamado desde el launcher cuando Fusion abre el comando.
    """
    familias = _cargar_familias()

    # ── Tipo de pieza ──────────────────────────────────
    grp_tipo = inputs.addGroupCommandInput('grp_tipo', 'Tipo de pieza')
    grp_tipo.isExpanded = True

    tipo_dd = grp_tipo.children.addDropDownCommandInput(
        'tipo_pieza', 'Familia',
        adsk.core.DropDownStyles.TextListDropDownStyle
    )
    for i, f in enumerate(familias):
        tipo_dd.listItems.add(f['nombre'], i == 0, '')

    # Descripción de la familia seleccionada
    desc = familias[0]['descripcion'] if familias else ''
    grp_tipo.children.addTextBoxCommandInput(
        'desc_familia', '', f'<i>{desc}</i>', 2, True
    )

    # ── Dimensiones ────────────────────────────────────
    grp_dim = inputs.addGroupCommandInput('grp_dim', 'Dimensiones')
    grp_dim.isExpanded = True
    d = grp_dim.children

    defaults = familias[0]['params_default'] if familias else {}

    d.addValueInput('largo', 'Largo', 'mm',
        adsk.core.ValueInput.createByReal(defaults.get('largo', 100) / 10))
    d.addValueInput('ancho', 'Ancho', 'mm',
        adsk.core.ValueInput.createByReal(defaults.get('ancho', 60) / 10))
    d.addValueInput('alto',  'Alto',  'mm',
        adsk.core.ValueInput.createByReal(defaults.get('alto', 30) / 10))

    # ── Opciones ───────────────────────────────────────
    grp_opt = inputs.addGroupCommandInput('grp_opt', 'Opciones')
    grp_opt.isExpanded = True
    o = grp_opt.children

    o.addBoolValueInput('tiene_filete', 'Redondear bordes', True, '', True)
    o.addValueInput('radio_filete', 'Radio del filete', 'mm',
        adsk.core.ValueInput.createByReal(defaults.get('filete', 2.0) / 10))

    o.addBoolValueInput('exportar_stl', 'Exportar STL automáticamente', True, '', True)

    # ── Tolerancias ────────────────────────────────────
    grp_tol = inputs.addGroupCommandInput('grp_tol', 'Tolerancias')
    grp_tol.isExpanded = False
    t = grp_tol.children

    t.addValueInput('tolerancia', 'Tolerancia general', 'mm',
        adsk.core.ValueInput.createByReal(defaults.get('tolerancia', 0.2) / 10))

    # ── Info al pie ────────────────────────────────────
    inputs.addTextBoxCommandInput(
        'info', '',
        '<b>Tip:</b> Cambiá la familia para cargar valores por defecto.',
        2, True
    )


# ═══════════════════════════════════════════════════════
# VALIDACIÓN
# ═══════════════════════════════════════════════════════

def _validar(inputs):
    largo = inputs.itemById('largo').value
    ancho = inputs.itemById('ancho').value
    alto  = inputs.itemById('alto').value

    if largo <= 0 or ancho <= 0 or alto <= 0:
        return False, 'Todas las dimensiones deben ser mayores a 0.'

    if max(largo, ancho, alto) > 100:
        return False, 'Dimensión máxima: 1000 mm. Verificá las unidades.'

    tiene_filete = inputs.itemById('tiene_filete').value
    radio        = inputs.itemById('radio_filete').value
    if tiene_filete and radio >= min(largo, ancho, alto) / 2:
        return False, f'Filete muy grande para estas dimensiones.'

    return True, ''


# ═══════════════════════════════════════════════════════
# HANDLERS
# ═══════════════════════════════════════════════════════

class _InputChanged(adsk.core.InputChangedEventHandler):
    def __init__(self, modelo_mod):
        super().__init__()
        self._mod = modelo_mod

    def notify(self, args):
        try:
            inputs   = args.inputs
            changed  = args.input
            familias = _cargar_familias()

            # Si cambió el tipo de pieza → actualizar defaults y descripción
            if changed.id == 'tipo_pieza':
                idx     = changed.selectedItem.index
                familia = familias[idx] if idx < len(familias) else None
                if familia:
                    p = familia['params_default']
                    inputs.itemById('largo').value = p.get('largo', 100) / 10
                    inputs.itemById('ancho').value = p.get('ancho', 60) / 10
                    inputs.itemById('alto').value  = p.get('alto', 30) / 10
                    inputs.itemById('radio_filete').value = p.get('filete', 2.0) / 10
                    inputs.itemById('tolerancia').value   = p.get('tolerancia', 0.2) / 10
                    inputs.itemById('desc_familia').text  = f'<i>{familia["descripcion"]}</i>'

            # Mostrar/ocultar radio según checkbox
            inputs.itemById('radio_filete').isVisible = inputs.itemById('tiene_filete').value

        except Exception:
            pass


class _Validate(adsk.core.ValidateInputsEventHandler):
    def notify(self, args):
        ok, msg = _validar(args.inputs)
        args.areInputsValid    = ok
        if not ok:
            args.validationMessage = msg


class _Execute(adsk.core.CommandEventHandler):
    def __init__(self, modelo_mod):
        super().__init__()
        self._mod = modelo_mod

    def notify(self, args):
        try:
            self._mod.crear_modelo(args.command.commandInputs)
        except Exception:
            app = adsk.core.Application.get()
            app.userInterface.messageBox(
                f'Error al generar:\n{traceback.format_exc()}',
                'Generador — Error'
            )


def conectar_handlers(cmd, modelo_mod):
    """
    Conecta todos los handlers al comando.
    Retorna la lista para que el caller mantenga referencias (evita GC).
    """
    h_input = _InputChanged(modelo_mod)
    h_valid = _Validate()
    h_exec  = _Execute(modelo_mod)

    cmd.inputChanged.add(h_input)
    cmd.validateInputs.add(h_valid)
    cmd.execute.add(h_exec)

    return [h_input, h_valid, h_exec]
