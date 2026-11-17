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


def build_daily_shop(next_update_time: int, items: list[dict]) -> bytes:
    """NetDailyShopProto: NextUpdateTime (1) and ItemList (2, container idx -> NetShopItemProto).

    The client's getDailyItemData() keeps entries whose Page equals the tab's Sync_DailyShopType.
    Priced means diamond, gold, TimeSlider (Adventure) or another currency (Worth).
    Each page gets its first DAILY_SLOTS_PER_PAGE priced daily rows; slot keys are unique.
    """
    out = bytearray(_int(1, int(next_update_time)))
    key = 1
    for page in DAILY_PAGES:
        rows = [x for x in items
                if int(x.get("shopType", -1)) == 0 and int(x.get("pageIdx", -1)) == page
                and (int(x.get("diamond", 0)) > 0 or int(x.get("gold", 0)) > 0
                     or int(x.get("TimeSlider", 0)) > 0 or x.get("Worth"))]
        rows.sort(key=lambda x: int(x["Id"]))
        for row in rows[:DAILY_SLOTS_PER_PAGE]:
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
