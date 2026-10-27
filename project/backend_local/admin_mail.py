"""Mail delivery, attachment claims, and the notice board used by the admin tools.

Mail format (observed in the client, Mail/pbsData2MailData and getMailStringByType):
- ShowMail (type 3) shows title and body as literal text.
- attachment is a JSON array of {"item": "<item id as string>", "num": <count>}.
- Claiming sends ECS_MarkMailArgs (155) with the mail ids; the server must credit the
  attachments and mark the mail Received (state 2) before answering ESC_MarkMailReply (156).

Each account keeps its own mail file (AccountStore.mail_path), so delivery appends to
those files and claims credit only the mail of the authenticated account.
"""

from __future__ import annotations

import json
import secrets
import time
from pathlib import Path
from typing import Callable

from mail_fixture import MAIL_STATE_NEW, MAIL_STATE_RECEIVED, MAIL_TYPE_SHOW, load_mail_state, save_mail_state

# Client game clock: seconds since 2018-01-01 UTC (same epoch as ws_probe_server.game_time_seconds).
GAME_TIME_EPOCH_SECONDS = 1514736000
MAIL_LIFETIME_SECONDS = 30 * 24 * 3600
MAX_TITLE_CHARS = 60
MAX_BODY_CHARS = 2000
MAX_SENDER_CHARS = 24
MAX_ATTACHMENTS = 10
MAX_ITEM_NUM = 1_000_000_000
MAX_NOTICE_CHARS = 8000


class AdminInputError(ValueError):
    """Invalid admin input; the message is safe to show in the admin page."""


def game_time_seconds(now: float | None = None) -> int:
    return int((time.time() if now is None else now) - GAME_TIME_EPOCH_SECONDS)


def validate_attachments(raw: object) -> list[dict[str, object]]:
    if raw in (None, ""):
        return []
    if not isinstance(raw, list):
        raise AdminInputError("attachments must be a list")
    if len(raw) > MAX_ATTACHMENTS:
        raise AdminInputError(f"at most {MAX_ATTACHMENTS} attachments per mail")
    result = []
    for entry in raw:
        if not isinstance(entry, dict):
            raise AdminInputError("each attachment needs an item id and a count")
        try:
            item = int(str(entry.get("item", "")).strip())
            num = int(entry.get("num", 0))
        except (TypeError, ValueError):
            raise AdminInputError("item and num must be whole numbers") from None
        if item <= 0:
            raise AdminInputError("item id must be positive")
        if not 1 <= num <= MAX_ITEM_NUM:
            raise AdminInputError(f"num must be between 1 and {MAX_ITEM_NUM}")
        result.append({"item": str(item), "num": num})
    return result


def build_mail(title: str, body: str, sender: str, attachments: list[dict[str, object]],
               now: float | None = None) -> dict[str, object]:
    title = (title or "").strip()
    body = (body or "").strip()
    sender = (sender or "").strip() or "Spiral Warrior Team"
    if not title or len(title) > MAX_TITLE_CHARS:
        raise AdminInputError(f"title is required (max {MAX_TITLE_CHARS} characters)")
    if len(body) > MAX_BODY_CHARS:
        raise AdminInputError(f"body is too long (max {MAX_BODY_CHARS} characters)")
    if len(sender) > MAX_SENDER_CHARS:
        raise AdminInputError(f"sender is too long (max {MAX_SENDER_CHARS} characters)")
    stamp = game_time_seconds(now)
    return {
        # Numeric string ids, like the client's own mail ids.
        "id": f"{time.time_ns() // 1000}{secrets.randbelow(900) + 100}",
        "title": title,
        "body": body,
        "from": sender,
        "state": MAIL_STATE_NEW,
        "time": stamp,
        "exp": stamp + MAIL_LIFETIME_SECONDS,
        "type": MAIL_TYPE_SHOW,
        "attachment": json.dumps(attachments, ensure_ascii=False),
        "deleted": False,
    }


