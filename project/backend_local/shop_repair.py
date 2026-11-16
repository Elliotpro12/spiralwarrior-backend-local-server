"""ECS_ShopOpr (137) for the Store > Packs > Launcher > Repair Kits shop.

Observed in the client (agent2/analysis/jsc/recovered_local/project.js):
- CS_ShopOpr fields: 3 goodsID, 4 goodsNum, 5 costType.
- SC_ShopOpr (ESC_ShopOpr, id 138) field 1 shopOprRet; E_ShopOprRet: 0 unknown,
  1 invalid goods, 2 invalid money, 6 shopping OK.
- The repair goods list (StaticShop type 3, RepairPackage) is sent by the original
  server; it is not in the local data, so the goods table here starts empty and is
  filled from captured requests (logs/shop_capture.jsonl).

Unknown until captured: goods IDs, price per unit, and currency for each good.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
TABLE_PATH = ROOT / "data" / "repair_kit_shop.json"
CAPTURE_PATH = ROOT / "logs" / "shop_capture.jsonl"

SHOP_OPR_REQUEST = 137
SHOP_OPR_RESPONSE = 138
RET_UNKNOWN = 0
RET_INVALID_GOODS = 1
RET_INVALID_MONEY = 2
RET_SHOPPING_OK = 6
COST_DIAMOND_ITEM_ID = 1227894834


def load_table() -> dict[int, dict[str, Any]]:
    """goodsID -> {"item_id", "per_unit", "cost_id", "cost_per_unit"}; empty until captured."""
    try:
        raw = json.loads(TABLE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    table: dict[int, dict[str, Any]] = {}
    for key, row in raw.get("goods", {}).items():
        if str(key).isdigit() and isinstance(row, dict):
            table[int(key)] = row
    return table


def capture(goods_id: int, goods_num: int, cost_type: int, ret: int) -> None:
    """Keep every request so the goods table can be completed from the game."""
    CAPTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    row = {"time": time.strftime("%Y-%m-%dT%H:%M:%S"), "goods_id": goods_id,
           "goods_num": goods_num, "cost_type": cost_type, "ret": ret}
    with CAPTURE_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")


def plan_purchase(goods_id: int, goods_num: int, inventory: dict[int, int],
                  table: dict[int, dict[str, Any]]) -> tuple[int, dict[str, Any] | None]:
    """Check a purchase against the table. Returns (ret, plan) with plan=None unless OK."""
    row = table.get(int(goods_id))
    if row is None or goods_num <= 0:
        return RET_INVALID_GOODS, None
    cost_id = int(row["cost_id"])
    cost = int(row["cost_per_unit"]) * int(goods_num)
    if int(inventory.get(cost_id, 0)) < cost:
        return RET_INVALID_MONEY, None
    grant = int(row["per_unit"]) * int(goods_num)
    return RET_SHOPPING_OK, {"item_id": int(row["item_id"]), "grant": grant,
                             "cost_id": cost_id, "cost": cost}
