"""Shared local friend state for the HTTP FriendService routes.

State lives in data/friends.json and is read and written by server.py. Each player has a
friend list and a list of pending requests received. Both lists are capped, so the file
size is bounded. Writes are atomic (temp file + os.replace) under a process lock.

Friendship is mutual: accepting a request adds both sides; deleting removes both sides.
Error codes follow the client's pbs.ErrCode values (FriendCapFull 4002, FriendNotExists 4003,
AlreadyInFriends 4004, AlreadyInApply 4001, ApplyCapFull 4006).
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

FRIEND_STATE_FILE = Path(__file__).resolve().parent / "data" / "friends.json"
MAX_FRIENDS = 50
MAX_APPLIES = 50

CODE_OK = 0
CODE_ALREADY_IN_APPLY = 4001
CODE_FRIEND_CAP_FULL = 4002
CODE_FRIEND_NOT_EXISTS = 4003
CODE_ALREADY_IN_FRIENDS = 4004
CODE_APPLY_CAP_FULL = 4006

_LOCK = threading.Lock()


def _load(path: Path = FRIEND_STATE_FILE) -> dict[str, Any]:
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"players": {}}
    if not isinstance(state, dict) or not isinstance(state.get("players"), dict):
        return {"players": {}}
    return state


def _save(state: dict[str, Any], path: Path = FRIEND_STATE_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, path)


def _entry(state: dict[str, Any], player: str) -> dict[str, list[str]]:
    row = state["players"].setdefault(player, {"friends": [], "applies": []})
    row.setdefault("friends", [])
    row.setdefault("applies", [])
    return row


def snapshot(player: str, path: Path = FRIEND_STATE_FILE) -> dict[str, list[str]]:
    """Friends and pending requests received by the player (copies, safe to return)."""
    row = _load(path)["players"].get(str(player), {})
    return {"friends": list(row.get("friends", [])), "applies": list(row.get("applies", []))}


def apply_request(sender: str, target: str, target_exists: bool,
                  path: Path = FRIEND_STATE_FILE) -> int:
    sender, target = str(sender), str(target)
    if not target_exists or sender == target:
        return CODE_FRIEND_NOT_EXISTS
    with _LOCK:
        state = _load(path)
        mine = _entry(state, sender)
        theirs = _entry(state, target)
        if target in mine["friends"]:
            return CODE_ALREADY_IN_FRIENDS
        if sender in theirs["applies"]:
            return CODE_ALREADY_IN_APPLY
        if len(theirs["applies"]) >= MAX_APPLIES:
            return CODE_APPLY_CAP_FULL
        if len(mine["friends"]) >= MAX_FRIENDS or len(theirs["friends"]) >= MAX_FRIENDS:
            return CODE_FRIEND_CAP_FULL
        theirs["applies"].append(sender)
        _save(state, path)
    return CODE_OK


def answer_request(me: str, requester: str, accept: bool, path: Path = FRIEND_STATE_FILE) -> int:
    me, requester = str(me), str(requester)
    with _LOCK:
        state = _load(path)
        mine = _entry(state, me)
        if requester not in mine["applies"]:
            return CODE_FRIEND_NOT_EXISTS
        mine["applies"].remove(requester)
        if accept:
            theirs = _entry(state, requester)
            if len(mine["friends"]) >= MAX_FRIENDS or len(theirs["friends"]) >= MAX_FRIENDS:
                _save(state, path)
                return CODE_FRIEND_CAP_FULL
            if requester not in mine["friends"]:
                mine["friends"].append(requester)
            if me not in theirs["friends"]:
                theirs["friends"].append(me)
            # A request in the opposite direction is settled by becoming friends.
            if me in theirs["applies"]:
                theirs["applies"].remove(me)
        _save(state, path)
    return CODE_OK


def delete_friend(me: str, other: str, path: Path = FRIEND_STATE_FILE) -> int:
    me, other = str(me), str(other)
    with _LOCK:
        state = _load(path)
        mine = _entry(state, me)
        if other not in mine["friends"]:
            return CODE_FRIEND_NOT_EXISTS
        mine["friends"].remove(other)
        theirs = _entry(state, other)
        if me in theirs["friends"]:
            theirs["friends"].remove(me)
        _save(state, path)
    return CODE_OK
