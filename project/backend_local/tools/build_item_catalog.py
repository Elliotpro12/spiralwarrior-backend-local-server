"""Build the local item, box and skin catalogs from your own copy of the game.

Nothing in this repository contains game data. You provide the inputs from a copy of
Spiral Warrior 1.1.0.96 that you are allowed to inspect. See tools/README.md for the full procedure.

Inputs
- --tables DIR     decrypted client tables: Item.json, TextData-English.json, Chance.json, SkinData.json
- --settings FILE  the client settings.js (texture uuid map)
- --apk FILE       NewAssets.apk from the same client version (sprite frames and textures)
- --streamed DIR   optional: streamed resources folder containing import/ and raw-assets/
- --extra-apk FILE optional, repeatable: other APKs of the same version that carry missing textures

Outputs (default: backend_local/data, git-ignored)
- item_catalog.json       list of {id, name, type, icon}
- item_icons/<id>.png     96px icons cropped from the sprite frame rect
- ITEMS_LIST.txt          every item id with its name, type and icon file
- box_catalog.json        reward rows per box id (Chance table) and opening delay
- skin_catalog.json       part skins (SkinData table)

Usage (from backend_local):
    python tools/build_item_catalog.py --tables <tables dir> --settings <settings.js> --apk <NewAssets.apk>
"""

from __future__ import annotations

import argparse
import io
import json
import re
import struct
import sys
import zipfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ICON_SIZE = 96
B64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"

# Set by main() from the command line.
DATA = ROOT / "data"
ICON_DIR = DATA / "item_icons"
IMPORT_ROOT: Path | None = None
RAW_ROOT: Path | None = None
EXTRA_ARCHIVES: list[Path] = []


def expand_uuid(short: str) -> str:
    value = 0
    for ch in short[2:]:
        value = (value << 6) | B64.index(ch)
    full = short[:2] + format(value, "030x")
    return f"{full[:8]}-{full[8:12]}-{full[12:16]}-{full[16:20]}-{full[20:]}"


def read_table(tables: Path, name: str) -> dict:
    return json.loads((tables / name).read_text(encoding="utf-8"))


def load_names(tables: Path) -> dict[int, str]:
    rows = read_table(tables, "TextData-English.json")["Items"]
    return {int(row["Id"]): str(row.get("English") or "").strip() for row in rows}


def import_documents(apk: zipfile.ZipFile):
    """Raw import JSON documents: NewAssets.apk first, then the streamed import folder."""
    for name in apk.namelist():
        if name.startswith("assets/res/import/") and name.endswith(".json"):
            yield apk.read(name)
    if IMPORT_ROOT is not None and IMPORT_ROOT.is_dir():
        for path in sorted(IMPORT_ROOT.rglob("*.json")):
            yield path.read_bytes()


def sprite_index(apk: zipfile.ZipFile) -> dict[str, tuple[str, list[int]]]:
    """Sprite frame name -> (texture short uuid, rect) from every import JSON."""
    index: dict[str, tuple[str, list[int]]] = {}
    for raw in import_documents(apk):
        try:
            entries = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict) or entry.get("__type__") != "cc.SpriteFrame":
                continue
            content = entry.get("content") or {}
            sprite = content.get("name")
            if sprite and sprite not in index and content.get("texture") and content.get("rect"):
                index[sprite] = (content["texture"], content["rect"])
    return index


def pkm_decoders() -> dict[int, object]:
    """PKM format codes (Khronos ETC): 0 ETC1 RGB, 1 ETC2 RGB, 3 ETC2 RGBA8 (the only one seen in this build).

    texture2ddecoder is imported here, so the rest of the tool runs without it.
    """
    import texture2ddecoder
    return {
        0: texture2ddecoder.decode_etc1,
        1: texture2ddecoder.decode_etc2,
        3: texture2ddecoder.decode_etc2a8,
    }


def decode_pkm(data: bytes) -> Image.Image | None:
    """Decode a PKM texture: 16-byte big-endian header, then the compressed 4x4 blocks."""
    if len(data) < 16 or data[:4] != b"PKM ":
        return None
    fmt, ext_w, ext_h, width, height = struct.unpack(">5H", data[6:16])
    decoder = pkm_decoders().get(fmt)
    if decoder is None:
        return None
    pixels = decoder(data[16:], ext_w, ext_h)
    image = Image.frombuffer("RGBA", (ext_w, ext_h), pixels, "raw", "BGRA", 0, 1)
    return image.crop((0, 0, width, height))


