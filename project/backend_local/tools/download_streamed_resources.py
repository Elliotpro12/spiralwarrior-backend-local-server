#!/usr/bin/env python3
"""Recover the indexed LeBian/Cocos resources from the public CDN.

Downloads use at most two workers and globally rate-limited request starts.
Existing valid files are reused. Interrupted transfers resume from a sibling
.part file when the server honors HTTP Range. Each completed file is checked
against its indexed byte size and CRC32 before it is moved into the preserved
relative-path tree.
"""

from __future__ import annotations

import argparse
import csv
import concurrent.futures
import hashlib
import json
import os
import re
import shutil
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any


INDEX_PATH = Path()
TRYFLAG_PATH = Path()
RESOURCE_ROOT = Path()
OUTPUTS = Path()
LOG_PATH = Path()
MANIFEST_PATH = Path()
SUMMARY_PATH = Path()
ALLOWED_EXTENSIONS = {".json", ".mp3", ".pkm", ".png"}
ALLOWED_PREFIX = PurePosixPath("assets/res")
USER_AGENT = "SpiralWarriorPreservationResearch/1.0"
LOG_FIELDS = [
    "timestamp_utc",
    "path",
    "status",
    "expected_size",
    "actual_size",
    "expected_crc32",
    "actual_crc32",
    "sha256",
    "source_host",
    "final_url",
    "attempts",
    "http_status",
    "error",
]
MANIFEST_FIELDS = [
    "path",
    "category",
    "expected_size",
    "expected_crc32",
    "status",
    "actual_size",
    "actual_crc32",
    "sha256",
    "source_host",
    "attempts",
    "error",
]


class DownloadFailure(Exception):
    def __init__(self, message: str, http_status: int | None = None):
        super().__init__(message)
        self.http_status = http_status


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def hash_file(path: Path) -> tuple[int, str, str]:
    crc = 0
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            size += len(chunk)
            crc = zlib.crc32(chunk, crc)
            digest.update(chunk)
    return size, f"{crc & 0xFFFFFFFF:08x}", digest.hexdigest()


