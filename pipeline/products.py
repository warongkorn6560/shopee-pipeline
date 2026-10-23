"""
Flow A product queue.

Primary source: the dashboard's queue (pipeline.hub). Claiming marks the
product "Producing"; afterwards it becomes "Posted" (video delivered for
review) or "Failed" with the reason.
Offline source: scraper/products.csv, for local tests without the dashboard.
"""

from __future__ import annotations

import csv
from pathlib import Path

from . import hub
from .config import STATUS_DONE, STATUS_FAILED, STATUS_READY, Product


def _from_hub(item: dict) -> Product:
    return Product(
        ref=item["id"],
        name=item.get("name", ""),
        price_thb=str(item.get("price", "")),
        commission_pct=str(item.get("commission", "")),
        sales=str(item.get("sales", "")),
        affiliate_url=item.get("url", ""),
        niche="",
        notes=item.get("notes", ""),
        image_url=item.get("image", ""),
    )


def next_ready_from_csv(path: str = "scraper/products.csv") -> Product | None:
    p = Path(path)
    if not p.exists():
        return None
    with p.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for i, row in enumerate(rows, start=2):
        if row.get("status", "Ready").strip().lower() == STATUS_READY.lower():
            return Product(
                ref=f"csv-{i}",
                name=row.get("name", ""),
                price_thb=row.get("price_thb", ""),
                commission_pct=row.get("commission_pct", ""),
                sales=row.get("sales", ""),
                affiliate_url=row.get("affiliate_url", ""),
                niche=row.get("niche", "Pet supplies & toys"),
                notes=row.get("notes", ""),
                image_url=row.get("image_url", ""),
            )
    return None


def get_next_product(source: str = "platform") -> Product | None:
    if source == "csv":
        return next_ready_from_csv()
    item = hub.claim("shopee").get("item")
    return _from_hub(item) if item else None


def mark_done(product: Product, source: str, video_id: str = "") -> None:
    if source == "platform":
        hub.update("shopee", product.ref, status=STATUS_DONE, videoId=video_id, lastError="")


def mark_failed(product: Product, source: str, reason: str) -> None:
    if source == "platform":
        hub.update("shopee", product.ref, status=STATUS_FAILED, lastError=reason[:400])
