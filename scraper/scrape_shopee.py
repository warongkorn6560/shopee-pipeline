"""
Shopee Thailand daily product scraper for the affiliate pipeline.

Strategy:
  1. Hit Shopee TH's public search/discovery API (no login required for listings).
  2. Filter by commission rate, price ceiling, and minimum sales.
  3. Push the top N candidates either:
       - via webhook (Make.com custom webhook trigger),  OR
       - directly to Google Sheets 'Inbox' tab with a service account.

Run from CSV (recommended for V1):
    python scrape_shopee.py --source csv --csv products.csv --sink sheets

Run from live API (experimental — Shopee blocks plain requests with 403, needs curl_cffi or
playwright with stealth + real session cookies):
    python scrape_shopee.py --source api --top 3 --dry-run

Schedule (cron):
    0 9 * * *  cd /path/to/shopee-pipeline && python3 scraper/scrape_shopee.py --source csv --csv inbox/today.csv --sink sheets

Schedule (GitHub Actions): see .github/workflows/scrape.yml
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import quote

import requests

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    env.update({k: v for k, v in os.environ.items() if k in env or k.startswith(("SHOPEE_", "MAKE_", "GOOGLE_"))})
    return env


@dataclass
class Product:
    name: str
    price_thb: float
    commission_pct: float
    sales: int
    affiliate_url: str
    niche: str
    notes: str

    def to_row(self) -> list[str]:
        today = dt.date.today().isoformat()
        return [
            today,
            self.name,
            f"{self.price_thb:.2f}",
            f"{self.commission_pct:.0f}",
            str(self.sales),
            self.affiliate_url,
            self.niche,
            "New",
            self.notes,
        ]


SHOPEE_SEARCH = "https://shopee.co.th/api/v4/search/search_items"


def load_from_csv(path: Path, niche_default: str) -> list[Product]:
    """Read products from a CSV with columns:
       name, price_thb, commission_pct, sales, affiliate_url, niche (optional), notes (optional)
    """
    items: list[Product] = []
    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            items.append(
                Product(
                    name=row["name"].strip(),
                    price_thb=float(row["price_thb"]),
                    commission_pct=float(row["commission_pct"]),
                    sales=int(row["sales"]),
                    affiliate_url=row["affiliate_url"].strip(),
                    niche=row.get("niche", "").strip() or niche_default,
                    notes=row.get("notes", "").strip(),
                )
            )
    return items


def fetch_shopee_candidates(keyword: str, limit: int = 50) -> list[dict]:
    """Pull listing JSON. Public endpoint, no auth required."""
    params = {
        "by": "sales",
        "keyword": keyword,
        "limit": limit,
        "newest": 0,
        "order": "desc",
        "page_type": "search",
        "scenario": "PAGE_GLOBAL_SEARCH",
        "version": 2,
    }
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        ),
        "Accept": "application/json",
        "Referer": f"https://shopee.co.th/search?keyword={quote(keyword)}",
        "X-API-SOURCE": "pc",
    }
    r = requests.get(SHOPEE_SEARCH, params=params, headers=headers, timeout=30)
    r.raise_for_status()
    data = r.json()
    return data.get("items", []) or []


def parse_item(raw: dict, niche: str) -> Product | None:
    item = raw.get("item_basic") or raw.get("item") or raw
    if not item:
        return None
    name = item.get("name") or ""
    price_raw = item.get("price_min") or item.get("price") or 0
    price_thb = float(price_raw) / 100000.0 if price_raw else 0.0
    sales = int(item.get("historical_sold") or item.get("sold") or 0)
    shopid = item.get("shopid") or item.get("shop_id")
    itemid = item.get("itemid") or item.get("item_id")

    raw_pct = (item.get("raw_discount") or 0)
    commission_pct = float(raw_pct) if raw_pct else 0.0

    if not (shopid and itemid):
        return None

    affiliate_url = f"https://shopee.co.th/product/{shopid}/{itemid}"
    return Product(
        name=name.strip(),
        price_thb=price_thb,
        commission_pct=commission_pct,
        sales=sales,
        affiliate_url=affiliate_url,
        niche=niche,
        notes=f"shopid={shopid} itemid={itemid}",
    )


def filter_winners(
    items: Iterable[Product],
    min_commission_pct: float,
    max_price: float,
    min_sales: int,
) -> list[Product]:
    return sorted(
        (
            p for p in items
            if p.commission_pct >= min_commission_pct
            and p.price_thb < max_price
            and p.sales >= min_sales
        ),
        key=lambda p: (p.commission_pct, p.sales),
        reverse=True,
    )


def push_via_webhook(products: list[Product], webhook_url: str) -> None:
    for p in products:
        r = requests.post(webhook_url, json=asdict(p), timeout=30)
        r.raise_for_status()
        print(f"  -> webhook: {p.name[:60]} ({r.status_code})")
        time.sleep(1)


def push_via_sheets(products: list[Product], env: dict[str, str]) -> None:
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except ImportError:
        sys.exit("Install google libs: pip install google-api-python-client google-auth")

    sa_path = env.get("GOOGLE_SERVICE_ACCOUNT_JSON") or "./scraper/service-account.json"
    sheet_id = env.get("GOOGLE_SHEET_ID")
    if not sheet_id:
        sys.exit("GOOGLE_SHEET_ID missing from .env")
    if not Path(sa_path).exists():
        sys.exit(
            f"Service account JSON not found at {sa_path}. "
            "Create one at console.cloud.google.com -> IAM -> Service Accounts -> Keys, "
            f"then share the sheet (ID {sheet_id}) as Editor with the service account's email."
        )

    creds = service_account.Credentials.from_service_account_file(
        sa_path, scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    svc = build("sheets", "v4", credentials=creds)
    body = {"values": [p.to_row() for p in products]}
    resp = (
        svc.spreadsheets()
        .values()
        .append(
            spreadsheetId=sheet_id,
            range="Inbox!A:I",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body=body,
        )
        .execute()
    )
    print(f"  -> sheets: appended {len(products)} row(s); updated range = {resp.get('updates', {}).get('updatedRange')}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["csv", "api"], default="csv",
                    help="csv = read from --csv file (reliable). api = live Shopee scrape (experimental).")
    ap.add_argument("--csv", default="scraper/products.csv", help="CSV file for --source csv")
    ap.add_argument("--keyword", default="ของเล่นสัตว์เลี้ยง", help="Thai search keyword for --source api")
    ap.add_argument("--niche", default="Pet supplies & toys")
    ap.add_argument("--top", type=int, default=3)
    ap.add_argument("--min-commission", type=float, default=40.0)
    ap.add_argument("--max-price", type=float, default=500.0)
    ap.add_argument("--min-sales", type=int, default=30)
    ap.add_argument("--sink", choices=["sheets", "webhook", "stdout"], default="stdout")
    ap.add_argument("--webhook-url", default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    env = load_env()
    print(f"[scraper] source={args.source} sink={args.sink}")

    if args.source == "csv":
        csv_path = Path(args.csv)
        if not csv_path.exists():
            sys.exit(f"CSV not found: {csv_path}. Expected columns: name,price_thb,commission_pct,sales,affiliate_url[,niche,notes]")
        parsed = load_from_csv(csv_path, args.niche)
        print(f"[scraper] loaded {len(parsed)} products from {csv_path}")
    else:
        raw_items = fetch_shopee_candidates(args.keyword, limit=50)
        parsed = [p for p in (parse_item(r, args.niche) for r in raw_items) if p]
        print(f"[scraper] fetched {len(raw_items)} raw items from Shopee, parsed {len(parsed)}")

    winners = filter_winners(
        parsed,
        min_commission_pct=args.min_commission,
        max_price=args.max_price,
        min_sales=args.min_sales,
    )[: args.top]

    print(f"[scraper] {len(winners)} winners pass filters (commission>={args.min_commission}%, price<{args.max_price}, sales>={args.min_sales})")
    for p in winners:
        print(f"  - {p.name[:60]:<60} | {p.price_thb:>6.0f} THB | comm {p.commission_pct:>3.0f}% | sold {p.sales}")

    if args.dry_run or not winners:
        return 0

    if args.sink == "stdout":
        for p in winners:
            print(json.dumps(asdict(p), ensure_ascii=False))
    elif args.sink == "webhook":
        url = args.webhook_url or env.get("MAKE_WEBHOOK_URL")
        if not url:
            sys.exit("--webhook-url required (or set MAKE_WEBHOOK_URL in .env)")
        push_via_webhook(winners, url)
    elif args.sink == "sheets":
        push_via_sheets(winners, env)

    return 0


if __name__ == "__main__":
    sys.exit(main())
