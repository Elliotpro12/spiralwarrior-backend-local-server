"""Part skins (item type 10): ownership, purchase and equip for each top part.

Client facts (observed in the client code):
- Skin_Change(partId, skinIndex) sends CS_ItemOpr{itemOpr=6 (E_ITEM_USE_SKIN), itemKey=part id, param1=skin index}.
- Item_Buy_Skin(skinId) sends CS_ItemOpr{itemOpr=8 (E_ITEM_BUY_SKIN), itemKey=skin id}. Success is ret 21
  (E_ITEMRET_BUY_SKIN_OK). The buy button only appears when Worth.Num > 0.
- Part data: ToytopPartProto.Skin is the bit mask of owned skin indexes; CurSkin is the equipped index.
- Money types: E_MONEY_DIAMOND = 0, E_MONEY_GOLD = 1.

Inferred, not verified in game: a skin is owned when its item is in the inventory or when its index is 0.
Skins without Worth are not sold; they are only granted by other systems.
"""

from __future__ import annotations

import json
from pathlib import Path

OPR_USE_SKIN = 6
OPR_BUY_SKIN = 8

RET_INVALID_ITEM = 1
RET_SYSTEM_ERROR = 8
RET_USE_OK = 14
RET_MONEY_NOT_ENOUGH = 17
RET_BUY_SKIN_OK = 21

MONEY_DIAMOND = 0
MONEY_GOLD = 1
DIAMOND_ITEM_ID = 1227894834
GOLD_ITEM_ID = 1227894833

SKIN_CATALOG_FILE = Path(__file__).resolve().parent / "data" / "skin_catalog.json"
_skin_cache: dict[str, object] = {"mtime": None, "skins": {}}


def load_skin_catalog(path: Path = SKIN_CATALOG_FILE) -> dict[int, dict[str, int]]:
    """Skin id -> {"part", "index", "worth_id", "worth_num"}. Empty until tools/build_item_catalog.py runs."""
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return {}
    if _skin_cache["mtime"] != mtime:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        _skin_cache["skins"] = {int(key): value for key, value in raw.items()}
        _skin_cache["mtime"] = mtime
    return _skin_cache["skins"]


def is_owned(skin_id: int, skin: dict[str, int], inventory: dict[int, int]) -> bool:
    return skin["index"] == 0 or int(inventory.get(int(skin_id), 0)) > 0


def part_skin_mask(part_id: int, catalog: dict[int, dict[str, int]], inventory: dict[int, int]) -> int:
    """Bit mask of owned skin indexes for one part (ToytopPartProto.Skin)."""
    mask = 0
    for skin_id, skin in catalog.items():
        if skin["part"] == int(part_id) and is_owned(skin_id, skin, inventory):
            mask |= 1 << skin["index"]
    return mask


def plan_buy(skin_id: int, catalog: dict[int, dict[str, int]],
             inventory: dict[int, int]) -> tuple[int, int, int, int]:
    """Check a purchase. Returns (ret, cost item id, cost quantity, money type for a shortfall)."""
    skin = catalog.get(int(skin_id))
    if skin is None or skin["worth_num"] <= 0 or int(inventory.get(int(skin_id), 0)) > 0:
        return RET_INVALID_ITEM, 0, 0, 0
    cost_id, cost_num = skin["worth_id"], skin["worth_num"]
    money = MONEY_DIAMOND if cost_id == DIAMOND_ITEM_ID else MONEY_GOLD
    if int(inventory.get(cost_id, 0)) < cost_num:
        return RET_MONEY_NOT_ENOUGH, cost_id, cost_num, money
    return RET_BUY_SKIN_OK, cost_id, cost_num, money


def plan_use(part_id: int, index: int, catalog: dict[int, dict[str, int]],
             inventory: dict[int, int]) -> int:
    """Check an equip request: the skin for this part and index must exist and be owned."""
    for skin_id, skin in catalog.items():
        if skin["part"] == int(part_id) and skin["index"] == int(index):
            return RET_USE_OK if is_owned(skin_id, skin, inventory) else RET_INVALID_ITEM
    return RET_INVALID_ITEM
