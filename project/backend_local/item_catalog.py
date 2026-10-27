"""Local item catalog for the admin tools.

The catalog and icons are built from the client tables by tools/build_item_catalog.py.
They stay under data/ (git-ignored) and are served only through the admin API.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CATALOG_FILE = ROOT / "data" / "item_catalog.json"
ICON_DIR = ROOT / "data" / "item_icons"

_cache: dict = {"mtime": None, "items": []}


def load_items() -> list[dict]:
    """Catalog rows, reloaded when the file changes. Empty until the catalog is built."""
    try:
        mtime = CATALOG_FILE.stat().st_mtime
    except OSError:
        return []
    if _cache["mtime"] != mtime:
        try:
            rows = json.loads(CATALOG_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        _cache["items"] = rows
        _cache["mtime"] = mtime
    return _cache["items"]


def icon_bytes(item_id: int) -> bytes | None:
    """PNG bytes for one item icon, or None when the item has no icon."""
    try:
        return (ICON_DIR / f"{int(item_id)}.png").read_bytes()
    except OSError:
        return None