def safe_resource_path(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or path.suffix.lower() not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsafe or unsupported indexed path: {value!r}")
    if path.parts[:2] != ALLOWED_PREFIX.parts:
        raise ValueError(f"Path is outside assets/res: {value!r}")
    return path


def load_index() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with INDEX_PATH.open("r", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            if not row.get("package_state", "").startswith("absent from supplied XAPK"):
                continue
            relative = safe_resource_path(row["path"])
            size = int(row["size"])
            crc32 = row["crc32"].lower().zfill(8)
            if size <= 0 or not re.fullmatch(r"[0-9a-f]{8}", crc32):
                raise ValueError(f"Invalid size/CRC in index for {row['path']}")
            rows.append(
                {
                    "path": relative.as_posix(),
                    "size": size,
                    "crc32": crc32,
                    "category": row.get("category", "unknown"),
                }
            )
    return rows


def derive_hosts() -> tuple[str, list[str]]:
    lines = TRYFLAG_PATH.read_text(encoding="utf-8").splitlines()
    if not lines or not lines[0].strip().endswith("/"):
        raise ValueError(f"Could not read the resource prefix from {TRYFLAG_PATH}")
    resource_prefix = lines[0].strip().lstrip("/")
    return resource_prefix, ["rcdnaws.loveota.net", "rcdnukd.loveota.net"]


def public_url(host: str, prefix: str, relative_path: str) -> str:
    encoded = urllib.parse.quote(relative_path, safe="/")
    return f"http://{host}/{prefix}{encoded}"


def valid_file(path: Path, expected_size: int, expected_crc32: str) -> tuple[bool, dict[str, Any]]:
    if not path.is_file():
        return False, {}
    size, crc32, sha256 = hash_file(path)
    return size == expected_size and crc32 == expected_crc32, {
        "actual_size": size,
        "actual_crc32": crc32,
        "sha256": sha256,
    }


class RateLimiter:
    def __init__(self, interval: float):
        self.interval = max(interval, 0.0)
        self.next_start = 0.0
        self.lock = threading.Lock()

    def wait(self) -> None:
        with self.lock:
            delay = self.next_start - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            self.next_start = time.monotonic() + self.interval


def download_once(
    host: str,
    prefix: str,
    relative_path: str,
    part_path: Path,
    expected_size: int,
    timeout: float,
    limiter: RateLimiter,
) -> tuple[str, int, str]:
    part_path.parent.mkdir(parents=True, exist_ok=True)
    offset = part_path.stat().st_size if part_path.exists() else 0
    if offset > expected_size:
        part_path.unlink()
        offset = 0

    if offset == expected_size and part_path.exists():
        return public_url(host, prefix, relative_path), 0, "existing complete partial"

    url = public_url(host, prefix, relative_path)
    headers = {"User-Agent": USER_AGENT, "Accept-Encoding": "identity"}
    if offset:
        headers["Range"] = f"bytes={offset}-"
    request = urllib.request.Request(url, headers=headers, method="GET")
    limiter.wait()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = getattr(response, "status", response.getcode())
            final_url = response.geturl()
            if status not in (200, 206):
                raise DownloadFailure(f"Unexpected HTTP status {status}", status)

            if offset and status == 206:
                content_range = response.headers.get("Content-Range", "")
                match = re.match(r"bytes\s+(\d+)-(\d+)/(\d+|\*)", content_range, re.I)
                if not match or int(match.group(1)) != offset:
                    raise DownloadFailure(f"Invalid Content-Range for resume: {content_range!r}", status)
                mode = "ab"
            else:
                # A server that ignores Range must be restarted from byte zero.
                mode = "wb"
                offset = 0

            written = offset
            with part_path.open(mode) as stream:
                while chunk := response.read(64 * 1024):
                    written += len(chunk)
                    if written > expected_size:
                        raise DownloadFailure(
                            f"Response exceeded indexed size ({written} > {expected_size})", status
                        )
                    stream.write(chunk)
            if written < expected_size:
                raise DownloadFailure(f"Short response ({written} of {expected_size} bytes)", status)
            return final_url, status, ""
    except urllib.error.HTTPError as error:
        retry_after = error.headers.get("Retry-After") if error.headers else None
        if retry_after and retry_after.isdigit():
            time.sleep(min(max(int(retry_after), 1), 60))
        raise DownloadFailure(f"HTTP {error.code}: {error.reason}", error.code) from error
    except urllib.error.URLError as error:
        raise DownloadFailure(f"Network error: {error.reason}") from error


def append_log(row: dict[str, Any]) -> None:
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    write_header = not LOG_PATH.exists() or LOG_PATH.stat().st_size == 0
    with LOG_PATH.open("a", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=LOG_FIELDS, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        writer.writerow(row)
        stream.flush()
        os.fsync(stream.fileno())


def write_manifest(rows: list[dict[str, Any]], states: dict[str, dict[str, Any]]) -> None:
    temporary = MANIFEST_PATH.with_suffix(".csv.tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=MANIFEST_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for item in rows:
            state = states[item["path"]]
            writer.writerow(
                {
                    "path": item["path"],
                    "category": item["category"],
                    "expected_size": item["size"],
                    "expected_crc32": item["crc32"],
                    **state,
                }
            )
    os.replace(temporary, MANIFEST_PATH)


def write_summary(rows: list[dict[str, Any]], states: dict[str, dict[str, Any]], finished: bool) -> dict[str, Any]:
    counts: dict[str, int] = {"recovered": 0, "failed": 0, "pending": 0}
    recovered_bytes = 0
    expected_bytes = sum(item["size"] for item in rows)
    category_counts: dict[str, dict[str, int]] = {}
    for item in rows:
        status = states[item["path"]].get("status", "pending")
        counts[status] = counts.get(status, 0) + 1
        category = item["category"]
        category_counts.setdefault(category, {"total": 0, "recovered": 0, "failed": 0, "pending": 0})
        category_counts[category]["total"] += 1
        category_counts[category][status] = category_counts[category].get(status, 0) + 1
        if status == "recovered":
            recovered_bytes += item["size"]
    result = {
        "source_index": str(INDEX_PATH),
        "resource_root": str(RESOURCE_ROOT),
        "primary_host": "rcdnaws.loveota.net",
        "fallback_host": "rcdnukd.loveota.net",
        "scope": "Only paths marked absent from the supplied XAPK in lbresinfo index",
        "finished": finished,
        "updated_utc": utc_now(),
        "files": counts,
        "expected_files": len(rows),
        "recovered_percentage": round(counts["recovered"] * 100 / len(rows), 2) if rows else 0.0,
        "expected_bytes": expected_bytes,
        "recovered_bytes": recovered_bytes,
        "recovered_byte_percentage": round(recovered_bytes * 100 / expected_bytes, 2) if expected_bytes else 0.0,
        "category_counts": category_counts,
        "manifest_csv": str(MANIFEST_PATH),
        "event_log_csv": str(LOG_PATH),
    }
    SUMMARY_PATH.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def recover_one(
    item: dict[str, Any],
    original_state: dict[str, Any],
    hosts: list[str],
    prefix: str,
    args: argparse.Namespace,
    limiter: RateLimiter,
) -> tuple[dict[str, Any], dict[str, Any]]:
    path = item["path"]
    target = RESOURCE_ROOT.joinpath(*PurePosixPath(path).parts)
    part_path = target.with_name(target.name + ".part")
    state = dict(original_state)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        corrupt = target.with_name(target.name + ".corrupt")
        suffix = 1
        while corrupt.exists():
            corrupt = target.with_name(target.name + f".{suffix}.corrupt")
            suffix += 1
        os.replace(target, corrupt)

    attempts = 0
    last_error = ""
    last_status: int | None = None
    final_url = ""
    final_host = ""
    succeeded = False
    for host in hosts:
        final_host = host
        for host_attempt in range(1, args.attempts_per_host + 1):
            attempts += 1
            try:
                final_url, last_status, error_text = download_once(
                    host, prefix, path, part_path, item["size"], args.timeout, limiter
                )
                if error_text:
                    last_error = error_text
                actual_size, actual_crc, digest = hash_file(part_path)
                if actual_size != item["size"] or actual_crc != item["crc32"]:
                    part_path.unlink(missing_ok=True)
                    raise DownloadFailure(
                        f"Integrity mismatch: size {actual_size}/{item['size']}, CRC32 {actual_crc}/{item['crc32']}",
                        last_status,
                    )
                os.replace(part_path, target)
                state.update(
                    {
                        "status": "recovered",
                        "actual_size": actual_size,
                        "actual_crc32": actual_crc,
                        "sha256": digest,
                        "source_host": host,
                        "attempts": attempts,
                        "error": "",
                    }
                )
                succeeded = True
                break
            except (DownloadFailure, OSError, TimeoutError) as error:
                last_error = str(error)
                if isinstance(error, DownloadFailure) and error.http_status == 429:
                    time.sleep(min(2 * host_attempt, 10))
                elif host_attempt < args.attempts_per_host:
                    time.sleep(1.0 * host_attempt)
        if succeeded:
            break

    if not succeeded:
        if part_path.exists() and part_path.stat().st_size == item["size"]:
            part_path.unlink(missing_ok=True)
        state.update(
            {
                "status": "failed",
                "actual_size": part_path.stat().st_size if part_path.exists() else "",
                "actual_crc32": "",
                "sha256": "",
                "source_host": final_host,
                "attempts": attempts,
                "error": last_error,
            }
        )

    log_row = {
        "timestamp_utc": utc_now(),
        "path": path,
        "status": state["status"],
        "expected_size": item["size"],
        "actual_size": state.get("actual_size", ""),
        "expected_crc32": item["crc32"],
        "actual_crc32": state.get("actual_crc32", ""),
        "sha256": state.get("sha256", ""),
        "source_host": state.get("source_host", ""),
        "final_url": final_url,
        "attempts": attempts,
        "http_status": last_status or "",
        "error": state.get("error", ""),
    }
    return state, log_row


def main() -> int:
    global INDEX_PATH, TRYFLAG_PATH, RESOURCE_ROOT, OUTPUTS, LOG_PATH, MANIFEST_PATH, SUMMARY_PATH
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, required=True, help="CSV produced by analyze_lebian_stream.py")
    parser.add_argument("--tryflag", type=Path, required=True, help="tryflag.txt extracted from the same XAPK")
    parser.add_argument("--output-dir", type=Path, required=True, help="Directory for resources and recovery reports")
    parser.add_argument("--interval", type=float, default=0.5, help="Minimum seconds between global request starts")
    parser.add_argument("--timeout", type=float, default=20.0, help="Per-request timeout in seconds")
    parser.add_argument("--attempts-per-host", type=int, default=2, help="Moderate retries per public CDN host")
    parser.add_argument("--checkpoint-every", type=int, default=50, help="Write summary/manifest after this many resources")
    parser.add_argument("--max-files", type=int, default=0, help="Optional cap for a staged run; 0 processes the full index")
    parser.add_argument("--workers", type=int, choices=(1, 2), default=2, help="At most two concurrent downloads; requests remain globally rate-limited")
    args = parser.parse_args()
    if args.interval < 0 or args.timeout <= 0 or args.attempts_per_host < 1 or args.checkpoint_every < 1 or args.max_files < 0:
        parser.error("interval must be nonnegative; timeout, retries, and checkpoint interval must be positive; max-files cannot be negative")

    INDEX_PATH = args.index.resolve()
    TRYFLAG_PATH = args.tryflag.resolve()
    output_dir = args.output_dir.resolve()
    RESOURCE_ROOT = output_dir / "resources"
    OUTPUTS = output_dir / "reports"
    LOG_PATH = OUTPUTS / "cdn_recovery_log.csv"
    MANIFEST_PATH = OUTPUTS / "cdn_recovery_manifest.csv"
    SUMMARY_PATH = OUTPUTS / "cdn_recovery_summary.json"

    rows = load_index()
    prefix, hosts = derive_hosts()
    if args.max_files:
        rows = rows[: args.max_files]
    RESOURCE_ROOT.mkdir(parents=True, exist_ok=True)
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    limiter = RateLimiter(args.interval)
    states: dict[str, dict[str, Any]] = {}

    # Revalidate all existing outputs; a log entry alone is never accepted as proof.
    for item in rows:
        target = RESOURCE_ROOT.joinpath(*PurePosixPath(item["path"]).parts)
        good, details = valid_file(target, item["size"], item["crc32"])
        states[item["path"]] = (
            {"status": "recovered", **details, "source_host": "existing verified file", "attempts": 0, "error": ""}
            if good
            else {"status": "pending", "actual_size": "", "actual_crc32": "", "sha256": "", "source_host": "", "attempts": 0, "error": ""}
        )

    logged_recovered: set[str] = set()
    if LOG_PATH.is_file():
        with LOG_PATH.open("r", encoding="utf-8-sig", newline="") as stream:
            logged_recovered = {
                row["path"]
                for row in csv.DictReader(stream)
                if row.get("status") == "recovered" and row.get("path")
            }
    for item in rows:
        path = item["path"]
        state = states[path]
        if state["status"] != "recovered" or path in logged_recovered:
            continue
        append_log(
            {
                "timestamp_utc": utc_now(),
                "path": path,
                "status": "recovered",
                "expected_size": item["size"],
                "actual_size": state.get("actual_size", ""),
                "expected_crc32": item["crc32"],
                "actual_crc32": state.get("actual_crc32", ""),
                "sha256": state.get("sha256", ""),
                "source_host": "existing verified file",
                "final_url": "",
                "attempts": 0,
                "http_status": "",
                "error": "",
            }
        )
        logged_recovered.add(path)

    pending_rows = [item for item in rows if states[item["path"]]["status"] != "recovered"]
    processed_since_checkpoint = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(recover_one, item, states[item["path"]], hosts, prefix, args, limiter): item
            for item in pending_rows
        }
        for number, future in enumerate(concurrent.futures.as_completed(futures), start=1):
            item = futures[future]
            path = item["path"]
            state, log_row = future.result()
            states[path] = state
            append_log(log_row)
            processed_since_checkpoint += 1

            if processed_since_checkpoint >= args.checkpoint_every:
                write_manifest(rows, states)
                summary = write_summary(rows, states, finished=False)
                print(
                    f"checkpoint {number}/{len(pending_rows)} pending processed: recovered={summary['files']['recovered']} "
                    f"failed={summary['files']['failed']} pending={summary['files']['pending']} "
                    f"({summary['recovered_percentage']}%; {summary['recovered_byte_percentage']}% bytes)",
                    flush=True,
                )
                processed_since_checkpoint = 0

    write_manifest(rows, states)
    summary = write_summary(rows, states, finished=(args.max_files == 0))
    print(json.dumps(summary, indent=2))
    return 0 if summary["files"]["failed"] == 0 and summary["files"]["pending"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
