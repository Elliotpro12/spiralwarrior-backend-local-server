"""Static shop goods for the Merchant tabs (AllStaticShopProto, message 3).

The client reads `_AllStaticShop.StaticShop[goodType].ItemList` (getShopItems). The official
server sends it; this local backend builds it from data/ShopItem.json, a table decoded from the
game's own NewAssets.apk (client data, kept local and out of Git).

Mapping used (inferred, to confirm in game):
- StaticShop key = ShopItem.pageIdx, because the client's Sync_GoodType ids line up with the
  pages that have a clear match: page 2 = Gold (coins bought with diamonds), 100 = LuckyDraw,
  101 = BattlePassLevel.
- Daily page 999 (DailyPlus) is served by the daily shop sync, so it is not sent here.
"""

from __future__ import annotations

import functools
import json
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent / "data" / "ShopItem.json"
STATIC_PAGES = frozenset({1, 2, 3, 4, 5, 6, 7, 100, 101})
STATIC_SHOP_TYPES = frozenset({0, 2})  # ShopItem_ShopType: Daily, LimitedShop


def _varint(value: int) -> bytes:
    if value < 0:
        value &= (1 << 64) - 1
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def _int(field: int, value: int) -> bytes:
    return _varint(field << 3) + _varint(int(value))


def _bytes(field: int, payload: bytes) -> bytes:
    return _varint((field << 3) | 2) + _varint(len(payload)) + payload


def _container(idx: int, val: bytes) -> bytes:
    return _int(1, idx) + _bytes(2, val)


def _int_container(idx: int, val: int) -> bytes:
    return _int(1, idx) + _int(2, val)


def encode_shop_item(item: dict) -> bytes:
    """NetShopItemProto. Field numbers come from the client's decoder (project.js ~139000)."""
    out = bytearray()
    out += _int(1, item["Id"])                              # GoodsID
    out += _int(2, item.get("descriptionID", 0))             # DescriptionID
    for reward in item.get("ItemList", []):
        out += _bytes(3, _int_container(int(reward["ID"]), int(reward["Num"])))  # RewardList
    out += _int(4, item.get("limitTimes", 0))                # LimitTimes
    out += _int(5, item.get("diamond", 0))                   # Diamond
    out += _int(6, item.get("gold", 0))                      # Gold
    out += _int(7, item.get("limitLevel", 0))                # LimitLevel
    out += _int(8, item.get("TimeSlider", 0))                # TimeSlider
    for index, value in enumerate(item.get("Discount") or []):
        out += _bytes(9, _int_container(index, int(value)))  # DisCount
    out += _int(10, item.get("LimitType", 0))                # LimitType
    out += _int(11, item.get("pageIdx", 0))                  # Page
    worth = item.get("Worth")
    if worth:                                                 # other currency price (Time debris etc.)
        out += _int(12, worth["ID"])                          # CurrencyId
        out += _int(13, worth["Num"])                         # CurrencyNum
    return bytes(out)


def build_all_static_shop(items: list[dict]) -> bytes:
    """AllStaticShopProto: repeated ContainerIntNetStaticShopProto (field 1)."""
    by_page: dict[int, list[dict]] = {}
    for item in items:
        if int(item.get("shopType", -1)) not in STATIC_SHOP_TYPES:
            continue
        page = int(item.get("pageIdx", 0))
        if page in STATIC_PAGES:
            by_page.setdefault(page, []).append(item)
    out = bytearray()
    for page in sorted(by_page):
        shop = bytearray()
        shop += _int(1, 0)  # NextUpdateTime
        for item in by_page[page]:
            shop += _bytes(2, _container(int(item["Id"]), encode_shop_item(item)))  # ItemList
        out += _bytes(1, _container(page, bytes(shop)))
    return bytes(out)


DAILY_PAGES = (1, 2, 3, 4, 5, 6)  # Sync_DailyShopType: Normal, Rogue, TimePlay, SecretArea (Adventure: Time debris), LuckyCard, Club
DAILY_SLOTS_PER_PAGE = 6  # the Merchant grid has six positions


RARITY_PATH = DATA_PATH.with_name("item_rarity.json")  # item id -> rarity, from the client Item table
ASCENDED_RARITY = 5  # Ascended parts: rarity 5 in the client Item table
MERCHANT_PAGE = 1  # Sync_DailyShopType.Normal: the Merchant tab with the random refresh
MERCHANT_REFRESH_DIAMOND = 200  # UpdateDailyShopCostDiamond (client constant)


