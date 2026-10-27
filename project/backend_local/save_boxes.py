"""Save-box slots: timed chests the client opens from BaseInfo.SaveBoxList.

Client contract (observed in the client code, see the ItemOpr notes):
- ECS_ItemOpr (135) E_ITEM_BOX_COUNTDOWN (4): itemKey=box id, param1=slot key. Starts the timer.
- ECS_ItemOpr (135) E_ITEM_USE_ITEM (3): itemKey=box id, param1=slot key, param2=1 free or 0 paid.
  Opens an unlocked slot for free, or pays diamonds to open a slot that is still counting down.
- A slot with CanOpenTime == 0 is locked; the client shows it as "start countdown".
- Rewards come back as SC_GetItems.BoxList (GetItemFrom=GIF_OPENBOX), the same envelope as lottery.

Loot pools: a chest's rows are grouped by RandomIndex, one weighted row is picked per group, rows
above the player's RaceScore are skipped, and a picked row that is itself a chest opens recursively.
This matches the client preview (getBoxInfo) and the in-game reveal for the Epic and Mystery chests.

Inferred or not verified in game:
- which granted boxes enter a free slot (the backend places mission chests there);
- the lineup (ops 5, 21) and the ad speed-up (op 7) are not implemented.
"""

from __future__ import annotations

import json
import math
import secrets
from pathlib import Path
from typing import Callable

MAX_SAVEBOX_NUM = 4  # Client constant MAX_SAVEBOX_NUM: slots the client draws.
# Chests beyond the visible slots stay in SaveBoxList as locked entries (the client shows them when a
# slot frees). The storage limit is not in the client; this value is an inferred cap.
MAX_STORED_BOXES = 32
FREE_OPEN_SECONDS = 600  # Client FREE_OPEN_BOX_TIME_RATIO: remaining time under this opens for free.
PURCHASE_TIME_SECONDS = 1200  # Client PURCHASE_OPEN_BOX_TIME_RATIO: one diamond per this many seconds.
PURCHASE_COST_PER_UNIT = 1  # Client PURCHASE_OPEN_BOX_COST_RATIO.

OPEN_OK = "ok"
OPEN_NOT_READY = "not_ready"
OPEN_INVALID = "invalid"

BOX_CATALOG_FILE = Path(__file__).resolve().parent / "data" / "box_catalog.json"
_box_catalog_cache: dict[str, object] = {"mtime": None, "boxes": {}}


def load_box_catalog(path: Path = BOX_CATALOG_FILE) -> dict[int, dict[str, object]]:
    """Box id -> {"delay": seconds, "rows": [...]}. Empty until tools/build_item_catalog.py runs."""
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return {}
    if _box_catalog_cache["mtime"] != mtime:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        _box_catalog_cache["boxes"] = {int(key): value for key, value in raw.items()}
        _box_catalog_cache["mtime"] = mtime
    return _box_catalog_cache["boxes"]


def normalize_save_boxes(raw: object) -> dict[int, dict[str, int]]:
    """Profile state -> {slot key: {"id", "can_open", "ready"}} limited to the stored slot keys."""
    if not isinstance(raw, dict):
        return {}
    slots: dict[int, dict[str, int]] = {}
    for key, value in raw.items():
        if not str(key).lstrip("-").isdigit() or not isinstance(value, dict):
            continue
        slot_key = int(key)
        if not 1 <= slot_key <= MAX_STORED_BOXES:
            continue
        box_id = int(value.get("id", 0))
        if box_id <= 0:
            continue
        slots[slot_key] = {
            "id": box_id,
            "can_open": max(0, int(value.get("can_open", 0))),
            "ready": max(0, int(value.get("ready", 0))),
        }
    return slots


def free_slot_key(slots: dict[int, dict[str, int]]) -> int | None:
    """Lowest empty slot key, or None when the storage is full."""
    for key in range(1, MAX_STORED_BOXES + 1):
        if key not in slots:
            return key
    return None


def place_box(slots: dict[int, dict[str, int]], box_id: int,
              catalog: dict[int, dict[str, object]]) -> int | None:
    """Store one granted box as a locked chest in the first free key. Returns its key."""
    if int(box_id) not in catalog:
        return None
    key = free_slot_key(slots)
    if key is None:
        return None
    slots[key] = {"id": int(box_id), "can_open": 0, "ready": 0}
    return key


