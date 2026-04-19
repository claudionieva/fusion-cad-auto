"""
core/ia_generador.py
Nivel 3 — Genera código Python para Fusion 360 usando Claude API.
Recibe una descripción en texto y retorna código ejecutable.
"""

import urllib.request
import urllib.error
import json
import os


# ═══════════════════════════════════════════════════════
# CONFIGURACIÓN
# ═══════════════════════════════════════════════════════

MODEL    = 'claude-sonnet-4-20250514'
MAX_TOKENS = 4096

# System prompt que le dice a Claude cómo generar el código
SYSTEM_PROMPT = """Eres un experto en la API de Fusion 360 (Python).
Tu tarea es generar código Python válido para crear geometría 3D en Fusion 360.

REGLAS ESTRICTAS:
1. Devolvé SOLO el código Python, sin explicaciones, sin markdown, sin ```python
2. El código debe ser una función llamada exactamente: crear_pieza(root)
3. root es el rootComponent de Fusion 360 ya inicializado
4. Usá solo adsk.core y adsk.fusion que ya están importados
5. Siempre trabajá en centímetros (unidad interna de Fusion) — dividí mm por 10
6. El código debe ser robusto y no generar errores
7. Incluí comentarios breves en español
8. No incluyas import, app, design, ui — solo la función crear_pieza(root)

EJEMPLO de respuesta correcta:
def crear_pieza(root):
    # Sketch en plano XY
    sketch = root.sketches.add(root.xYConstructionPlane)
    lines = sketch.sketchCurves.sketchLines
    lines.addTwoPointRectangle(
        adsk.core.Point3D.create(0, 0, 0),
        adsk.core.Point3D.create(10, 5, 0)
    )
    # Extruir 3cm
    prof = sketch.profiles.item(0)
    ext_in = root.features.extrudeFeatures.createInput(
        prof, adsk.fusion.FeatureOperations.NewBodyFeatureOperation
    )
    ext_in.setDistanceExtent(False, adsk.core.ValueInput.createByReal(3))
    root.features.extrudeFeatures.add(ext_in)
"""


# ═══════════════════════════════════════════════════════
# GENERACIÓN CON CLAUDE API
# ═══════════════════════════════════════════════════════

def generar_codigo(descripcion, api_key):
    """
    Envía la descripción a Claude y retorna el código Python generado.
    Retorna (codigo: str, error: str|None)
    """
    if not api_key or not api_key.startswith('sk-ant-'):
        return None, 'API key inválida. Debe empezar con sk-ant-'

    prompt = f"""Generá el código Python para Fusion 360 que cree esta pieza:

{descripcion}

Recordá: solo la función crear_pieza(root), en centímetros, sin imports."""

    payload = json.dumps({
        'model':      MODEL,
        'max_tokens': MAX_TOKENS,
        'system':     SYSTEM_PROMPT,
        'messages':   [{'role': 'user', 'content': prompt}]
    }).encode('utf-8')

    req = urllib.request.Request(
        'https://api.anthropic.com/v1/messages',
        data    = payload,
        headers = {
            'Content-Type':      'application/json',
            'x-api-key':         api_key,
            'anthropic-version': '2023-06-01'
        },
        method = 'POST'
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data   = json.loads(resp.read().decode())
            codigo = data['content'][0]['text'].strip()
            return codigo, None

    except urllib.error.HTTPError as e:
        cuerpo = e.read().decode()
        try:
            msg = json.loads(cuerpo).get('error', {}).get('message', cuerpo)
        except:
            msg = cuerpo
        return None, f'Error API ({e.code}): {msg}'

    except urllib.error.URLError as e:
        return None, f'Sin conexión: {e.reason}'

    except Exception as e:
        return None, f'Error inesperado: {e}'


# ═══════════════════════════════════════════════════════
# VALIDACIÓN DEL CÓDIGO
# ═══════════════════════════════════════════════════════

def validar_codigo(codigo):
    """
    Validación básica de seguridad antes de ejecutar el código generado.
    Retorna (valido: bool, mensaje: str)
    """
    if not codigo:
        return False, 'El código está vacío.'

    if 'def crear_pieza(root)' not in codigo:
        return False, 'El código no contiene la función crear_pieza(root).'

    # Palabras peligrosas que no deberían estar en código CAD
    palabras_prohibidas = [
        'os.system', 'subprocess', 'exec(', 'eval(',
        '__import__', 'open(', 'shutil', 'rmdir',
        'socket', 'urllib.request.urlopen'
    ]
    for palabra in palabras_prohibidas:
        if palabra in codigo:
            return False, f'Código rechazado por seguridad: contiene "{palabra}"'

    return True, 'OK'


# ═══════════════════════════════════════════════════════
# EJECUCIÓN DEL CÓDIGO GENERADO
# ═══════════════════════════════════════════════════════

def ejecutar_codigo(codigo, design):
    """
    Ejecuta el código generado por Claude en Fusion 360.
    Retorna (ok: bool, error: str|None)
    """
    import adsk.core
    import adsk.fusion

    try:
        # Crear namespace con los módulos disponibles
        namespace = {
            'adsk':  adsk,
            'root':  design.rootComponent,
        }

        # Ejecutar el código en el namespace
        exec(codigo, namespace)

        # Llamar a la función generada
        if 'crear_pieza' not in namespace:
            return False, 'El código no definió la función crear_pieza.'

        namespace['crear_pieza'](design.rootComponent)
        return True, None

    except Exception as e:
        import traceback
        return False, traceback.format_exc()


# ═══════════════════════════════════════════════════════
# GUARDAR HISTORIAL
# ═══════════════════════════════════════════════════════

def guardar_historial(descripcion, codigo, exitoso):
    """Guarda cada generación en un archivo de historial."""
    import datetime
    carpeta = os.path.join(os.path.expanduser('~'), 'Documents', 'FusionCAD', 'IA_Historial')
    os.makedirs(carpeta, exist_ok=True)

    ts    = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    ruta  = os.path.join(carpeta, f'generacion_{ts}.py')
    estado = '# EXITOSO' if exitoso else '# FALLIDO'

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(f'{estado}\n')
        f.write(f'# Descripcion: {descripcion}\n')
        f.write(f'# Fecha: {ts}\n\n')
        f.write(codigo)

    return ruta
