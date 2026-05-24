import cv2
import numpy as np
import os
import sys
import logging
import argparse


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)


def guardar_debug_imagen(ruta, imagen, descripcion):
    ok = cv2.imwrite(ruta, imagen)
    if ok:
        logger.info("Debug guardado (%s): %s", descripcion, ruta)
    else:
        logger.warning("No se pudo guardar debug (%s): %s", descripcion, ruta)


def siguiente_badge_disponible(salida_dir, indice_inicio=1):
    indice = indice_inicio
    while True:
        ruta = os.path.join(salida_dir, f"badge_{indice:02d}.png")
        if not os.path.exists(ruta):
            return ruta, indice
        logger.info("Salida existente detectada, se omite: %s", ruta)
        indice += 1


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="Extrae badges con transparencia a partir de una imagen."
    )
    parser.add_argument("entrada", help="Ruta de la imagen de entrada")
    parser.add_argument("salida_dir", help="Carpeta donde guardar resultados")
    parser.add_argument(
        "--white-threshold",
        type=int,
        default=245,
        help="Umbral de casi-blanco para detectar fondo (0-255). Por defecto: 245",
    )
    parser.add_argument(
        "--save-debug",
        action="store_true",
        help="Guarda las imágenes intermedias de depuración en la carpeta de salida",
    )
    parser.add_argument(
        "--min-area",
        type=int,
        default=500,
        help="Área mínima en píxeles para aceptar un componente como badge. Por defecto: 500",
    )
    args = parser.parse_args(argv)

    if args.white_threshold < 0 or args.white_threshold > 255:
        parser.error("--white-threshold debe estar entre 0 y 255")
    if args.min_area < 1:
        parser.error("--min-area debe ser mayor que 0")

    return args


args = parse_args(sys.argv[1:])
entrada = args.entrada
salida_dir = args.salida_dir
white_threshold = args.white_threshold
save_debug = args.save_debug
min_area = args.min_area
os.makedirs(salida_dir, exist_ok=True)
logger.info("Inicio de ejecución")
logger.info("Imagen de entrada: %s", entrada)
logger.info("Carpeta de salida: %s", salida_dir)
logger.info("white_threshold: %d", white_threshold)
logger.info("save_debug: %s", save_debug)
logger.info("min_area: %d", min_area)

# Cargar imagen
img = cv2.imread(entrada, cv2.IMREAD_COLOR)
if img is None:
    logger.error("No se pudo abrir la imagen: %s", entrada)
    sys.exit(1)
logger.info("Imagen cargada correctamente con tamaño: %sx%s", img.shape[1], img.shape[0])

# Convertir a RGB para trabajar mejor
img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
logger.info("Paso 1/4: imagen convertida a RGB")

# --------------------------------------------------
# 1) Crear una máscara de "todo lo que no sea blanco"
# --------------------------------------------------
# Fondo candidato: píxeles casi blancos
near_white = (np.all(img_rgb >= white_threshold, axis=2).astype(np.uint8) * 255)

# Fondo real: solo regiones casi blancas conectadas al borde
num_white_labels, white_labels, white_stats, _ = cv2.connectedComponentsWithStats(
    (near_white > 0).astype(np.uint8),
    connectivity=8,
)
fondo_conectado = np.zeros_like(near_white, dtype=np.uint8)
componentes_fondo_borde = 0

for i in range(1, num_white_labels):  # 0 es fondo de connected components
    x = white_stats[i, cv2.CC_STAT_LEFT]
    y = white_stats[i, cv2.CC_STAT_TOP]
    w = white_stats[i, cv2.CC_STAT_WIDTH]
    h = white_stats[i, cv2.CC_STAT_HEIGHT]

    toca_borde = x == 0 or y == 0 or (x + w) == img.shape[1] or (y + h) == img.shape[0]
    if toca_borde:
        fondo_conectado[white_labels == i] = 255
        componentes_fondo_borde += 1

# Contenido = todo lo que no pertenece al fondo conectado
mask = np.where(fondo_conectado == 255, 0, 255).astype(np.uint8)
pixeles_no_blancos = int(np.count_nonzero(mask))
pixeles_totales = int(mask.size)
logger.info(
    "Paso 1/4: máscara por fondo conectado creada (white_threshold=%d, componentes_fondo_borde=%d, no_fondo=%d/%d, %.2f%%)",
    white_threshold,
    componentes_fondo_borde,
    pixeles_no_blancos,
    pixeles_totales,
    (pixeles_no_blancos / pixeles_totales) * 100 if pixeles_totales else 0,
)

if save_debug:
    debug_mask_inicial = os.path.join(salida_dir, "debug_01_mask_inicial.png")
    guardar_debug_imagen(debug_mask_inicial, mask, "mascara inicial")

    debug_near_white = os.path.join(salida_dir, "debug_00_near_white.png")
    guardar_debug_imagen(debug_near_white, near_white, "candidatos casi blancos")

    debug_fondo_conectado = os.path.join(salida_dir, "debug_00_fondo_conectado.png")
    guardar_debug_imagen(debug_fondo_conectado, fondo_conectado, "fondo conectado al borde")

