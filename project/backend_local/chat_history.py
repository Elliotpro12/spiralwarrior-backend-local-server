"""Bounded server-side history for world and club chat.

Each channel keeps only its last HISTORY_LIMIT messages, in a deque, so memory is fixed per
channel. Writes are not done per message: a message marks the store dirty, and a background
thread flushes it at most once per FLUSH_SECONDS, with an atomic temp-file replace. Reads
return copies, so callers cannot change the stored deque.
"""

from __future__ import annotations

import json
import os
import threading
import time
from collections import deque
from pathlib import Path

HISTORY_LIMIT = 50
FLUSH_SECONDS = 5.0
HISTORY_FILE = Path(__file__).resolve().parent / "data" / "chat_history.json"


class ChatHistory:
    def __init__(self, path: Path = HISTORY_FILE) -> None:
        self.path = path
        self._lock = threading.Lock()
        self._channels: dict[str, deque[str]] = {}
        self._dirty = False
        self._load()
        threading.Thread(target=self._flush_loop, name="chat-history-flush", daemon=True).start()

    def _load(self) -> None:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if not isinstance(raw, dict):
            return
        for key, items in raw.items():
            if isinstance(key, str) and isinstance(items, list):
                self._channels[key] = deque((str(i) for i in items[-HISTORY_LIMIT:]), maxlen=HISTORY_LIMIT)

    def add(self, key: str, talk_data: str) -> None:
        with self._lock:
            channel = self._channels.get(key)
            if channel is None:
                channel = self._channels[key] = deque(maxlen=HISTORY_LIMIT)
            channel.append(talk_data)
            self._dirty = True

    def recent(self, key: str) -> list[str]:
        with self._lock:
            return list(self._channels.get(key, ()))

    def flush(self) -> bool:
        with self._lock:
            if not self._dirty:
                return False
            snapshot = {key: list(items) for key, items in self._channels.items()}
            self._dirty = False
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temp = self.path.with_suffix(".tmp")
            temp.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")
            os.replace(temp, self.path)
        except OSError:
            with self._lock:
                self._dirty = True  # nothing was published, so retry on the next pass
            raise
        return True

    def _flush_loop(self) -> None:
        while True:
            time.sleep(FLUSH_SECONDS)
            try:
                self.flush()
            except OSError:
                pass  # keep the dirty flag; the next pass retries


HISTORY = ChatHistory()
