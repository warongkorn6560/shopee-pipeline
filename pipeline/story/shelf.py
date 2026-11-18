"""
Affiliate products that fit the wildlife clips (binoculars for a bird story, a plush tiger for a tiger story).

  python -m pipeline.story.shelf import <BatchProductLinks.csv> [tag ...]   # add Shopee/Lazada offer links
  python -m pipeline.story.shelf show

Edits by hand: copy shelf.json to dashboard/lib/shelf.json too (the public /shop page).

shelf.json: {"channels": [...], "items": [{"name", "url", "label", "tags": [...], "any": bool}]}
An item matches when one of its tags appears in the clip's subject (first word of the title); items with "any" fit every
wildlife clip and are used when nothing more specific matches. No match = no link (never a cat-litter
link under a tiger story). Free: plain keyword matching, no model call.
"""

from __future__ import annotations

import csv
import json
import sys
import zlib
from pathlib import Path

SHELF = Path(__file__).with_name("shelf.json")
PAGE_COPY = Path(__file__).parents[2] / "dashboard" / "lib" / "shelf.json"   # the public /shop page (IG bio link)


def _load() -> dict:
    return json.loads(SHELF.read_text(encoding="utf-8")) if SHELF.exists() else {"channels": [], "items": []}


def pick(channel_id: str, topic: str, title: str) -> dict | None:
    shelf = _load()
    if channel_id not in shelf["channels"]:
        return None
    # Only the subject (first word of the title, e.g. "นกชนหิน"): Thai has no spaces, so a tag like "นก"
    # also hides inside longer text ("บนก้อน") and the topic notes mention other animals.
    text = (title.split() or [topic])[0].lower()
    items = [i for i in shelf["items"] if i.get("url")]
    hits = [i for i in items if any(t.lower() in text for t in i.get("tags", []))] or \
           [i for i in items if i.get("any")]
    # Same clip → same product, different clips spread over the shelf.
    return hits[zlib.crc32(title.encode()) % len(hits)] if hits else None


def caption_line(item: dict) -> str:
    return (f"\n\n🛒 {item.get('label') or item['name'][:60]}\n🔗 {item['url']}\n"
            "(ลิงก์ affiliate — ช่องได้ค่าคอมเล็กน้อยเมื่อสั่งผ่านลิงก์)")


def import_csv(path: str, tags: list[str]) -> int:
    shelf = _load()
    have = {i["url"] for i in shelf["items"]}
    added = 0
    with open(path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            url = (row.get("Offer Link") or row.get("ลิงก์ข้อเสนอ") or row.get("affiliate_url") or "").strip()
            if url and url not in have:
                shelf["items"].append({"name": (row.get("Item Name") or row.get("ชื่อสินค้า") or "").strip(), "url": url, "label": "",
                                       "tags": tags, "any": not tags})
                have.add(url)
                added += 1
    for f in (SHELF, PAGE_COPY):
        f.write_text(json.dumps(shelf, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return added


if __name__ == "__main__":
    if sys.argv[1:2] == ["import"]:
        print(f"added {import_csv(sys.argv[2], sys.argv[3:])}")
    else:
        print(json.dumps(_load(), ensure_ascii=False, indent=1))