def load_texture(apk: zipfile.ZipFile, members: set[str], texture_short: str) -> Image.Image | None:
    return load_texture_full(apk, members, expand_uuid(texture_short))


def whole_image_index(settings: Path) -> dict[str, str]:
    """Image name -> texture uuid for whole PNG assets listed in the client resource map (settings.js).

    Those assets are the icon itself, with no sprite rectangle to crop.
    """
    src = settings.read_text(encoding="utf-8", errors="replace")
    uuids = json.loads(re.search(r"uuids:(\[.*?\])", src, re.S).group(1))
    index: dict[str, str] = {}
    for match in re.finditer(r'"(\d+)":\["([^"]+\.png)",5\]', src):
        name = match.group(2).rsplit("/", 1)[-1][:-4]
        index.setdefault(name, expand_uuid(uuids[int(match.group(1))]))
    return index


def load_texture_full(apk: zipfile.ZipFile, members: set[str], texture: str) -> Image.Image | None:
    member = f"assets/res/raw-assets/{texture[:2]}/{texture}.png"
    if member in members:
        return Image.open(io.BytesIO(apk.read(member))).convert("RGBA")
    if RAW_ROOT is not None:
        png = RAW_ROOT / texture[:2] / f"{texture}.png"
        if png.is_file():
            return Image.open(png).convert("RGBA")
        pkm = RAW_ROOT / texture[:2] / f"{texture}.pkm"
        if pkm.is_file():
            return decode_pkm(pkm.read_bytes())
    return load_extra_texture(texture)


def load_extra_texture(texture: str) -> Image.Image | None:
    """Look for the texture in the extra APKs given with --extra-apk (PNG first, then PKM)."""
    for archive_path in EXTRA_ARCHIVES:
        with zipfile.ZipFile(archive_path) as archive:
            names = set(archive.namelist())
            png = f"assets/res/raw-assets/{texture[:2]}/{texture}.png"
            if png in names:
                return Image.open(io.BytesIO(archive.read(png))).convert("RGBA")
            pkm = f"assets/res/raw-assets/{texture[:2]}/{texture}.pkm"
            if pkm in names:
                return decode_pkm(archive.read(pkm))
    return None


def crop_icon(texture: Image.Image, rect: list[int]) -> Image.Image | None:
    x, y, w, h = (int(v) for v in rect)
    if w <= 0 or h <= 0:
        return None
    icon = texture.crop((x, y, x + w, y + h))
    icon.thumbnail((ICON_SIZE, ICON_SIZE))
    return icon


def build_box_catalog(tables: Path, items: list[dict]) -> int:
    """Weighted reward rows per box id (Chance table) and the opening delay in seconds (Item table)."""
    chance = read_table(tables, "Chance.json")["Items"]
    delays = {int(row["ItemId"]): int(float(row.get("DelayOpenTime") or 0)) for row in items}
    boxes: dict[str, dict] = {}
    for row in chance:
        box_id = int(row["BoxID"])
        reward = row.get("reward") or {}
        entry = boxes.setdefault(str(box_id), {"delay": delays.get(box_id, 0), "rows": []})
        entry["rows"].append({
            "random_index": int(float(row.get("RandomIndex") or 0)),
            "pvalue": int(float(row.get("Pvalue") or 0)),
            "item": int(reward.get("ID") or 0),
            "num": int(reward.get("Num") or 0),
            "level": int(float(row.get("Level") or 0)),
            "ranks": [int(float(row.get(f"NumRank{rank}") or 0)) for rank in range(1, 8)],
        })
    (DATA / "box_catalog.json").write_text(json.dumps(boxes, ensure_ascii=False), encoding="utf-8")
    return len(boxes)


