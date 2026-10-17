#!/usr/bin/env python3
"""Parse LeBian's packaged resource index and compare it with both XAPK APKs."""

from __future__ import annotations

import argparse
import collections
import csv
import io
import json
import pathlib
import re
import struct
import zipfile


def read_xapk_member(xapk: zipfile.ZipFile, apk_name: str, member: str) -> bytes:
    with zipfile.ZipFile(io.BytesIO(xapk.read(apk_name))) as apk:
        return apk.read(member)


def parse_lbresinfo(data: bytes) -> tuple[list[dict[str, object]], dict[str, object]]:
    eocd = data.rfind(b"PK\x05\x06")
    if eocd < 0:
        raise ValueError("EOCD signature not found")
    values = struct.unpack_from("<IHHHHIIH", data, eocd)
    _, disk, cd_disk, disk_entries, total_entries, cd_size, reported_cd_offset, comment_size = values
    cd_start = data.find(b"PK\x01\x02")
    if cd_start < 0:
        raise ValueError("central-directory signature not found")

    records: list[dict[str, object]] = []
    position = cd_start
    for _ in range(total_entries):
        if position + 46 > len(data):
            raise ValueError(f"central-directory record at {position} is truncated")
        fields = struct.unpack_from("<IHHHHHHIIIHHHHHII", data, position)
        (signature, made_by, needed, flags, method, mtime, mdate, crc32,
         compressed_size, size, name_len, extra_len, file_comment_len,
         disk_start, internal_attr, external_attr, local_header_offset) = fields
        if signature != 0x02014B50:
            raise ValueError(f"bad central-directory signature at {position}: {signature:#x}")
        name_bytes = data[position + 46:position + 46 + name_len]
        encoding = "utf-8" if flags & 0x800 else "cp437"
        name = name_bytes.decode(encoding, "replace")
        records.append({
            "path": name,
            "size": size,
            "compressed_size": compressed_size,
            "crc32": f"{crc32:08x}",
            "compression_method": method,
            "flags": flags,
            "local_header_offset": local_header_offset,
        })
        position += 46 + name_len + extra_len + file_comment_len

    metadata = {
        "eocd_offset": eocd,
        "entry_count_reported": total_entries,
        "entries_on_disk_reported": disk_entries,
        "central_directory_size_reported": cd_size,
        "central_directory_offset_reported": reported_cd_offset,
        "central_directory_offset_observed": cd_start,
        "central_directory_parse_end": position,
        "zip_comment_size": comment_size,
        "disk_number": disk,
        "central_directory_disk_number": cd_disk,
        "note": "The reported central-directory offset is outside this file; records were parsed from the observed PK\\x01\\x02 sequence. This is an index, not a verified extractable ZIP payload.",
    }
    return records, metadata


