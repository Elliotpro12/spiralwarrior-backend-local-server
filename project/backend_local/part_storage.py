"""Storage rules for part items (the client's LocationTop/Middle/Bottom items).

Observed in the shipped 1.1.0.96 bundle:

* A part counts as owned only when its ``BaseInfo.TopPartList`` /
  ``MidPartList`` / ``BotPartList`` entry has ``Level >= 1``;
  ``SyncDataManager.getSelfPart`` otherwise returns a "default" part and every
  list (parts bag, upgrade screen, collection) marks it as not acquired.
* The item counter of an owned part is ``Piece + 1``
  (``SyncDataManager.getItemNumByTable``), and ``ItemUpgrade.LevelN.piece``
  consumes those pieces when the part is upgraded.

So the profile stores ``part_levels`` (Level) and ``part_fragments`` (Piece),
and receiving ``N`` copies of part ``P`` means:

    not owned -> Level = ItemUpgrade.initLevel, Piece += N - 1
    owned     -> Piece += N

``initLevel`` comes from the client's ``ItemUpgrade`` table (the row the part's
``Item.upgradekey`` points at) and is the rarity-based starting level the
client itself enforces with ``Math.max(Level, initLevel)`` in every upgrade
view: 1 common, 3 rare, 5 epic, 7 legendary, 9 ascended. Storing anything lower
leaves the part card and its stats at the wrong level, and the first upgrade
would jump several levels because the upgrade screen clamps the current level.

Older local profiles stored the part item ids in ``inventory_items`` (a store
the client never reads for parts) and, later, the copy counts in
``part_fragments`` without a level. ``migrate`` rewrites both forms in place;
the conversion is lossless (the displayed count stays ``Piece + 1``) and
idempotent. It also raises any owned part stored below its ``initLevel``.
"""

from __future__ import annotations

import json
from pathlib import Path

CATALOG_PATH = Path(__file__).resolve().parent / "data" / "part_item_catalog.json"
UPGRADE_CATALOG_PATH = Path(__file__).resolve().parent / "data" / "item_upgrade_catalog.json"

_locations: dict[int, int] | None = None
_init_levels: dict[int, int] | None = None


def load_locations() -> dict[int, int]:
    """Client-confirmed part id -> slot (0 Top, 1 Middle, 2 Bottom)."""
    global _locations
    if _locations is None:
        try:
            catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            catalog = {}
        locations: dict[int, int] = {}
        for location, item_ids in (catalog.get("items_by_location", {}) or {}).items():
            try:
                slot = int(location)
            except (TypeError, ValueError):
                continue
            if slot not in (0, 1, 2) or not isinstance(item_ids, list):
                continue
            for item_id in item_ids:
                try:
                    parsed_id = int(item_id)
                except (TypeError, ValueError):
                    continue
                if parsed_id > 0:
                    locations[parsed_id] = slot
        _locations = locations
    return dict(_locations)


def load_init_levels() -> dict[int, int]:
    """Client ItemUpgrade.initLevel per part id (1/3/5/7/9 by rarity).

    The catalogue is extracted from the shipped client
    (``TableManager.itemUpgradeManager``); without it every part falls back to
    level 1, which is the old behaviour.
    """
    global _init_levels
    if _init_levels is None:
        levels: dict[int, int] = {}
        try:
            catalog = json.loads(UPGRADE_CATALOG_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            catalog = {}
        upgrades = {}
        for row in catalog.get("upgrades", []) or []:
            if not isinstance(row, dict):
                continue
            try:
                key = int(row.get("UpgradeKey", 0))
                init_level = max(1, int(row.get("initLevel", 1)))
            except (TypeError, ValueError):
                continue
            if key > 0:
                upgrades[key] = init_level
        for row in catalog.get("parts", []) or []:
            if not isinstance(row, dict):
                continue
            try:
                part_id = int(row.get("partId", 0))
                upgrade_key = int(row.get("upgradeKey", 0))
            except (TypeError, ValueError):
                continue
            if part_id > 0 and upgrade_key in upgrades:
                levels[part_id] = upgrades[upgrade_key]
        _init_levels = levels
    return dict(_init_levels)


def initial_level(part_id: int, init_levels: dict[int, int] | None = None) -> int:
    """Starting level for a newly owned part (1 when the client table is absent)."""
    levels = load_init_levels() if init_levels is None else init_levels
    try:
        return max(1, int(levels.get(int(part_id), 1)))
    except (TypeError, ValueError):
        return 1


def normalize_counts(raw: object) -> dict[int, int]:
    """Coerce a profile mapping (string or int keys) to positive int -> int."""
    result: dict[int, int] = {}
    if not isinstance(raw, dict):
        return result
    for key, value in raw.items():
        try:
            item_id, amount = int(key), int(value)
        except (TypeError, ValueError):
            continue
        if item_id > 0 and amount > 0:
            result[item_id] = amount
    return result


def stringify_counts(counts: dict[int, int]) -> dict[str, int]:
    """Profile JSON form (object keys are strings)."""
    return {str(int(key)): int(value) for key, value in sorted(counts.items())
            if int(value) > 0}


def credit(part_levels: dict[int, int], part_fragments: dict[int, int],
           part_id: int, quantity: int, *, locations: dict[int, int] | None = None,
           init_levels: dict[int, int] | None = None) -> bool:
    """Add ``quantity`` copies of one part. Returns True when it was a part."""
    locations = load_locations() if locations is None else locations
    part_id, quantity = int(part_id), max(0, int(quantity))
    if part_id not in locations:
        return False
    if quantity <= 0:
        return True
    if int(part_levels.get(part_id, 0)) < 1:
        part_levels[part_id] = initial_level(part_id, init_levels)
        quantity -= 1
    if quantity > 0:
        part_fragments[part_id] = int(part_fragments.get(part_id, 0)) + quantity
    return True


def migrate(inventory_items: dict, part_levels: dict, part_fragments: dict,
            *, locations: dict[int, int] | None = None,
            init_levels: dict[int, int] | None = None) -> bool:
    """Rewrite legacy part storage in place. Returns True when anything moved."""
    locations = load_locations() if locations is None else locations
    init_levels = load_init_levels() if init_levels is None else init_levels
    changed = False
    for part_id in [key for key in inventory_items if int(key) in locations]:
        quantity = int(inventory_items.pop(part_id))
        credit(part_levels, part_fragments, int(part_id), quantity,
               locations=locations, init_levels=init_levels)
        changed = True
    for part_id in [key for key in part_fragments if int(key) in locations]:
        if int(part_levels.get(part_id, 0)) < 1:
            part_levels[part_id] = initial_level(part_id, init_levels)
            remaining = max(0, int(part_fragments.get(part_id, 0)) - 1)
            if remaining:
                part_fragments[part_id] = remaining
            else:
                part_fragments.pop(part_id, None)
            changed = True
    for part_id in list(part_levels):
        if int(part_id) not in locations or int(part_levels.get(part_id, 0)) < 1:
            part_levels.pop(part_id, None)
            changed = True
    # Repair profiles written before the initLevel rule: the client clamps
    # those parts to their rarity level in upgrade views, so store that level.
    for part_id, level in list(part_levels.items()):
        required = initial_level(part_id, init_levels)
        if int(level) < required:
            part_levels[int(part_id)] = required
            changed = True
    return changed
