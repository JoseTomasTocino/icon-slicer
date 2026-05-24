# icon-slicer

![Resumen del proyecto](summary-image.png)

Script para extraer iconos desde una imagen compuesta y guardarlos como PNG con transparencia.

## Requisitos

- Python 3
- OpenCV
- NumPy

## Instalación con uv

Si no tienes `uv` instalado:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Sincroniza el entorno virtual y las dependencias del proyecto:

```bash
uv sync
```

Esto creará `.venv/` e instalará las dependencias definidas en `pyproject.toml` usando también `uv.lock` si está presente.

Para activar el entorno manualmente:

```bash
source .venv/bin/activate
```

También puedes ejecutar el script directamente con `uv` sin activar el entorno:

```bash
uv run python icon_slicer.py image_sources/b1.png salida --white-threshold 245 --min-area 500
```

## Uso

```bash
python icon_slicer.py ENTRADA SALIDA_DIR [--white-threshold N] [--min-area N] [--save-debug]
```

Ejemplo:

```bash
python icon_slicer.py image_sources/b1.png salida --white-threshold 245 --min-area 500
```

## Cómo funciona

El script detecta fondo como regiones de píxeles blancos o casi blancos conectadas al borde de la imagen. Todo lo que no pertenezca a ese fondo conectado se considera contenido.

Después:

- limpia la máscara con operaciones morfológicas,
- detecta componentes conectados,
- descarta componentes demasiado pequeños,
- exporta cada componente válido como `icon_XX.png` con canal alpha.

## Parámetros

### `--white-threshold`

Umbral para considerar un píxel como casi blanco.

- Rango: `0-255`
- Valor por defecto: `245`
- Cuanto más alto sea, más estricto será el criterio de blanco.

### `--min-area`

Área mínima en píxeles para aceptar un componente como icono.

- Valor por defecto: `500`
- Si lo subes, se descarta más ruido.
- Si lo bajas, se aceptan componentes más pequeños.

### `--save-debug`

Si se indica, guarda imágenes intermedias de depuración en la carpeta de salida.

Por defecto no se guardan.

Archivos de debug generados:

- `debug_00_near_white.png`
- `debug_00_fondo_conectado.png`
- `debug_01_mask_inicial.png`
- `debug_02_mask_limpia.png`
- `debug_03_componentes.png`

Ejemplo:

```bash
python icon_slicer.py image_sources/b1.png salida --white-threshold 245 --min-area 500 --save-debug
```

## Salida

Los iconos se guardan como:

- `icon_01.png`
- `icon_02.png`
- `icon_03.png`

Si esos nombres ya existen, el script no sobreescribe archivos anteriores: busca automáticamente el siguiente índice libre.

## Logging

El script emite logs paso a paso para facilitar el diagnóstico:

- carga de imagen,
- creación de máscara,
- limpieza morfológica,
- detección de componentes,
- exportación de iconos,
- saltos de nombres ya ocupados.
