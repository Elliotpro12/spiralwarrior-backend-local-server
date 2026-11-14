"""Item classification for the local backend.

Categories come from the client enum Item_ItemType (agent2/analysis/jsc/recovered_local/project.js,
lines 102760-102799; the Item table field is "itemType"). Each catalog row in data/item_catalog.json
is classified by its numeric type, with a few id overrides where the server keeps a scalar counter.

Destinations describe where the local server credits an item when it is granted:
- part_fragments: parts (LocationTop/Middle/Bottom), stored with their levels;
- save_box: chests and boxes, placed in a free save slot when granted by mail;
- task_score / achievement_score: scalar profile counters that the client reads (BaseInfo);
- inventory: counted items in the profile inventory (currency, skins, cosmetics, materials...).
"""

from __future__ import annotations

from typing import Any

import item_catalog
import save_boxes

# Client enum Item_ItemType, value -> name (observed in the recovered client bundle).
TYPE_NAMES: dict[int, str] = {
    0: "LocationTop", 1: "LocationMiddle", 2: "LocationBottom", 3: "MoneyGold", 4: "MoneyDiamond",
    5: "Box2Open", 6: "Box2Save", 7: "PlayerExp", 8: "TaskScore", 9: "HeadIcon", 10: "PartSkin",
    11: "Emitter", 12: "AchievementPoint", 13: "NumOnlyItem", 14: "VipBuff", 15: "ItemWrapper",
    16: "EmitterHP", 17: "AllPartType", 18: "Expression", 19: "ClientOnly", 20: "RogueLikeItem",
    21: "Kern", 22: "EmitterMaterial", 23: "MythPartNum", 24: "RogueLikeKey", 25: "Currency",
    26: "HeadFrame", 27: "Scene", 28: "PartNoticePiece", 29: "Box2Select", 30: "SecretAreaKey",
    31: "SecretAreaExp", 32: "ClubScore", 33: "SecretAreaTalentExp", 34: "BattlePassItem",
    35: "BattlePassTicket", 36: "Stamp", 37: "Bubble", 38: "PlayerCard", 39: "TopChampCup",
}

# Category by client type. Every type present in the catalog has one.
CATEGORY_BY_TYPE: dict[int, str] = {
    0: "part", 1: "part", 2: "part",
    3: "currency", 4: "currency", 25: "currency",
    7: "player_exp",
    8: "points", 12: "points", 32: "club",
    5: "box", 6: "box", 29: "box",
    10: "skin",
    9: "cosmetic", 26: "cosmetic", 27: "cosmetic", 37: "cosmetic", 38: "cosmetic",
    18: "collectible", 36: "collectible", 39: "collectible",
    11: "part_material", 15: "part_material", 16: "part_material", 17: "part_material",
    21: "part_material", 22: "part_material", 23: "part_material", 28: "part_material",
    13: "number_only",
    14: "vip_buff",
    19: "client_only",
    20: "roguelike", 24: "roguelike",
    30: "secret_area", 31: "secret_area", 33: "secret_area",
    34: "battle_pass", 35: "battle_pass",
}

CATEGORY_BY_TYPE_DESTINATION = {"part": "part_fragments", "box": "save_box", "player_exp": "player_exp", "club": "club_score"}

# Ids the server reads as scalar counters or special currencies.
GOLD_ITEM_ID = 1227894833
DIAMOND_ITEM_ID = 1227894834
TASK_SCORE_ITEM_ID = 1227894838
ACHIEVEMENT_POINT_ITEM_ID = 1227894839

_ID_OVERRIDES: dict[int, tuple[str, str]] = {
    GOLD_ITEM_ID: ("currency", "inventory"),
    DIAMOND_ITEM_ID: ("currency", "inventory"),
    TASK_SCORE_ITEM_ID: ("points", "task_score"),
    ACHIEVEMENT_POINT_ITEM_ID: ("points", "achievement_score"),
}

_cache: dict[str, Any] = {"rows": None, "box_ids": frozenset(), "registry": {}}


def classify_row(row: dict[str, Any], box_ids: set[int] = frozenset()) -> dict[str, Any]:
    item_id = int(row["id"])
    item_type = int(row.get("type", -1))
    category = CATEGORY_BY_TYPE.get(item_type, "unclassified")
    destination = CATEGORY_BY_TYPE_DESTINATION.get(category, "inventory")
    if item_id in box_ids:
        # The server opens an item as a box when box_catalog.json lists it, whatever its client type.
        category, destination = "box", "save_box"
    if item_id in _ID_OVERRIDES:
        category, destination = _ID_OVERRIDES[item_id]
    name = str(row.get("name") or "")
    return {
        "id": item_id,
        "name": name,
        "named": bool(name) and not (name.startswith("Item ") and name[5:].isdigit()),
        "type": item_type,
        "type_name": TYPE_NAMES.get(item_type, "Unknown"),
        "category": category,
        "destination": destination,
        "icon": bool(row.get("icon")),
    }


def registry() -> dict[int, dict[str, Any]]:
    """Classification of every catalog row, rebuilt when the catalog or the box catalog changes."""
    rows = item_catalog.load_items()
    box_ids = frozenset(int(key) for key in save_boxes.load_box_catalog())
    if _cache["rows"] is not rows or _cache["box_ids"] != box_ids:
        _cache["registry"] = {int(row["id"]): classify_row(row, box_ids) for row in rows}
        _cache["rows"] = rows
        _cache["box_ids"] = box_ids
    return _cache["registry"]


def classify(item_id: int) -> dict[str, Any] | None:
    return registry().get(int(item_id))


def destination_for(item_id: int) -> str:
    entry = classify(item_id)
    return entry["destination"] if entry else "inventory"


def known_ids() -> set[int]:
    return set(registry().keys())