def _load_or_empty(path: Path) -> dict[str, object]:
    # A missing file means the account has no mail yet; do not seed the fixture test mail.
    if not path.exists():
        return {"mails": []}
    return load_mail_state(path)


def deliver_mail(paths: list[Path], mail: dict[str, object]) -> int:
    """Append one copy of mail to each account's mail file. Returns the number of copies."""
    for path in paths:
        state = _load_or_empty(path)
        state["mails"].append(dict(mail))
        save_mail_state(state, path)
    return len(paths)


def claim_mail(path: Path, mail_ids: list[str],
               grant: Callable[[int, int], None]) -> list[tuple[int, int]]:
    """Mark the requested attachment mails Received and grant each attachment once.

    The mail file is saved with the Received state before grant() runs, so a repeated
    claim of the same id finds nothing left to grant.
    """
    if not path.exists():
        return []
    state = load_mail_state(path)
    wanted = {str(value) for value in mail_ids}
    granted: list[tuple[int, int]] = []
    changed = False
    for mail in state["mails"]:
        if str(mail.get("id")) not in wanted or mail.get("deleted"):
            continue
        if int(mail.get("state", MAIL_STATE_NEW)) == MAIL_STATE_RECEIVED:
            continue
        try:
            attachments = json.loads(mail.get("attachment") or "[]")
        except json.JSONDecodeError:
            attachments = []
        if not attachments:
            continue
        mail["state"] = MAIL_STATE_RECEIVED
        changed = True
        for entry in attachments:
            item, num = int(entry["item"]), int(entry["num"])
            granted.append((item, num))
    if changed:
        save_mail_state(state, path)
    for item, num in granted:
        grant(item, num)
    return granted


def read_notice(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


NOTICE_HISTORY_LIMIT = 50


def notice_history_path(path: Path) -> Path:
    """History file beside the notice (notices/ is git-ignored except the default notice)."""
    return path.with_name("notice_history.json")


def read_notice_history(path: Path) -> list[dict[str, str]]:
    """Versions that were replaced, newest first: [{"replaced_at": iso time, "text": ...}]."""
    try:
        rows = json.loads(notice_history_path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return []
    if not isinstance(rows, list):
        return []
    return [row for row in reversed(rows) if isinstance(row, dict) and isinstance(row.get("text"), str)]


def write_notice(path: Path, text: str) -> None:
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    if len(text) > MAX_NOTICE_CHARS:
        raise AdminInputError(f"notice is too long (max {MAX_NOTICE_CHARS} characters)")
    if any(ord(ch) < 32 and ch not in "\n\t" for ch in text):
        raise AdminInputError("notice cannot contain control characters")
    path.parent.mkdir(parents=True, exist_ok=True)
    previous = read_notice(path)
    if previous and previous != text:
        history = list(reversed(read_notice_history(path)))  # stored oldest first
        history.append({"replaced_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "text": previous})
        history_file = notice_history_path(path)
        history_temp = history_file.with_name(f"{history_file.name}.tmp")
        history_temp.write_text(json.dumps(history[-NOTICE_HISTORY_LIMIT:], ensure_ascii=False), encoding="utf-8")
        history_temp.replace(history_file)
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


MAIL_HISTORY_LIMIT = 200
MAIL_HISTORY_FILE = Path(__file__).resolve().parent / "data" / "mail_history.json"


def read_mail_history(path: Path = MAIL_HISTORY_FILE) -> list[dict[str, object]]:
    """Sent mails, newest first."""
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return []
    return list(reversed(rows)) if isinstance(rows, list) else []


def record_mail_sent(entry: dict[str, object], path: Path = MAIL_HISTORY_FILE) -> None:
    """Append one sent mail to the history (atomic write, bounded length)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = list(reversed(read_mail_history(path)))  # stored oldest first
    rows.append(entry)
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(rows[-MAIL_HISTORY_LIMIT:], ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)
