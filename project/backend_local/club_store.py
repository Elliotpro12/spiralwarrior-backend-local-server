"""Shared local club state for the HTTP (ClubService) and WebSocket (club chat) servers.

Both server processes read and write data/clubs.json. Writes are atomic (temp file +
os.replace), and a process lock covers writes inside one process. Two processes creating
clubs at the same instant could still race; this is acceptable for a single-tester backend.

Client contract (observed in the recovered client):
- Creating a club: ECS_CreateClub (195) -> ESC_CreateClub (196) with SC_CreateClub{code, id};
  code 200 means success (checkDHServiseCode), 13003 AlreadyInClub, 13028 NameDuplicate.
- Loading the own club: HTTP ClubService.GetClub with id 0 -> {code 0, error "", data {club}}.
  club null means "no club" (ClubMgrNull). A named club that is missing uses code 13001.
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any

CLUB_STATE_FILE = Path(__file__).resolve().parent / "data" / "clubs.json"
CLUB_ID_START = 1000
MAX_NAME_CHARS = 20
MAX_DESC_CHARS = 200

CODE_OK = 200
CODE_INVALID_TEXT = 406
CODE_NOT_FOUND_CLUB = 13001
CODE_ALREADY_IN_CLUB = 13003
CODE_NAME_DUPLICATE = 13028

_LOCK = threading.Lock()


def _empty_state() -> dict[str, Any]:
    return {"next_id": CLUB_ID_START, "clubs": {}}


def load_state(path: Path = CLUB_STATE_FILE) -> dict[str, Any]:
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _empty_state()
    if not isinstance(state, dict) or not isinstance(state.get("clubs"), dict):
        return _empty_state()
    state.setdefault("next_id", CLUB_ID_START)
    return state


def _save_state(state: dict[str, Any], path: Path = CLUB_STATE_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, path)


def club_for_user(user_id: str | int, path: Path = CLUB_STATE_FILE) -> dict[str, Any] | None:
    uid = str(user_id)
    for club in load_state(path)["clubs"].values():
        if uid in club.get("members", []):
            return club
    return None


def get_club(club_id: int | str, path: Path = CLUB_STATE_FILE) -> dict[str, Any] | None:
    return load_state(path)["clubs"].get(str(int(club_id)))


def member_ids(club_id: int | str, path: Path = CLUB_STATE_FILE) -> set[str]:
    club = get_club(club_id, path)
    return set(club.get("members", [])) if club else set()


def create_club(user_id: str | int, name: str, desc: str, club_type: int,
                meta: dict[str, int], path: Path = CLUB_STATE_FILE) -> tuple[int, dict[str, Any] | None]:
    """Create a club led by user_id. Returns (client code, club or None)."""
    name = name.strip()
    if not name or len(name) > MAX_NAME_CHARS or len(desc) > MAX_DESC_CHARS:
        return CODE_INVALID_TEXT, None
    uid = str(user_id)
    with _LOCK:
        state = load_state(path)
        for club in state["clubs"].values():
            if uid in club.get("members", []):
                return CODE_ALREADY_IN_CLUB, None
            if club.get("name", "").casefold() == name.casefold():
                return CODE_NAME_DUPLICATE, None
        club_id = int(state["next_id"])
        state["next_id"] = club_id + 1
        club = {
            "id": club_id,
            "name": name,
            "desc": desc,
            "type": int(club_type),
            "time": int(time.time()),
            "leader": uid,
            "meta": {
                "MaxMemNum": int(meta.get("MaxMemNum", 30)),
                "minLv": int(meta.get("minLv", 1)),
                "loc": int(meta.get("loc", 0)),
                "badge": int(meta.get("badge", 0)),
            },
            "members": [uid],
        }
        state["clubs"][str(club_id)] = club
        _save_state(state, path)
    return CODE_OK, club


CLUB_POST_MEMBER = 0  # pbs.ClubPost.Member
CLUB_POST_PRESIDENT = 3  # pbs.ClubPost.President


def club_client_view(club: dict[str, Any] | None) -> dict[str, Any] | None:
    """Shape of the club object that Club.create reads from GetClub.

    The client requires memberList and eventList arrays (Club.create calls .length and .slice on
    them). userid and owner must be numbers because isOwner and isPresidentType compare them with
    SyncDataManager.getID(), which is numeric. Scores and medals are local zeros.
    """
    if club is None:
        return None
    leader = int(club["leader"])
    members = [
        {
            "userid": int(uid),
            "post": CLUB_POST_PRESIDENT if int(uid) == leader else CLUB_POST_MEMBER,
            "time": int(club["time"]),
            "actives": [],
            "score": 0,
            "isOnline": False,
        }
        for uid in club.get("members", [])
    ]
    return {
        "id": club["id"],
        "name": club["name"],
        "desc": club["desc"],
        "time": club["time"],
        "type": club["type"],
        "owner": leader,
        "totalScore": 0,
        "historyScore": 0,
        "curScore": 0,
        "weekScore": 0,
        "totalMedal": 0,
        "roundMedal": 0,
        "meta": dict(club["meta"]),
        "memberList": members,
        "applyList": [],
        "eventList": [],
    }
