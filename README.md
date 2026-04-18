# Generador Paramétrico CAD — Fusion 360 + GitHub

Sistema de automatización CAD con auto-update desde GitHub.

---

## Estructura del repositorio

```
fusion-cad-auto/
├── version.txt              ← versión actual (ej: "1.0.0")
├── core/
│   ├── __init__.py
│   ├── formulario.py        ← panel lateral de Fusion
│   ├── modelo.py            ← lógica de modelado 3D
│   └── exportador.py        ← exportación STL/STEP/F3D
├── config/
│   └── familias.json        ← tipos de piezas y defaults
└── launcher/
    ├── generador.py         ← instalar este en Fusion (una sola vez)
    └── generador.manifest
```

---

## PASOS DE INSTALACIÓN (una sola vez)

### PASO 1 — Crear el repo en GitHub

1. Ir a https://github.com/new
2. Nombre: `fusion-cad-auto`
3. Visibilidad: **Private** (recomendado)
4. Crear sin README (vamos a subir todo desde acá)

### PASO 2 — Subir los archivos al repo

Opción A — desde la terminal:
```bash
git clone https://github.com/TU_USUARIO/fusion-cad-auto.git
# Copiar todos los archivos de este proyecto a la carpeta clonada
cd fusion-cad-auto
git add .
git commit -m "Setup inicial"
git push
```

Opción B — subir directo desde GitHub web:
- En el repo → "Add file" → "Upload files"
- Subir todos los archivos respetando la estructura de carpetas

### PASO 3 — Editar generador.py con tu usuario

Abrir `launcher/generador.py` y cambiar:
```python
GITHUB_USER = 'TU_USUARIO'    # ← tu usuario de GitHub
GITHUB_REPO = 'fusion-cad-auto'
```

### PASO 4 — Instalar en Fusion 360

Copiar la carpeta `launcher/` y **renombrarla** a `generador_parametrico`:

**Windows:**
```
%appdata%\Autodesk\Autodesk Fusion 360\API\AddIns\generador_parametrico\
  ├── generador.py
  └── generador.manifest
```

**Mac:**
```
~/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns/generador_parametrico/
  ├── generador.py
  └── generador.manifest
```

### PASO 5 — Activar en Fusion

1. Abrir Fusion 360
2. Menú: **Tools → Scripts and Add-Ins** (o Shift+S)
3. Pestaña: **Add-Ins**
4. Buscar "generador_parametrico" → clic en **Run**
5. Tildar **Run on Startup** para que arranque siempre

✅ La primera vez descarga los archivos de GitHub automáticamente.

### PASO 6 — Usar el generador

- Ir a la pestaña **SOLID** en la barra de herramientas
- Panel **CREATE** → botón **"Generador Paramétrico"**
- Completar el formulario → **Generar pieza**

---

## FLUJO DE ACTUALIZACIÓN

Cuando quieras modificar el comportamiento:

```bash
# 1. Editar el archivo que necesitás
nano core/formulario.py   # o modelo.py, exportador.py, familias.json

# 2. Subir los cambios
git add .
git commit -m "Descripción del cambio"
git push

# 3. Incrementar la versión
echo "1.1.0" > version.txt
git add version.txt
git commit -m "v1.1.0"
git push
```

La próxima vez que ejecutes el add-in en Fusion, detecta la versión nueva
y descarga los archivos actualizados automáticamente. No necesitás tocar Fusion.

---

## AGREGAR UNA NUEVA FAMILIA DE PIEZAS

Editar `config/familias.json` y agregar:

```json
{
  "id": "mi_pieza",
  "nombre": "Mi pieza nueva",
  "descripcion": "Descripción corta",
  "params_default": {
    "largo": 80,
    "ancho": 40,
    "alto": 15,
    "filete": 1.5,
    "tolerancia": 0.2
  }
}
```

Después agregar el constructor en `core/modelo.py`:

```python
elif 'mi pieza' in tipo:
    return _construir_mi_pieza(root, params)
```

---

## SOLUCIÓN DE PROBLEMAS

**"Sin conexión y sin cache"**
→ Necesitás internet la primera vez. Conectate y volvé a ejecutar.

**"Error al cargar formulario"**
→ Revisá que `GITHUB_USER` y `GITHUB_REPO` estén bien escritos.

**El botón no aparece en Fusion**
→ Ir a Tools → Scripts and Add-Ins → Add-Ins → Run manualmente.

**Quiero forzar la actualización**
→ Borrar la carpeta `_cache` dentro de la carpeta del add-in en Fusion.