def start_countdown(slots: dict[int, dict[str, int]], box_id: int, key: int,
                    now: int, catalog: dict[int, dict[str, object]]) -> bool:
    """Start the open timer on a locked slot that holds this box."""
    slot = slots.get(int(key))
    if slot is None or slot["id"] != int(box_id) or slot["can_open"] != 0:
        return False
    box = catalog.get(int(box_id))
    if box is None:
        return False
    slot["can_open"] = int(now) + int(box.get("delay", 0) or 0)
    return True


def remaining_seconds(slot: dict[str, int], now: int) -> int:
    return max(0, slot["can_open"] - int(now))


def purchase_cost(remaining: int) -> int:
    """Diamonds to open a slot early. Same rule as the client getPrice: under 600 s is free."""
    remaining = int(remaining)
    if remaining < FREE_OPEN_SECONDS:
        return 0
    return math.ceil(remaining / PURCHASE_TIME_SECONDS) * PURCHASE_COST_PER_UNIT


def plan_open(slots: dict[int, dict[str, int]], box_id: int, key: int,
              free: bool, now: int) -> tuple[str, int]:
    """Check an open request. Returns (OPEN_* result, diamond cost)."""
    slot = slots.get(int(key))
    if slot is None or slot["id"] != int(box_id) or slot["can_open"] == 0:
        return OPEN_INVALID, 0
    remaining = remaining_seconds(slot, now)
    if remaining == 0:
        return OPEN_OK, 0
    if free:
        return OPEN_NOT_READY, 0
    return OPEN_OK, purchase_cost(remaining)


# Client getChanceLevel(): RaceScore thresholds for the quantity rank (NumRank1..NumRank7).
CHANCE_RANK_STEPS = (5, 10, 15, 20, 25, 30)
MAX_POOL_DEPTH = 4  # Chests nest loot pools two levels deep in the client tables.


def chance_rank(score: int) -> int:
    for rank, limit in enumerate(CHANCE_RANK_STEPS, start=1):
        if int(score) <= limit:
            return rank
    return len(CHANCE_RANK_STEPS) + 1


def _weighted_pick(rows: list[dict[str, object]], pick: Callable[[int], int]) -> dict[str, object]:
    total = sum(int(row["pvalue"]) for row in rows)
    roll = pick(total)
    for row in rows:
        if roll < int(row["pvalue"]):
            return row
        roll -= int(row["pvalue"])
    return rows[-1]


def roll_box(box_id: int, catalog: dict[int, dict[str, object]], score: int = 1,
             pick: Callable[[int], int] = secrets.randbelow, depth: int = 0) -> list[tuple[int, int]]:
    """Open a chest: one weighted row per RandomIndex group, rows gated by Level <= RaceScore.

    A row whose reward is itself a chest opens that chest (a loot pool) the same way. A leaf
    reward pays the NumRank quantity for the player's championship rank. Returns (item, quantity).
    """
    box = catalog.get(int(box_id))
    if box is None or depth > MAX_POOL_DEPTH:
        return []
    rank = chance_rank(score)
    groups: dict[int, list[dict[str, object]]] = {}
    for row in box.get("rows", []):
        if int(row["item"]) <= 0 or int(row["pvalue"]) <= 0 or int(row.get("level", 0)) > int(score):
            continue
        groups.setdefault(int(row["random_index"]), []).append(row)
    rewards: list[tuple[int, int]] = []
    for index in sorted(groups):
        row = _weighted_pick(groups[index], pick)
        item = int(row["item"])
        if item in catalog:
            rewards.extend(roll_box(item, catalog, score, pick, depth + 1))
            continue
        ranks = row.get("ranks") or []
        quantity = int(ranks[rank - 1]) if rank - 1 < len(ranks) and int(ranks[rank - 1]) > 0 else int(row["num"])
        if quantity > 0:
            rewards.append((item, quantity))
    return rewards


def consume_slot(slots: dict[int, dict[str, int]], key: int) -> None:
    slots.pop(int(key), None)


def migrate_inventory_boxes(inventory: dict, slots: dict[int, dict[str, int]],
                            catalog: dict[int, dict[str, object]]) -> bool:
    """Move chests that were credited to the inventory into free save slots so they can be opened.

    Returns True when anything moved. Chests that do not fit the storage stay in the inventory.
    """
    changed = False
    for raw_key, raw_count in list(inventory.items()):
        item_id = int(raw_key)
        count = int(raw_count or 0)
        if item_id not in catalog or count <= 0:
            continue
        while count > 0 and place_box(slots, item_id, catalog) is not None:
            count -= 1
            changed = True
        inventory[raw_key] = count
    return changed
