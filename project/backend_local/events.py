"""Timed activities the server switches on (Halloween, Thanksgiving, Christmas).

Client contract (observed in the client code, recovered_local project.js ~ ActivityHalloweenData.initData):
- The activity is open when PlayerData.DBTaskLists has a container of type 14 (TaskData_TaskType.LuckyCardTask)
  whose Param (DBTaskListProto field 3) is a LuckyCard row id, and its EndSymbol (field 2) is the end time
  in game seconds.
- The LuckyCard row (data/lucky_card.json, from the client LuckyCard table) gives the kind: 1 Halloween,
  2 Thanksgiving, 3 Christmas.

Config file: data/events.json, written by start_lucky_card() / stop_lucky_card() (admin panel later).
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent / "data"
CONFIG_PATH = DATA_DIR / "events.json"
GAME_EPOCH_UNIX = 1514736000
LUCKY_CARD_TASK_TYPE = 14  # TaskData_TaskType.LuckyCardTask
# LuckyCard row ids of the seasonal activities (client LuckyCard table, ActivityType 1 Halloween,
# 2 Thanksgiving, 3 Christmas). Christmas has several rows, one per season; any of them works.
LUCKY_CARD_KINDS = {
    2020: "Halloween",
    20201126: "Thanksgiving",
    20201223: "Christmas", 20210214: "Christmas", 20210404: "Christmas", 20210511: "Christmas",
    20210706: "Christmas", 20210803: "Christmas", 20211116: "Christmas", 20211221: "Christmas",
}
DEFAULT_DAYS = 14


class EventError(ValueError):
    pass


def _load() -> dict[str, Any]:
    try:
        raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _save(record: dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(record, indent=2), encoding="utf-8")
    os.replace(tmp, CONFIG_PATH)


def active_lucky_card(unix_now: int | None = None) -> dict[str, int] | None:
    """{"lucky_id", "end_game"} while the seasonal activity is open, else None."""
    now = int(time.time()) if unix_now is None else int(unix_now)
    record = _load().get("lucky_card")
    if not isinstance(record, dict):
        return None
    try:
        lucky_id = int(record["lucky_id"])
        start = int(record["start_unix"])
        end = int(record["end_unix"])
    except (KeyError, TypeError, ValueError):
        return None
    if lucky_id not in LUCKY_CARD_KINDS or not start <= now < end:
        return None
    return {"lucky_id": lucky_id, "end_game": end - GAME_EPOCH_UNIX}


def start_lucky_card(lucky_id: int, days: int = DEFAULT_DAYS, unix_now: int | None = None) -> dict[str, Any]:
    if int(lucky_id) not in LUCKY_CARD_KINDS:
        raise EventError(f"lucky_id must be one of {sorted(LUCKY_CARD_KINDS)}")
    if not 1 <= int(days) <= 60:
        raise EventError("days must be between 1 and 60")
    now = int(time.time()) if unix_now is None else int(unix_now)
    record = {"lucky_card": {"lucky_id": int(lucky_id), "kind": LUCKY_CARD_KINDS[int(lucky_id)],
                             "start_unix": now, "end_unix": now + int(days) * 86400}}
    _save(record)
    return record["lucky_card"]


def stop_lucky_card(unix_now: int | None = None) -> None:
    now = int(time.time()) if unix_now is None else int(unix_now)
    record = _load()
    current = record.get("lucky_card")
    if isinstance(current, dict):
        current["end_unix"] = min(int(current.get("end_unix", now)), now)
        _save(record)
