"""Season window for the Season missions tab (TaskData type 9, SeasonStaticTask).

Observed in the client (agent2/analysis/jsc/recovered_local/project.js):
- The Season tab reads DBTaskLists[9]. When that container is missing or its EndSymbol is 0,
  refreshTimeLabel shows "This event is over." (TXT_PARTNOTICE_AVTIVITY_OVER) and the tab is closed.
- EndSymbol is a game-second timestamp (getRealTime: 2018-01-01 epoch + seconds).

Unknown: how long a season of missions lasts. The decoded tables have no season dates and the
text only names the Champions League season (3 weeks, TextData 1088). The admin panel sets the
window, so nothing here invents a schedule.

The season id is the start time in Unix seconds. Changing it resets the season task progress
(task_periods.py, PERIODIC_KIND type 9). When no season is open the season id reported is 0.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent / "data"
CONFIG_PATH = DATA_DIR / "season.json"
GAME_EPOCH_UNIX = 1514736000
DAY_SECONDS = 86400
MIN_DAYS = 1
MAX_DAYS = 366
DEFAULT_DAYS = 21  # 3 weeks: the only season length written in the client text (Champions League).
MAX_NAME = 60


class SeasonError(ValueError):
    """Invalid season request from the admin panel."""


def _empty() -> dict[str, Any]:
    return {"season_id": 0, "name": "", "start_unix": 0, "end_unix": 0}


def load() -> dict[str, Any]:
    """Stored season record. Missing or damaged files mean no season."""
    try:
        raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return _empty()
    if not isinstance(raw, dict):
        return _empty()
    try:
        return {
            "season_id": int(raw.get("season_id", 0)),
            "name": str(raw.get("name", ""))[:MAX_NAME],
            "start_unix": int(raw.get("start_unix", 0)),
            "end_unix": int(raw.get("end_unix", 0)),
        }
    except (TypeError, ValueError):
        return _empty()


def _save(record: dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(record, indent=2), encoding="utf-8")
    os.replace(tmp, CONFIG_PATH)


def open_record(unix_now: int) -> dict[str, Any] | None:
    """The stored season when it is open at unix_now, else None."""
    record = load()
    if record["season_id"] and record["start_unix"] <= int(unix_now) < record["end_unix"]:
        return record
    return None


def end_game_seconds(game_now: int) -> int:
    """EndSymbol for the season container at a game-second time, or 0 when no season is open."""
    record = open_record(int(game_now) + GAME_EPOCH_UNIX)
    return record["end_unix"] - GAME_EPOCH_UNIX if record else 0


def season_index(unix_now: int) -> int:
    """Season id open at unix_now, or 0. task_periods uses it to reset season progress."""
    record = open_record(unix_now)
    return record["season_id"] if record else 0


def status(now_unix: int | None = None) -> dict[str, Any]:
    """Admin view: whether a season is open, its window and the time left."""
    now = int(now_unix if now_unix is not None else time.time())
    record = load()
    open_now = open_record(now)
    remaining = max(0, record["end_unix"] - now) if open_now else 0
    return {
        "open": open_now is not None,
        "name": record["name"] if record["season_id"] else "",
        "season_id": record["season_id"] if open_now else 0,
        "start_unix": record["start_unix"] if record["season_id"] else 0,
        "end_unix": record["end_unix"] if record["season_id"] else 0,
        "remaining_seconds": remaining,
        "default_days": DEFAULT_DAYS,
    }


def start(name: object, days: object, now_unix: int | None = None) -> dict[str, Any]:
    """Open a new season for `days` days from now. The previous season, if any, ends now."""
    text = str(name if name is not None else "").strip()
    if not text:
        raise SeasonError("the season needs a name")
    if len(text) > MAX_NAME:
        raise SeasonError(f"the season name is longer than {MAX_NAME} characters")
    try:
        count = int(days)
    except (TypeError, ValueError):
        raise SeasonError("days must be a whole number") from None
    if not MIN_DAYS <= count <= MAX_DAYS:
        raise SeasonError(f"days must be between {MIN_DAYS} and {MAX_DAYS}")
    now = int(now_unix if now_unix is not None else time.time())
    record = {"season_id": now, "name": text, "start_unix": now, "end_unix": now + count * DAY_SECONDS}
    _save(record)
    return record


def stop(now_unix: int | None = None) -> dict[str, Any]:
    """End the open season now. Its progress is reset when the next season starts."""
    now = int(now_unix if now_unix is not None else time.time())
    record = load()
    if record["season_id"] and record["end_unix"] > now:
        record["end_unix"] = now
        _save(record)
    return record