# --------------------------------------------------
# 2) Limpiar y consolidar las formas
# --------------------------------------------------
kernel = np.ones((3, 3), np.uint8)
mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

# Opcional: dilatar ligeramente para asegurar que círculo + icono queden
# como una sola unidad
mask = cv2.dilate(mask, np.ones((3, 3), np.uint8), iterations=1)
pixeles_post_morfologia = int(np.count_nonzero(mask))
logger.info(
    "Paso 2/4: morfología aplicada (pixeles activos tras limpieza: %d)",
    pixeles_post_morfologia,
)

if save_debug:
    debug_mask_limpia = os.path.join(salida_dir, "debug_02_mask_limpia.png")
    guardar_debug_imagen(debug_mask_limpia, mask, "mascara tras morfologia")

# --------------------------------------------------
# 3) Detectar componentes conectados
# --------------------------------------------------
num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
logger.info("Paso 3/4: connected components detectó %d etiquetas (incluyendo fondo)", num_labels)

componentes = []
descartados = 0
for i in range(1, num_labels):  # 0 es fondo
    x = stats[i, cv2.CC_STAT_LEFT]
    y = stats[i, cv2.CC_STAT_TOP]
    w = stats[i, cv2.CC_STAT_WIDTH]
    h = stats[i, cv2.CC_STAT_HEIGHT]
    area = stats[i, cv2.CC_STAT_AREA]

    # Filtrar basura pequeña
    if area > min_area:
        componentes.append((x, y, w, h, area, i))
    else:
        descartados += 1

logger.info(
    "Paso 3/4: componentes válidos=%d, descartados por área<=%d=%d",
    len(componentes),
    min_area,
    descartados,
)

if save_debug:
    debug_componentes = img.copy()
    for x, y, w, h, area, _ in componentes:
        cv2.rectangle(debug_componentes, (x, y), (x + w, y + h), (0, 180, 0), 2)
        cv2.putText(
            debug_componentes,
            f"OK {area}",
            (x, max(y - 8, 0)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 180, 0),
            1,
            cv2.LINE_AA,
        )

    for i in range(1, num_labels):
        x = stats[i, cv2.CC_STAT_LEFT]
        y = stats[i, cv2.CC_STAT_TOP]
        w = stats[i, cv2.CC_STAT_WIDTH]
        h = stats[i, cv2.CC_STAT_HEIGHT]
        area = stats[i, cv2.CC_STAT_AREA]
        if area <= min_area:
            cv2.rectangle(debug_componentes, (x, y), (x + w, y + h), (0, 0, 220), 1)

    debug_componentes_ruta = os.path.join(salida_dir, "debug_03_componentes.png")
    guardar_debug_imagen(debug_componentes_ruta, debug_componentes, "componentes detectados")

# Ordenar arriba-abajo, izquierda-derecha
componentes.sort(key=lambda c: (c[1] // 100, c[0]))
if not componentes:
    logger.warning(
        "No se encontraron componentes para exportar. Revisa umbral de blanco, tamaño mínimo de área o calidad de imagen."
    )

# --------------------------------------------------
# 4) Extraer cada badge con fondo transparente
# --------------------------------------------------
logger.info("Paso 4/4: iniciando exportación de badges")
indice_salida = 1
for idx, (x, y, w, h, area, label_id) in enumerate(componentes, start=1):
    padding = 25
    x1 = max(x - padding, 0)
    y1 = max(y - padding, 0)
    x2 = min(x + w + padding, img.shape[1])
    y2 = min(y + h + padding, img.shape[0])

    logger.info(
        "Badge %02d: bbox=(x=%d,y=%d,w=%d,h=%d), area=%d, recorte=(%d,%d)-(%d,%d)",
        idx,
        x,
        y,
        w,
        h,
        area,
        x1,
        y1,
        x2,
        y2,
    )

    crop_bgr = img[y1:y2, x1:x2]
    crop_rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)

    # Recrear máscara del recorte para transparencia
    crop_labels = labels[y1:y2, x1:x2]
    alpha = np.where(crop_labels == label_id, 255, 0).astype(np.uint8)

    # Suavizar un pelín bordes de alpha
    alpha = cv2.GaussianBlur(alpha, (3, 3), 0)
    alpha = np.where(alpha > 10, alpha, 0).astype(np.uint8)

    # Construir RGBA
    rgba = np.dstack([crop_rgb, alpha])

    salida, indice_usado = siguiente_badge_disponible(salida_dir, indice_salida)
    ok = cv2.imwrite(salida, cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGRA))
    if ok:
        logger.info("Guardado componente %02d en: %s", idx, salida)
    else:
        logger.warning("No se pudo guardar componente %02d en: %s", idx, salida)
    indice_salida = indice_usado + 1

logger.info("Terminado. Se generaron %d badges.", len(componentes))