@functools.lru_cache(maxsize=1)
def item_rarity() -> dict[int, int]:
    try:
        raw = json.loads(RARITY_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {int(key): int(value) for key, value in raw.items()}


def merchant_pool(items: list[dict]) -> list[dict]:
    """Priced daily rows of the Merchant page: the pool the random roll draws from."""
    return [x for x in items
            if int(x.get("shopType", -1)) == 0 and int(x.get("pageIdx", -1)) == MERCHANT_PAGE
            and (int(x.get("diamond", 0)) > 0 or int(x.get("gold", 0)) > 0)]


def roll_merchant_picks(items: list[dict], rng, level: int | None = None) -> list[int]:
    """Six Merchant row ids. Slots 1-5 draw from all parts except Ascended. The last slot has a
    1% chance of an Ascended part (client text: 'Including all parts, small chance (1%)').
    Only goods whose limitLevel is at or below `level` are offered."""
    rarity = item_rarity()
    pool = sorted(merchant_pool(items), key=lambda x: int(x["Id"]))
    if level is not None:  # goods above the player's level cannot be bought (SC_ShopOpr 5)
        pool = [r for r in pool if int(r.get("limitLevel", 0) or 0) <= int(level)]

    def part_of(row: dict) -> int:
        return int(row["ItemList"][0]["ID"]) if row.get("ItemList") else 0

    ascended = [r for r in pool if rarity.get(part_of(r)) == ASCENDED_RARITY]
    normal = [r for r in pool if rarity.get(part_of(r)) != ASCENDED_RARITY]
    picks: list[int] = []
    used_parts: set[int] = set()
    for _ in range(DAILY_SLOTS_PER_PAGE - 1):
        choices = [r for r in normal if part_of(r) not in used_parts]
        if not choices:
            break
        row = rng.choice(choices)
        picks.append(int(row["Id"]))
        used_parts.add(part_of(row))
    last_pool = ascended if (ascended and rng.random() < 0.01) else normal
    choices = [r for r in last_pool if part_of(r) not in used_parts] or last_pool
    if choices:
        picks.append(int(rng.choice(choices)["Id"]))
    return picks


def build_daily_shop(next_update_time: int, items: list[dict], picks: dict | None = None) -> bytes:
    """NetDailyShopProto: NextUpdateTime (1) and ItemList (2, container idx -> NetShopItemProto).

    The client's getDailyItemData() keeps entries whose Page equals the tab's Sync_DailyShopType.
    Priced means diamond, gold, TimeSlider (Adventure) or another currency (Worth).
    Each page gets its first DAILY_SLOTS_PER_PAGE priced daily rows; slot keys are unique.
    """
    out = bytearray(_int(1, int(next_update_time)))
    key = 1
    by_id = {int(x["Id"]): x for x in items}
    for page in DAILY_PAGES:
        if picks and str(page) in picks:
            rows = [by_id[int(i)] for i in picks[str(page)] if int(i) in by_id]
        else:
            rows = [x for x in items
                    if int(x.get("shopType", -1)) == 0 and int(x.get("pageIdx", -1)) == page
                    and (int(x.get("diamond", 0)) > 0 or int(x.get("gold", 0)) > 0
                         or int(x.get("TimeSlider", 0)) > 0 or x.get("Worth"))]
            rows.sort(key=lambda x: int(x["Id"]))
            rows = rows[:DAILY_SLOTS_PER_PAGE]
        for row in rows:
            out += _bytes(2, _container(key, encode_shop_item(row)))
            key += 1
    return bytes(out)


@functools.lru_cache(maxsize=1)
def cached_items() -> tuple[dict, ...]:
    return tuple(load_items())


def load_items(path: Path = DATA_PATH) -> list[dict]:
    """Decoded ShopItem rows, or an empty list when the local table is missing."""
    try:
        table = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return list(table.get("Items", []))


# Currency item ids (client Item table; names confirmed in TextData-English and the Item table).
CURRENCY_GOLD = 1227894833
CURRENCY_DIAMOND = 1227894834
CURRENCY_TIME_DEBRIS = 1194340400  # Adventure Shop (ShopItem.TimeSlider price)

# ShopItem.LimitType: 0 none, 1 day, 2 week, 3 month, 4 year, 5 forever.
LIMIT_NONE, LIMIT_DAY, LIMIT_WEEK = 0, 1, 2

# Shop return codes (client E_ShopOprRet).
RET_UNKNOWN, RET_INVALID_GOODS, RET_INVALID_MONEY = 0, 1, 2
RET_MONEY_LIMIT, RET_TIMES_LIMIT, RET_LEVEL_LIMIT, RET_OK = 3, 4, 5, 6


def item_by_id() -> dict[int, dict]:
    return {int(row["Id"]): row for row in cached_items()}


def price_lines(row: dict, goods_num: int) -> list[tuple[int, int]]:
    """(currency item id, amount) for goods_num units. Discount[0] is the percent taken off."""
    discount = int((row.get("Discount") or [0])[0] or 0)
    discount = min(max(discount, 0), 100)

    def net(value: int) -> int:
        return int(value) * (100 - discount) // 100 * int(goods_num)

    lines: list[tuple[int, int]] = []
    if int(row.get("diamond", 0)) > 0:
        lines.append((CURRENCY_DIAMOND, net(row["diamond"])))
    if int(row.get("gold", 0)) > 0:
        lines.append((CURRENCY_GOLD, net(row["gold"])))
    if int(row.get("TimeSlider", 0)) > 0:
        lines.append((CURRENCY_TIME_DEBRIS, net(row["TimeSlider"])))
    worth = row.get("Worth")
    if worth:
        lines.append((int(worth["ID"]), net(worth["Num"])))
    return lines


def reward_lines(row: dict, goods_num: int) -> list[tuple[int, int]]:
    return [(int(r["ID"]), int(r["Num"]) * int(goods_num)) for r in row.get("ItemList", [])]


def limit_bucket(limit_type: int, unix_now: int) -> str | None:
    """Key for the purchase cap, or None when the goods have no cap.

    Day and week follow the game's UTC+8 reset (task_periods). Month, year and forever share one
    bucket: the cap is then lifetime, which is only an approximation for month and year.
    """
    limit_type = int(limit_type)
    if limit_type == LIMIT_NONE:
        return None
    import task_periods
    if limit_type == LIMIT_DAY:
        return f"day:{task_periods.period_index('daily', unix_now)}"
    if limit_type == LIMIT_WEEK:
        return f"week:{task_periods.period_index('weekly', unix_now)}"
    return "lifetime"


def row_level_ok(row_id: int, level: int) -> bool:
    """True when the ShopItem row exists and its limitLevel is at or below the player's level."""
    row = item_by_id().get(int(row_id))
    return row is not None and int(row.get("limitLevel", 0) or 0) <= int(level)

