"""Build the local item catalog (ids, names, icons) for the admin tools.

Inputs (client data, never published):
- the decrypted Item and TextData-English tables (recovered_local/tables/*.json);
- NewAssets.apk, for sprite frames (assets/res/import/*.json) and textures (assets/res/raw-assets);
- recovered/streamed_resources/assets/res (import JSON and raw-assets PNG/PKM), for the sprites and
  textures that NewAssets.apk does not ship.

Outputs (local, under backend_local/data, not for distribution):
- data/item_catalog.json   list of {id, name, type, icon}
- data/item_icons/<id>.png 96px icons cropped from the sprite frame rect
- data/ITEMS_LIST.txt      every item id with its name, type, and icon file

Usage:
    python tools/build_item_catalog.py <recovered_local dir> <NewAssets.apk>
"""

from __future__ import annotations

import io
import re
import json
import struct
import sys
import zipfile
from pathlib import Path

import texture2ddecoder
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
ICON_DIR = DATA / "item_icons"
ICON_SIZE = 96
B64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
STREAMED_RES = ROOT.parent / "recovered" / "streamed_resources" / "assets" / "res"
IMPORT_ROOT = STREAMED_RES / "import"
RAW_ROOT = STREAMED_RES / "raw-assets"
# Local packages that still carry textures missing from the streamed folder (our own loopback build).
# The installed game APK (pulled from the device) carries the sprite frames and textures the packages above lack.
EXTRA_ARCHIVES = [
    ROOT.parent / "extracted" / "apk" / "device_installed_base.apk",
    ROOT.parent / "releases" / "android16_loopback" / "SpiralWarrior_AllInOne_Loopback.apk",
]
EXTRA_TEXTURE_ARCHIVES = EXTRA_ARCHIVES
# PKM format codes (Khronos ETC): 0 ETC1 RGB, 1 ETC2 RGB, 3 ETC2 RGBA8 (the only one seen in this build).
PKM_DECODERS = {
    0: texture2ddecoder.decode_etc1,
    1: texture2ddecoder.decode_etc2,
    3: texture2ddecoder.decode_etc2a8,
}


def expand_uuid(short: str) -> str:
    value = 0
    for ch in short[2:]:
        value = (value << 6) | B64.index(ch)
    full = short[:2] + format(value, "030x")
    return f"{full[:8]}-{full[8:12]}-{full[12:16]}-{full[16:20]}-{full[20:]}"


def load_names(recovered: Path) -> dict[int, str]:
    rows = json.loads((recovered / "tables" / "TextData-English.json").read_text(encoding="utf-8"))["Items"]
    return {int(row["Id"]): str(row.get("English") or "").strip() for row in rows}


def import_documents(apk: zipfile.ZipFile):
    """Raw import JSON documents: NewAssets.apk first, then the streamed import folder."""
    for name in apk.namelist():
        if name.startswith("assets/res/import/") and name.endswith(".json"):
            yield apk.read(name)
    if IMPORT_ROOT.is_dir():
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


def decode_pkm(data: bytes) -> Image.Image | None:
    """Decode a PKM texture: 16-byte big-endian header, then the compressed 4x4 blocks."""
    if len(data) < 16 or data[:4] != b"PKM ":
        return None
    fmt, ext_w, ext_h, width, height = struct.unpack(">5H", data[6:16])
    decoder = PKM_DECODERS.get(fmt)
    if decoder is None:
        return None
    pixels = decoder(data[16:], ext_w, ext_h)
    image = Image.frombuffer("RGBA", (ext_w, ext_h), pixels, "raw", "BGRA", 0, 1)
    return image.crop((0, 0, width, height))


def load_texture(apk: zipfile.ZipFile, members: set[str], texture_short: str) -> Image.Image | None:
    return load_texture_full(apk, members, expand_uuid(texture_short))


def whole_image_index(recovered: Path) -> dict[str, str]:
    """Image name -> texture uuid for whole PNG assets listed in the client resource map (settings.js).

    Those assets are the icon itself, with no sprite rectangle to crop.
    """
    src = (recovered / "settings.js").read_text(encoding="utf-8", errors="replace")
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
    png = RAW_ROOT / texture[:2] / f"{texture}.png"
    if png.is_file():
        return Image.open(png).convert("RGBA")
    pkm = RAW_ROOT / texture[:2] / f"{texture}.pkm"
    if pkm.is_file():
        return decode_pkm(pkm.read_bytes())
    return load_extra_texture(texture)


def load_extra_texture(texture: str) -> Image.Image | None:
    """Look for the texture in the extra local archives (PNG first, then PKM)."""
    for archive_path in EXTRA_TEXTURE_ARCHIVES:
        if not archive_path.is_file():
            continue
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


def build_box_catalog(recovered: Path, items: list[dict]) -> int:
    """Weighted reward rows per box id (Chance table) and the opening delay in seconds (Item table)."""
    chance = json.loads((recovered / "tables" / "Chance.json").read_text(encoding="utf-8"))["Items"]
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


def build_skin_catalog(recovered: Path) -> int:
    """Part skins from the client SkinData table: skin id -> part, index and price (Worth)."""
    rows = json.loads((recovered / "tables" / "SkinData.json").read_text(encoding="utf-8"))["Items"]
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


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    recovered = Path(sys.argv[1])
    apk_path = Path(sys.argv[2])
    names = load_names(recovered)
    items = json.loads((recovered / "tables" / "Item.json").read_text(encoding="utf-8"))["Items"]
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(apk_path) as apk:
        sprites = sprite_index(apk)
        whole_images = whole_image_index(recovered)
        for extra in EXTRA_ARCHIVES:
            if extra.is_file():
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
    print(f"boxes {build_box_catalog(recovered, items)}")
    print(f"skins {build_skin_catalog(recovered)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
