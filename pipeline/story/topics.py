"""
Topic queue for Flow B, stored in the "Stories" tab of the pipeline Sheet.

  A Date | B Topic | C Angle / Notes | D Status | E Title | F Run | G Published | H Log

Status lifecycle: Ready → Producing → Done (sent for review) / Posted (auto-
published) / Failed. "Hold" parks a topic. The tab is created on first use and
seeded with starter topics so the flow has material from day one.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from ..config import ENV, STORY_TAB

HEADER = ["Date", "Topic", "Angle / Notes", "Status", "Title", "Run", "Published", "Log"]
READY, PRODUCING, DONE, POSTED, FAILED = "Ready", "Producing", "Done", "Posted", "Failed"

STARTER_TOPICS = [
    ("ทำไมแผนที่ประเทศไทยถึงมีรูปร่างคล้ายขวาน", "เล่าว่ารูปร่างประเทศเกิดจากภูมิประเทศและเส้นเขตแดนที่ค่อยๆ ลงตัว"),
    ("ทำไมเกาะกรีนแลนด์ในแผนที่โลกดูใหญ่กว่าความจริงมาก", "อธิบายการฉายแผนที่แบบเมอร์เคเตอร์ เทียบขนาดจริงกับแอฟริกา"),
    ("กรุงเทพฯ เคยเป็นเมืองแห่งคลอง จนได้ชื่อว่าเวนิสตะวันออก", "ชีวิตริมคลองสมัยก่อน และทำไมคลองหายไป"),
    ("เส้นแบ่งวันสากลคืออะไร ทำไมบางประเทศข้ามวันได้", "เล่าเรื่องซามัวที่กระโดดข้ามวันในปี 2011"),
    ("อาณาจักรสุโขทัยตั้งอยู่ตรงไหนบนแผนที่ปัจจุบัน", "พาดูเมืองเก่า แม่น้ำยม และเส้นทางการค้า"),
    ("ทำไมแม่น้ำเจ้าพระยาถึงคดเคี้ยว และคนไทยขุดลัดแม่น้ำอย่างไร", "คลองลัดสมัยอยุธยาที่เปลี่ยนเส้นทางน้ำ"),
]


@dataclass
class Topic:
    row_number: int | None
    topic: str
    angle: str = ""
    source: str = "sheet"  # sheet | auto | cli


def _svc():
    from ..products import _sheets_service
    return _sheets_service()


def _sheet_id() -> str:
    return ENV["GOOGLE_SHEET_ID"]


def ensure_tab() -> None:
    """Create the Stories tab (header + starter topics) if it does not exist."""
    svc = _svc()
    meta = svc.spreadsheets().get(spreadsheetId=_sheet_id(), fields="sheets.properties").execute()
    if any(s["properties"]["title"] == STORY_TAB for s in meta.get("sheets", [])):
        return
    resp = svc.spreadsheets().batchUpdate(spreadsheetId=_sheet_id(), body={"requests": [
        {"addSheet": {"properties": {"title": STORY_TAB, "gridProperties": {"frozenRowCount": 1}}}},
    ]}).execute()
    tab_id = resp["replies"][0]["addSheet"]["properties"]["sheetId"]
    today = dt.date.today().isoformat()
    rows = [HEADER] + [[today, t, a, READY, "", "", "", ""] for t, a in STARTER_TOPICS]
    svc.spreadsheets().values().update(
        spreadsheetId=_sheet_id(), range=f"{STORY_TAB}!A1", valueInputOption="RAW",
        body={"values": rows}).execute()
    svc.spreadsheets().batchUpdate(spreadsheetId=_sheet_id(), body={"requests": [
        {"repeatCell": {"range": {"sheetId": tab_id, "startRowIndex": 0, "endRowIndex": 1},
                        "cell": {"userEnteredFormat": {"textFormat": {"bold": True}}},
                        "fields": "userEnteredFormat.textFormat.bold"}},
    ]}).execute()
    print(f"  [topics] created '{STORY_TAB}' tab with {len(STARTER_TOPICS)} starter topics")


def _rows() -> list[list[str]]:
    resp = _svc().spreadsheets().values().get(
        spreadsheetId=_sheet_id(), range=f"{STORY_TAB}!A:H").execute()
    return resp.get("values", [])


def _cell(row: list[str], i: int) -> str:
    return row[i].strip() if i < len(row) else ""


def next_ready() -> Topic | None:
    for n, row in enumerate(_rows()[1:], start=2):
        if _cell(row, 3).lower() == READY.lower() and _cell(row, 1):
            return Topic(row_number=n, topic=_cell(row, 1), angle=_cell(row, 2))
    return None


def previous_topics() -> list[str]:
    return [_cell(r, 1) for r in _rows()[1:] if _cell(r, 1)]


def append(topic: str, angle: str, status: str) -> int:
    resp = _svc().spreadsheets().values().append(
        spreadsheetId=_sheet_id(), range=f"{STORY_TAB}!A:H", valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": [[dt.date.today().isoformat(), topic, angle, status, "", "", "", ""]]},
    ).execute()
    rng = resp.get("updates", {}).get("updatedRange", "")  # e.g. Stories!A9:H9
    return int(rng.rsplit("!", 1)[-1].split(":")[0].lstrip("ABCDEFGH")) if rng else 0


def update(row_number: int | None, *, status: str | None = None, title: str | None = None,
           run: str | None = None, published: str | None = None, log: str | None = None) -> None:
    if not row_number:
        return
    cols = {"D": status, "E": title, "F": run, "G": published, "H": log}
    data = [{"range": f"{STORY_TAB}!{c}{row_number}", "values": [[v[:480]]]}
            for c, v in cols.items() if v is not None]
    if data:
        _svc().spreadsheets().values().batchUpdate(
            spreadsheetId=_sheet_id(),
            body={"valueInputOption": "RAW", "data": data}).execute()
