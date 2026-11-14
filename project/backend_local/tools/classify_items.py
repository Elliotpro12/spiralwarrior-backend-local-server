"""Write the item classification table next to the catalog (local, git-ignored data).

Usage (from backend_local):
    python tools/classify_items.py

Writes data/ITEMS_CLASSIFIED.tsv with one row per catalog item and prints a category summary.
Categories come from item_registry.py (client enum Item_ItemType).
"""

from __future__ import annotations

import collections
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import item_registry  # noqa: E402


def main() -> int:
    rows = sorted(item_registry.registry().values(), key=lambda entry: entry["id"])
    if not rows:
        print("The item catalog is empty; run tools/build_item_catalog.py first.")
        return 1
    output = ROOT / "data" / "ITEMS_CLASSIFIED.tsv"
    lines = ["ID\tNAME\tNAMED\tTYPE\tTYPE_NAME\tCATEGORY\tDESTINATION\tICON"]
    for entry in rows:
        lines.append("\t".join([
            str(entry["id"]), entry["name"], "yes" if entry["named"] else "no",
            str(entry["type"]), entry["type_name"], entry["category"], entry["destination"],
            "yes" if entry["icon"] else "no",
        ]))
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")

    by_category = collections.Counter(entry["category"] for entry in rows)
    by_destination = collections.Counter(entry["destination"] for entry in rows)
    print(f"Classified {len(rows)} items -> {output.name}")
    print("By category:")
    for category, count in by_category.most_common():
        print(f"  {category}: {count}")
    print("By destination:")
    for destination, count in by_destination.most_common():
        print(f"  {destination}: {count}")
    unnamed = sum(1 for entry in rows if not entry["named"])
    print(f"Items without a real name (generic 'Item NNNN'): {unnamed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
