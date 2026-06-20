"""
Read the next product to make a video for, and write status back.

Primary source: the Google Sheet "Inbox" tab (service account).
Fallback: a local CSV (scraper/products.csv) for offline testing.

A product is "next" if its Status column == "Ready". After a successful run we
set it to "Posted"; on failure, "Failed".
"""

from __future__ import annotations

import csv
from pathlib import Path

from .config import COL, ENV, SHEET_RANGE, STATUS_DONE, STATUS_FAILED, STATUS_READY, Product


# ---------------------------------------------------------------------------
# Google Sheets backend
# ---------------------------------------------------------------------------
def _sheets_service():
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    sa_path = ENV.get("GOOGLE_SERVICE_ACCOUNT_JSON", "./scraper/service-account.json")
    if not Path(sa_path).exists():
        raise FileNotFoundError(
            f"Service account JSON not found at {sa_path}. Create one in Google Cloud "
            "Console (IAM → Service Accounts → Keys) and share the sheet with its email."
        )
    creds = service_account.Credentials.from_service_account_file(
        sa_path, scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    return build("sheets", "v4", credentials=creds)


def _row_to_product(row: list[str], row_number: int) -> Product:
    def get(key: str) -> str:
        idx = COL[key]
        return row[idx].strip() if idx < len(row) else ""

    return Product(
        row_number=row_number,
        name=get("name"),
        price_thb=get("price"),
        commission_pct=get("commission"),
        sales=get("sales"),
        affiliate_url=get("affiliate_url"),
        niche=get("niche"),
        notes=get("notes"),
        image_url=get("image_url"),
    )


def next_ready_from_sheets() -> Product | None:
    svc = _sheets_service()
    sheet_id = ENV["GOOGLE_SHEET_ID"]
    resp = svc.spreadsheets().values().get(spreadsheetId=sheet_id, range=SHEET_RANGE).execute()
    rows = resp.get("values", [])
    # Row 1 is headers -> data starts at sheet row 2 (index 1)
    for i, row in enumerate(rows[1:], start=2):
        status = row[COL["status"]].strip() if COL["status"] < len(row) else ""
        if status.lower() == STATUS_READY.lower():
            return _row_to_product(row, i)
    return None


def set_status_sheets(row_number: int, status: str, note: str = "") -> None:
    svc = _sheets_service()
    sheet_id = ENV["GOOGLE_SHEET_ID"]
    updates = [{"range": f"Inbox!H{row_number}", "values": [[status]]}]
    if note:
        updates.append({"range": f"Inbox!I{row_number}", "values": [[note]]})
    svc.spreadsheets().values().batchUpdate(
        spreadsheetId=sheet_id,
        body={"valueInputOption": "USER_ENTERED", "data": updates},
    ).execute()


# ---------------------------------------------------------------------------
# CSV backend (offline / testing)
# ---------------------------------------------------------------------------
def next_ready_from_csv(path: str = "scraper/products.csv") -> Product | None:
    p = Path(path)
    if not p.exists():
        return None
    with p.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for i, row in enumerate(rows, start=2):
        if row.get("status", "Ready").strip().lower() == STATUS_READY.lower():
            return Product(
                row_number=i,
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


# ---------------------------------------------------------------------------
# Unified front door
# ---------------------------------------------------------------------------
def get_next_product(source: str = "sheets") -> Product | None:
    return next_ready_from_csv() if source == "csv" else next_ready_from_sheets()


def mark_done(product: Product, source: str, publish_result: dict) -> None:
    if source != "sheets":
        return
    svc = _sheets_service()
    sheet_id = ENV["GOOGLE_SHEET_ID"]
    n = product.row_number

    def _platform_status(res: dict) -> str:
        if not res:
            return "—"
        if res.get("media_id") or res.get("publish_id") or res.get("status") == "uploaded":
            return "Posted"
        if res.get("skipped"):
            return "Skipped"
        if res.get("error"):
            return f"Failed"
        return "—"

    tt_status = _platform_status(publish_result.get("tiktok", {}))
    ig_status = _platform_status(publish_result.get("instagram", {}))

    updates = [
        {"range": f"Inbox!H{n}", "values": [[STATUS_DONE]]},
        {"range": f"Inbox!K{n}", "values": [[tt_status]]},
        {"range": f"Inbox!L{n}", "values": [[ig_status]]},
        {"range": f"Inbox!M{n}", "values": [["—"]]},  # Shopee Video is always manual
    ]
    svc.spreadsheets().values().batchUpdate(
        spreadsheetId=sheet_id,
        body={"valueInputOption": "USER_ENTERED", "data": updates},
    ).execute()


def mark_failed(product: Product, source: str, reason: str) -> None:
    if source == "sheets":
        set_status_sheets(product.row_number, STATUS_FAILED, reason[:400])