def build_skin_catalog(tables: Path) -> int:
    """Part skins from the client SkinData table: skin id -> part, index and price (Worth)."""
    rows = read_table(tables, "SkinData.json")["Items"]
    skins = {}
    for row in rows:
        worth = row.get("Worth") or {}
        skins[str(int(row["SkinID"]))] = {
            "part": int(row["PartID"]),
            "index": int(row["SkinIndex"]),
            "worth_id": int(worth.get("ID") or 0),
            "worth_num": int(worth.get("Num") or 0),
        }
    (DATA / "skin_catalog.json").write_text(json.dumps(skins, ensure_ascii=False), encoding="utf-8")
    return len(skins)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tables", type=Path, required=True, help="folder with the decrypted client tables")
    parser.add_argument("--settings", type=Path, required=True, help="client settings.js")
    parser.add_argument("--apk", type=Path, required=True, help="NewAssets.apk of the same client version")
    parser.add_argument("--streamed", type=Path, help="streamed resources folder (import/ and raw-assets/)")
    parser.add_argument("--extra-apk", type=Path, action="append", default=[], help="extra APK, repeatable")
    parser.add_argument("--out", type=Path, default=ROOT / "data", help="output folder (default: backend_local/data)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    global DATA, ICON_DIR, IMPORT_ROOT, RAW_ROOT, EXTRA_ARCHIVES
    args = parse_args(sys.argv[1:] if argv is None else argv)
    for required in (args.tables, args.settings, args.apk):
        if not required.exists():
            print(f"Missing input: {required}")
            return 2
    for name in ("Item.json", "TextData-English.json", "Chance.json", "SkinData.json"):
        if not (args.tables / name).is_file():
            print(f"Missing table: {args.tables / name}")
            return 2
    DATA = args.out
    ICON_DIR = DATA / "item_icons"
    if args.streamed is not None:
        IMPORT_ROOT = args.streamed / "import"
        RAW_ROOT = args.streamed / "raw-assets"
    EXTRA_ARCHIVES = [path for path in args.extra_apk if path.is_file()]
    missing_extra = [str(path) for path in args.extra_apk if not path.is_file()]
    if missing_extra:
        print("Extra APK not found, continuing without it:", ", ".join(missing_extra))

    names = load_names(args.tables)
    items = read_table(args.tables, "Item.json")["Items"]
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.apk) as apk:
        sprites = sprite_index(apk)
        whole_images = whole_image_index(args.settings)
        for extra in EXTRA_ARCHIVES:
            with zipfile.ZipFile(extra) as other:
                for name, value in sprite_index(other).items():
                    sprites.setdefault(name, value)
        members = set(apk.namelist())
        textures: dict[str, Image.Image | None] = {}
        catalog = []
        icons_written = 0
        for item in sorted(items, key=lambda row: int(row["ItemId"])):
            item_id = int(item["ItemId"])
            name = names.get(int(item.get("name") or 0)) or f"Item {item_id}"
            icon_file = None
            sprite_name = str(item.get("iconPath") or "").rsplit("/", 1)[-1]
            if sprite_name not in sprites and sprite_name in whole_images:
                whole = load_texture_full(apk, members, whole_images[sprite_name])
                if whole is not None:
                    whole.thumbnail((ICON_SIZE, ICON_SIZE))
                    icon_file = f"{item_id}.png"
                    whole.save(ICON_DIR / icon_file)
                    icons_written += 1
            elif sprite_name in sprites:
                texture_short, rect = sprites[sprite_name]
                if texture_short not in textures:
                    textures[texture_short] = load_texture(apk, members, texture_short)
                texture = textures[texture_short]
                image = crop_icon(texture, rect) if texture is not None else None
                if image is not None:
                    icon_file = f"{item_id}.png"
                    image.save(ICON_DIR / icon_file)
                    icons_written += 1
            catalog.append({"id": item_id, "name": name, "type": int(item.get("itemType") or 0),
                            "icon": icon_file})
    (DATA / "item_catalog.json").write_text(json.dumps(catalog, ensure_ascii=False), encoding="utf-8")
    lines = ["ID\tNOMBRE\tTIPO\tICONO"]
    lines += [f"{row['id']}\t{row['name']}\t{row['type']}\t{row['icon'] or '-'}" for row in catalog]
    (DATA / "ITEMS_LIST.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"items {len(catalog)}, icons {icons_written}, without icon {len(catalog) - icons_written}")
    print(f"boxes {build_box_catalog(args.tables, items)}")
    print(f"skins {build_skin_catalog(args.tables)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
