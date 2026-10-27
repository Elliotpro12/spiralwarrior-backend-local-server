"""Optional trace of frames the WebSocket server sends to the client.

Enabled only when SPIRAL_TRACE_OUTGOING=1. When disabled, TracedSocket is not used and
nothing changes at runtime. The wrapper delegates every other socket method, so reads,
close and identity (used as the pusher key) behave as before.
"""

from __future__ import annotations

import os
from typing import Callable

ENABLED = os.environ.get("SPIRAL_TRACE_OUTGOING") == "1"


def _varint_fields(data: bytes, limit: int = 8) -> dict[int, int]:
    """Read scalar varint fields (wire type 0) from a protobuf body, best effort."""
    out: dict[int, int] = {}
    pos = 0
    while pos < len(data) and len(out) < limit:
        tag = 0
        shift = 0
        while True:
            if pos >= len(data):
                return out
            byte = data[pos]
            pos += 1
            tag |= (byte & 0x7F) << shift
            shift += 7
            if byte < 0x80:
                break
        number, wire = tag >> 3, tag & 7
        if wire == 0:
            value = 0
            shift = 0
            while pos < len(data):
                byte = data[pos]
                pos += 1
                value |= (byte & 0x7F) << shift
                shift += 7
                if byte < 0x80:
                    break
            out[number] = value
        elif wire == 2:
            size = 0
            shift = 0
            while pos < len(data):
                byte = data[pos]
                pos += 1
                size |= (byte & 0x7F) << shift
                shift += 7
                if byte < 0x80:
                    break
            pos += size
        elif wire == 1:
            pos += 8
        elif wire == 5:
            pos += 4
        else:
            return out
    return out


def describe_frame(frame: bytes) -> dict:
    """Describe one server frame: opcode, message id and scalar fields of its protobuf body."""
    if len(frame) < 2:
        return {"bytes": len(frame)}
    opcode = frame[0] & 0x0F
    length = frame[1] & 0x7F
    start = 2
    if length == 126:
        length = int.from_bytes(frame[2:4], "big")
        start = 4
    elif length == 127:
        length = int.from_bytes(frame[2:10], "big")
        start = 10
    payload = frame[start:start + length]
    if opcode == 1:
        return {"opcode": 1, "text": payload[:240].decode("utf-8", "replace")}
    if len(payload) < 6:
        return {"opcode": opcode, "bytes": len(payload)}
    message_id = int.from_bytes(payload[4:6], "big")
    return {
        "opcode": opcode,
        "message_id": message_id,
        "body_bytes": len(payload) - 6,
        "varint_fields": _varint_fields(payload[6:]),
    }


class TracedSocket:
    def __init__(self, sock, record: Callable[..., None]) -> None:
        self._sock = sock
        self._record = record

    def sendall(self, data: bytes, *args) -> None:
        try:
            self._record("outgoing_frame", **describe_frame(bytes(data)))
        except Exception as exc:  # tracing must never break the connection
            self._record("outgoing_trace_error", error=type(exc).__name__)
        return self._sock.sendall(data, *args)

    def __getattr__(self, name):
        return getattr(self._sock, name)
