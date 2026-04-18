"""
Generador Paramétrico — Launcher con auto-update desde GitHub
Este es el ÚNICO archivo que instalás manualmente en Fusion.
El resto se descarga automáticamente desde tu repo.
"""

import adsk.core, adsk.fusion
import traceback, os, sys, urllib.request, urllib.error, importlib

# ─── CONFIGURACIÓN ─────────────────────────────────────────────────────────────
GITHUB_USER   = 'claudionieva'          # ← cambiá esto
GITHUB_REPO   = 'fusion-cad-auto'    # ← cambiá esto
GITHUB_BRANCH = 'main'

ARCHIVOS_REMOTOS = [
    'core/formulario.py',
    'core/modelo.py',
    'core/exportador.py',
    'config/familias.json',
]

DIR_ADDIN  = os.path.dirname(os.path.abspath(__file__))
DIR_CACHE  = os.path.join(DIR_ADDIN, '_cache')
RAW_BASE   = f'https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/{GITHUB_BRANCH}'
CMD_ID     = 'generadorParametrico_v1'

_app = _ui = _handler = _button = None


# ═══════════════════════════════════════════════════════
# AUTO-UPDATER
# ═══════════════════════════════════════════════════════

def _get_version(url_o_path, es_url=True):
    try:
        if es_url:
            with urllib.request.urlopen(url_o_path, timeout=5) as r:
                return r.read().decode().strip()
        elif os.path.exists(url_o_path):
            return open(url_o_path).read().strip()
    except:
        pass
    return None


def _descargar(ruta_remota):
    url        = f'{RAW_BASE}/{ruta_remota}'
    ruta_local = os.path.join(DIR_CACHE, ruta_remota.replace('/', os.sep))
    os.makedirs(os.path.dirname(ruta_local), exist_ok=True)
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            open(ruta_local, 'wb').write(r.read())
        return True
    except Exception as e:
        return False


def sincronizar():
    """Descarga desde GitHub si hay versión nueva. Retorna (ok, version, msg)."""
    v_remota = _get_version(f'{RAW_BASE}/version.txt')
    v_local  = _get_version(os.path.join(DIR_CACHE, 'version.txt'), es_url=False)

    if v_remota is None:
        if v_local:
            return True, v_local, f'Sin conexión. Usando cache v{v_local}.'
        return False, None, 'Sin conexión y sin cache. Conectate la primera vez.'

    if v_remota == v_local:
        return True, v_local, None   # Sin cambios, nada que hacer

    errores = [r for r in ARCHIVOS_REMOTOS if not _descargar(r)]
    if errores:
        return False, v_local, f'Error al descargar: {", ".join(errores)}'

    open(os.path.join(DIR_CACHE, 'version.txt'), 'w').write(v_remota)
    return True, v_remota, f'✅ Actualizado a v{v_remota}'


# ═══════════════════════════════════════════════════════
# HANDLERS
# ═══════════════════════════════════════════════════════

class CreatedHandler(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        global _handler
        try:
            formulario = importlib.import_module('core.formulario')
            modelo_mod = importlib.import_module('core.modelo')
            importlib.reload(formulario)   # garantiza código fresco
            importlib.reload(modelo_mod)

            cmd = args.command
            cmd.isRepeatable = False
            cmd.okButtonText = 'Generar pieza'
            cmd.setDialogMinimumSize(320, 520)

            formulario.crear_inputs(cmd.commandInputs)
            _handler = formulario.conectar_handlers(cmd, modelo_mod)
        except:
            _ui.messageBox(f'Error cargando formulario:\n{traceback.format_exc()}')


# ═══════════════════════════════════════════════════════
# CICLO DE VIDA
# ═══════════════════════════════════════════════════════

def run(context):
    global _app, _ui, _button, _handler
    try:
        _app = adsk.core.Application.get()
        _ui  = _app.userInterface

        ok, version, msg = sincronizar()

        if not ok:
            _ui.messageBox(f'❌ {msg}', 'Generador Paramétrico')
            return

        if msg:
            _ui.messageBox(msg, 'Generador Paramétrico')

        # Agregar cache al path de Python
        if DIR_CACHE not in sys.path:
            sys.path.insert(0, DIR_CACHE)

        # Registrar comando
        defs = _ui.commandDefinitions
        ex = defs.itemById(CMD_ID)
        if ex: ex.deleteMe()

        label = f'Generador Paramétrico (v{version or "local"})'
        cmd_def = defs.addButtonDefinition(CMD_ID, label, 'CAD automático desde GitHub', '')

        h = CreatedHandler()
        cmd_def.commandCreated.add(h)
        _handler = h

        panel = _ui.allToolbarPanels.itemById('SolidCreatePanel')
        if panel:
            _button = panel.controls.addCommand(cmd_def, '', False)
            _button.isPromotedByDefault = True

    except:
        if _ui: _ui.messageBox(f'Error:\n{traceback.format_exc()}')


def stop(context):
    global _button
    try:
        if _button: _button.deleteMe()
        d = _ui.commandDefinitions.itemById(CMD_ID)
        if d: d.deleteMe()
        for m in ['core.formulario', 'core.modelo', 'core.exportador']:
            sys.modules.pop(m, None)
    except:
        pass
