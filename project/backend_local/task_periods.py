"""Daily and weekly mission periods: when their progress and rewards start over.

Client facts (observed in the client code):
- DBTaskListProto.EndSymbol is the end of the period of a task container (game seconds).
- Game seconds count from 2018-01-01 00:00 UTC (client getDateTime2018, 1514736000 s).

Inferred, not verified in game:
- the reset hour is local midnight (daily) and Monday midnight (weekly);
- the local offset is RESET_UTC_OFFSET_HOURS (Puerto Rico, UTC-4). Change it to match the device.
- weekly resets apply to the season weekly tasks (TaskData type 10) and the weekly static type (8).
"""

from __future__ import annotations

from typing import Callable

DAY_SECONDS = 86400
GAME_EPOCH_UNIX = 1514736000
RESET_UTC_OFFSET_HOURS = -4

# TaskData_TaskType values that restart on a period boundary.
PERIODIC_KIND = {
    3: "daily",    # DailyStaticTask
    0: "daily",    # DailyRandomTask
    8: "weekly",   # WeeklyStaticTask
    10: "weekly",  # SeasonWeeklyTask
}


def period_index(kind: str, unix_now: int, offset_hours: int = RESET_UTC_OFFSET_HOURS) -> int:
    """Index of the current period in local time. 1970-01-01 was a Thursday, so weeks start Monday."""
    days = (int(unix_now) + int(offset_hours) * 3600) // DAY_SECONDS
    if kind == "weekly":
        return (days + 3) // 7
    return days


def next_reset_game_seconds(task_type: int, game_now: int,
                            offset_hours: int = RESET_UTC_OFFSET_HOURS) -> int:
    """Game-second time of the next reset for a periodic task type, or 0 when it has none."""
    kind = PERIODIC_KIND.get(int(task_type))
    if kind is None:
        return 0
    unix_now = int(game_now) + GAME_EPOCH_UNIX
    index = period_index(kind, unix_now, offset_hours)
    next_day = index + 1 if kind == "daily" else (index + 1) * 7 - 3
    next_unix = next_day * DAY_SECONDS - int(offset_hours) * 3600
    return next_unix - GAME_EPOCH_UNIX


def reset_periodic_tasks(task_catalog: dict[int, dict[str, object]],
                         db_task_state: dict[str, dict[str, int]],
                         progression_counters: dict[str, object],
                         task_periods: dict[str, int],
                         game_now: int,
                         counter_key: Callable[[dict[str, object]], str],
                         offset_hours: int = RESET_UTC_OFFSET_HOURS) -> bool:
    """Start over the daily and weekly tasks whose period changed. Mutates the dicts.

    A type without a stored period is only stamped, so progress earned before this rule
    is not lost. Counters shared with non-periodic tasks are kept. Returns True on any change.
    """
    unix_now = int(game_now) + GAME_EPOCH_UNIX
    shared_keys = {
        counter_key(task) for task in task_catalog.values()
        if int(task.get("taskType", -1)) not in PERIODIC_KIND
    }
    changed = False
    for task_type, kind in sorted(PERIODIC_KIND.items()):
        index = period_index(kind, unix_now, offset_hours)
        marker = str(task_type)
        stored = task_periods.get(marker)
        if stored == index:
            continue
        if stored is not None:
            for task_id, task in task_catalog.items():
                if int(task.get("taskType", -1)) != task_type:
                    continue
                db_task_state.pop(str(int(task_id)), None)
                key = counter_key(task)
                if key not in shared_keys:
                    progression_counters.pop(key, None)
        task_periods[marker] = index
        changed = True
    return changed


def normalize_task_periods(raw: object) -> dict[str, int]:
    """Profile state -> {task type: period index} for the periodic task types only."""
    if not isinstance(raw, dict):
        return {}
    periods: dict[str, int] = {}
    for key, value in raw.items():
        if str(key).lstrip("-").isdigit() and int(key) in PERIODIC_KIND:
            periods[str(int(key))] = int(value)
    return periods