def category(path: str) -> str:
    suffix = pathlib.PurePosixPath(path).suffix.lower()
    return {
        ".json": "Cocos import/resource metadata",
        ".pkm": "ETC texture",
        ".png": "PNG texture/image",
        ".mp3": "audio",
    }.get(suffix, "other")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("xapk", type=pathlib.Path)
    parser.add_argument("--output", type=pathlib.Path, default=pathlib.Path("project/analysis/outputs"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(args.xapk) as xapk:
        outer_names = set(xapk.namelist())
        base_name = "com.oversea.spinarena.apk"
        assets_name = "NewAssets.apk"
        base = zipfile.ZipFile(io.BytesIO(xapk.read(base_name)))
        assets = zipfile.ZipFile(io.BytesIO(xapk.read(assets_name)))
        base_files = {info.filename for info in base.infolist() if not info.is_dir()}
        asset_files = {info.filename for info in assets.infolist() if not info.is_dir()}
        stream_text = read_xapk_member(xapk, base_name, "assets/lebian/lbstream").decode("utf-8", "replace")
        stream_paths = [line.strip() for line in stream_text.splitlines() if line.strip()]
        tryflag_text = read_xapk_member(xapk, base_name, "assets/tryflag").decode("utf-8", "replace")
        lbresinfo = read_xapk_member(xapk, base_name, "assets/lbresinfo")
        orig_size_text = read_xapk_member(xapk, base_name, "assets/origSize.txt").decode("ascii", "replace").strip()
        try:
            orig_sizes = [int(value) for value in re.split(r"[;,\s]+", orig_size_text) if value]
        except ValueError:
            orig_sizes = []

    index_records, index_meta = parse_lbresinfo(lbresinfo)
    indexed_paths = {str(record["path"]) for record in index_records}
    available = base_files | asset_files
    missing_index = [record for record in index_records if record["path"] != "AndroidManifest.xml" and record["path"] not in available]
    stream_missing = [path for path in stream_paths if path.startswith("assets/") and path not in available]
    missing_not_indexed = sorted(set(stream_missing) - indexed_paths)

    index_path = args.output / "lebian_stream_resource_index.csv"
    (args.output / "tryflag.txt").write_text(tryflag_text, encoding="utf-8")
    with index_path.open("w", newline="", encoding="utf-8") as file:
        fields = ["path", "size", "compressed_size", "crc32", "compression_method", "flags", "local_header_offset", "category", "package_state"]
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        for record in index_records:
            path = str(record["path"])
            writer.writerow({
                **record,
                "category": category(path),
                "package_state": "present in supplied XAPK" if path in available else "absent from supplied XAPK; expected stream index entry",
            })

    all_path = args.output / "lebian_stream_path_inventory.csv"
    record_by_path = {str(record["path"]): record for record in index_records}
    with all_path.open("w", newline="", encoding="utf-8") as file:
        fields = ["path", "size", "crc32", "source_index", "package_state", "category"]
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        for path in stream_paths:
            record = record_by_path.get(path)
            if path in available:
                state = "present in supplied XAPK"
            elif record:
                state = "absent; indexed by lbresinfo"
            else:
                state = "not found by exact path; packaging/root mapping needs review"
            writer.writerow({
                "path": path,
                "size": record.get("size", "") if record else "",
                "crc32": record.get("crc32", "") if record else "",
                "source_index": "lbresinfo" if record else "lbstream only",
                "package_state": state,
                "category": category(path),
            })

    total_missing_size = sum(int(record["size"]) for record in missing_index)
    ext_counts = collections.Counter(pathlib.PurePosixPath(str(r["path"])).suffix.lower() for r in missing_index)
    ext_sizes = {
        ext: sum(int(r["size"]) for r in missing_index if pathlib.PurePosixPath(str(r["path"])).suffix.lower() == ext)
        for ext in sorted(ext_counts)
    }
    summary = {
        "xapk": str(args.xapk.resolve()),
        "base_apk_files": len(base_files),
        "asset_split_files": len(asset_files),
        "lbstream_path_count": len(stream_paths),
        "lbstream_unique_paths": len(set(stream_paths)),
        "lbresinfo_index_records": len(index_records),
        "lbresinfo_index_unique_paths": len(indexed_paths),
        "lbresinfo_path_missing_from_xapk": len(missing_index),
        "indexed_missing_size_bytes": total_missing_size,
        "indexed_missing_size_gib": round(total_missing_size / 1024**3, 4),
        "indexed_missing_extension_counts": dict(sorted(ext_counts.items())),
        "indexed_missing_extension_sizes_bytes": ext_sizes,
        "lbstream_asset_paths_missing_from_xapk": len(stream_missing),
        "lbstream_missing_paths_not_in_lbresinfo": len(missing_not_indexed),
        "lbstream_missing_not_indexed_sample": missing_not_indexed[:50],
        "origSize_txt_values": orig_sizes,
        "origSize_second_matches_indexed_resource_bytes": len(orig_sizes) > 1 and orig_sizes[1] == total_missing_size,
        "lbresinfo_container": index_meta,
        "outputs": {
            "resource_index_csv": str(index_path.resolve()),
            "full_path_inventory_csv": str(all_path.resolve()),
        },
        "interpretation_limits": [
            "lbstream and lbresinfo establish path inventory and per-file CRC32/size metadata, not a captured live request or server URL.",
            "Entries marked absent are absent from the supplied base and NewAssets APK files; a device-side cache is not available for comparison.",
            "CRC32 comes from the embedded index; no SHA-256 is available for resources whose bytes are absent.",
            "The resource index's central-directory offset is inconsistent with the physical file, so its records were parsed directly and not extracted as a ZIP.",
        ],
    }
    summary_path = args.output / "lebian_stream_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: summary[key] for key in [
        "lbstream_path_count", "lbstream_unique_paths", "lbresinfo_index_records",
        "lbresinfo_path_missing_from_xapk", "indexed_missing_size_bytes",
        "indexed_missing_extension_counts", "lbstream_asset_paths_missing_from_xapk",
        "lbstream_missing_paths_not_in_lbresinfo", "origSize_txt_values",
        "origSize_second_matches_indexed_resource_bytes", "outputs",
    ]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
