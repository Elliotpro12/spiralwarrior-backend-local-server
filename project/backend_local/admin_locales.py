"""Language packs for the admin page.

English and Spanish are built into admin/index.html. Languages added from the Settings tab
are stored one file each in admin/locales/<code>.json and shared by everyone who uses this
admin server. The built-in languages cannot be replaced from here.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOCALES_DIR = ROOT / "admin" / "locales"
BUILTIN_LOCALES = {"en": "English", "es": "Español"}
CODE_PATTERN = re.compile(r"[a-z]{2,3}(-[A-Za-z0-9]{2,8})?")
KEY_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9]{0,79}")
MAX_NAME_CHARS = 40
MAX_TEXT_CHARS = 600
MAX_KEYS = 300


class LocaleError(ValueError):
    """Invalid language request; the message is safe to show in the admin page."""


class LocaleNotFound(LocaleError):
    """The requested added language does not exist."""


def validate_code(raw: object) -> str:
    code = str(raw or "").strip()
    if not CODE_PATTERN.fullmatch(code):
        raise LocaleError("language code must be 2-3 lowercase letters, optionally followed by a region such as -BR")
    if code in BUILTIN_LOCALES:
        raise LocaleError(f"{code} is built in and cannot be changed here")
    return code


def validate_name(raw: object) -> str:
    name = str(raw or "").strip()
    if not name or len(name) > MAX_NAME_CHARS or any(ord(ch) < 32 for ch in name):
        raise LocaleError(f"language name is required (max {MAX_NAME_CHARS} characters)")
    return name


def validate_strings(raw: object) -> dict[str, str]:
    """Keep only non-empty translations; empty fields fall back to English in the page."""
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise LocaleError("strings must be an object of text keys")
    if len(raw) > MAX_KEYS:
        raise LocaleError(f"at most {MAX_KEYS} texts per language")
    result: dict[str, str] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or not KEY_PATTERN.fullmatch(key):
            raise LocaleError(f"invalid text key: {str(key)[:40]}")
        if not isinstance(value, str):
            raise LocaleError(f"the text for {key} must be a string")
        value = value.strip()
        if len(value) > MAX_TEXT_CHARS:
            raise LocaleError(f"the text for {key} is too long (max {MAX_TEXT_CHARS} characters)")
        if value:
            result[key] = value
    return result


def _path(code: str) -> Path:
    return LOCALES_DIR / f"{code}.json"


def _write(path: Path, doc: dict[str, object]) -> None:
    LOCALES_DIR.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def read_locale(raw_code: str) -> dict[str, object] | None:
    """Return {code, name, strings} for an added language, or None when it does not exist."""
    try:
        code = validate_code(raw_code)
    except LocaleError:
        return None
    try:
        doc = json.loads(_path(code).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    if not isinstance(doc, dict):
        return None
    strings = doc.get("strings")
    return {
        "code": code,
        "name": str(doc.get("name") or code),
        "strings": strings if isinstance(strings, dict) else {},
    }


def list_locales() -> list[dict[str, object]]:
    rows = []
    if LOCALES_DIR.is_dir():
        for path in sorted(LOCALES_DIR.glob("*.json")):
            doc = read_locale(path.stem)
            if doc is not None:
                rows.append({"code": doc["code"], "name": doc["name"], "custom": True,
                             "translated": len(doc["strings"])})
    return rows


def create_locale(raw_code: object, raw_name: object) -> dict[str, object]:
    code = validate_code(raw_code)
    name = validate_name(raw_name)
    path = _path(code)
    if path.exists():
        raise LocaleError(f"language {code} already exists")
    _write(path, {"code": code, "name": name, "strings": {}})
    return {"code": code, "name": name, "custom": True, "translated": 0}


def save_locale(raw_code: str, raw_name: object, raw_strings: object) -> dict[str, object]:
    code = validate_code(raw_code)
    name = validate_name(raw_name)
    if not _path(code).exists():
        raise LocaleNotFound(f"language {code} does not exist")
    strings = validate_strings(raw_strings)
    _write(_path(code), {"code": code, "name": name, "strings": strings})
    return {"code": code, "name": name, "custom": True, "translated": len(strings)}


def delete_locale(raw_code: str) -> None:
    code = validate_code(raw_code)
    path = _path(code)
    if not path.exists():
        raise LocaleNotFound(f"language {code} does not exist")
    path.unlink()
