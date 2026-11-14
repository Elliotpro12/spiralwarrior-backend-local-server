# Cómo generar los catálogos del backend

Este repositorio **no contiene datos del juego**. Los catálogos (`data/*.json`), los iconos (`data/item_icons/`) y las tablas del cliente se generan en tu PC a partir de **tu propia copia** de Spiral Warrior 1.1.0.96, que debes tener derecho a inspeccionar. No compartas esos archivos ni los subas a Git.

Las herramientas de esta carpeta hacen la parte pública del proceso: convertir tablas y recursos que ya tienes en catálogos del backend, y clasificarlos. Algunos pasos no están incluidos (ver [Qué falta](#qué-falta)).

## Requisitos

- Windows 10/11 o Linux, Python 3.10 o superior.
- Dependencias de Python para generar iconos y texturas:

```bash
pip install pillow texture2ddecoder
```

- Tu XAPK de Spiral Warrior 1.1.0.96 (no se incluye).
- Opcional: APK adicionales de la misma versión, para texturas que faltan en el recurso en streaming.

## Resumen del flujo

| Paso | Herramienta | Entrada | Salida | Estado |
|---|---|---|---|---|
| 1. Índice de recursos | `analyze_lebian_stream.py` | tu XAPK | índice CSV y `tryflag.txt` | incluida |
| 2. Recursos en streaming | `download_streamed_resources.py` | índice y `tryflag` | carpeta `assets/res/` | incluida |
| 3. Tablas del cliente | (no incluida) | `NewAssets.apk` y `settings.js` | `Item.json`, `TextData-English.json`, `Chance.json`, `SkinData.json` | **no incluida** |
| 4. Catálogos | `build_item_catalog.py` | tablas, `settings.js`, `NewAssets.apk`, recursos | `data/item_catalog.json`, `item_icons/`, `box_catalog.json`, `skin_catalog.json`, `ITEMS_LIST.txt` | incluida |
| 5. Clasificación | `classify_items.py` | `data/item_catalog.json` | `data/ITEMS_CLASSIFIED.tsv` | incluida |

Desde la carpeta `project/backend_local` ejecuta los comandos de los pasos 4 y 5. Los pasos 1 y 2 se pueden ejecutar desde cualquier carpeta.

## Paso 1: índice de recursos desde tu XAPK

```bash
python tools/analyze_lebian_stream.py "ruta/a/Spiral+Warrior_1.1.0.96.xapk" --output "ruta/a/salida_indice"
```

Genera `lebian_stream_resource_index.csv` (el índice de recursos) y `tryflag.txt` (extraído del mismo paquete), además de un resumen. Los dos archivos que necesitas en el paso 2 son esos.

## Paso 2: recursos en streaming

```bash
python tools/download_streamed_resources.py \
  --index "ruta/a/salida_indice/lebian_stream_resource_index.csv" \
  --tryflag "ruta/a/salida_indice/tryflag.txt" \
  --output-dir "ruta/a/recovered/streamed_resources"
```

Descarga solo los recursos del índice desde espejos públicos, con dos conexiones como máximo y pausas entre peticiones. Verifica tamaño y CRC32 de cada archivo. Lee antes [`project/backend_local/ASSET_MIRRORS_AND_RECOVERY.md`](../ASSET_MIRRORS_AND_RECOVERY.md) y respeta sus límites.

Al terminar debe existir la carpeta `…/streamed_resources/assets/res/` con `import/` (unos 288 JSON) y `raw-assets/` (unos 3900 archivos). Esa carpeta `res` es lo que pasas a `--streamed`.

## Paso 3: tablas del cliente (no incluido)

El paso 4 necesita cuatro tablas en una sola carpeta:

- `Item.json`
- `TextData-English.json`
- `Chance.json`
- `SkinData.json`

Las tablas se obtienen descifrando los archivos de datos del cliente. Ese paso no está en el repositorio, así que hoy no puedes generarlas desde aquí. Si ya tienes esas cuatro tablas de una copia tuya del cliente, sigue con el paso 4.

Necesitas además `settings.js` de la misma versión, que mapea los UUID de las texturas.

## Paso 4: catálogos de objetos, iconos, cajas y skins

Desde `project/backend_local`:

```bash
python tools/build_item_catalog.py \
  --tables "ruta/a/tablas" \
  --settings "ruta/a/settings.js" \
  --apk "ruta/a/NewAssets.apk" \
  --streamed "ruta/a/recovered/streamed_resources/assets/res" \
  --extra-apk "ruta/a/otro_apk_de_la_misma_version.apk" \
  --out "data"
```

- `--apk` es `NewAssets.apk`, extraído del XAPK.
- `--streamed` y `--extra-apk` son opcionales. Sin ellos se generan menos iconos (en nuestra prueba, 105 objetos sin icono en vez de 65).
- `--out` es la carpeta de salida. Por defecto es `data/`, que es lo que lee el servidor.

Resultado esperado con una copia idéntica de la versión 1.1.0.96:

| Archivo | Cantidad esperada |
|---|---|
| `item_catalog.json` | 1233 objetos |
| `item_icons/*.png` | 1168 iconos (65 objetos sin icono) |
| `box_catalog.json` | 117 cajas |
| `skin_catalog.json` | 251 skins |
| `ITEMS_LIST.txt` | una línea por objeto |

En nuestra comprobación, los tres JSON (`item_catalog`, `box_catalog` y `skin_catalog`), `ITEMS_LIST.txt` y 1009 de 1168 iconos coinciden byte a byte con los de referencia. Los otros 159 iconos vienen de texturas PKM, y sus píxeles difieren en algunos puntos. No hemos encontrado la causa, así que pueden verse ligeramente distintos.

## Paso 5: clasificación

```bash
python tools/classify_items.py
```

Escribe `data/ITEMS_CLASSIFIED.tsv` con cada objeto, su tipo del cliente, su categoría y el destino que le da el servidor. La clasificación usa la enum `Item_ItemType` del cliente (líneas 102760-102799 de `project.js`).

## Qué falta

**Tablas del cliente (paso 3).** No están incluidas. Sin ellas no puedes ejecutar el paso 4 desde cero.

**Catálogos de exportación en vivo.** Estos archivos no los genera ninguna herramienta de este repositorio. Se obtuvieron ejecutando el juego en un emulador con Frida, o desde un volcado de su tabla en tiempo de ejecución:

- `guaji_pve_catalog.json`, `chapter_pve_catalog.json`
- `item_upgrade_catalog.json`, `part_item_catalog.json`
- `roguelike_shop_prices.json`, `roguelike_event_type_catalog.json`, `roguelike_export_items.json`
- `local_free_purchase_catalog.json`
- `lottery_catalog.json`

**Catálogos sin generador conocido.** `level_progression_catalog.json`, `level_up_exchanges.json`, `order_exchange_catalog.json` y `task_data_catalog.json` no tienen un script que los regenere. Hace falta investigarlos antes de prometer su reproducción.

## Estado y derechos

Los archivos generados contienen datos derivados del cliente de Spiral Warrior. El repositorio no tiene licencia sobre esos datos y su titularidad está en revisión. No los subas a Git ni los compartas. Si quieres usar el backend con tus propios datos, genéralos en tu PC.
