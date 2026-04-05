"""Nodes 5 & 6 — Lead Scorer + CSV/XLSX Delivery."""
import os, csv, logging
from datetime import datetime
from pathlib import Path
from app.agents.state import LeadState

logger = logging.getLogger(__name__)
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "/tmp/leads"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

COLS = [
    "score", "name", "primary_email", "email_verified", "email_catchall",
    "email_status", "owner_name", "owner_position", "phone", "website",
    "address", "rating", "review_count", "category", "latitude", "longitude", "source",
]


# ── Scorer ────────────────────────────────────────────────────────────────────

def _score(lead: dict) -> int:
    s = 0
    rating  = float(lead.get("rating") or 0)
    reviews = int(lead.get("review_count") or 0)

    # Rating (25 pts)
    s += 25 if rating >= 4.5 else 18 if rating >= 4.0 else 10 if rating >= 3.0 else 0

    # Reviews (20 pts)
    s += 20 if reviews >= 100 else 15 if reviews >= 50 else 10 if reviews >= 20 else 5 if reviews >= 5 else 0

    # Email quality (30 pts)
    if lead.get("email_verified"):  s += 30
    elif lead.get("email_catchall"): s += 20
    elif lead.get("email_valid"):    s += 10

    # Owner-level contact (15 pts)
    kws = {"owner", "ceo", "founder", "president", "manager", "director"}
    pos = (lead.get("owner_position") or "").lower()
    pfx = (lead.get("primary_email") or "").split("@")[0].lower()
    if any(k in pos for k in kws):   s += 15
    elif any(k in pfx for k in kws): s += 10

    # Website present (10 pts)
    if lead.get("website"): s += 10

    return min(100, s)


def score_leads_node(state: LeadState) -> LeadState:
    leads = state.get("verified_leads", [])
    scored = sorted(
        [{**l, "score": _score(l)} for l in leads],
        key=lambda l: l["score"], reverse=True,
    )
    high = sum(1 for l in scored if l["score"] >= 70)
    logger.info(f"[scorer] {len(scored)} leads — {high} high-quality (≥70)")
    return {**state, "scored_leads": scored}


# ── Delivery ──────────────────────────────────────────────────────────────────

def deliver_leads_node(state: LeadState) -> LeadState:
    leads = state.get("scored_leads", [])
    slug  = state.get("raw_query", "leads")[:40].replace(" ", "_").replace("/", "-")
    ts    = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem  = f"{slug}_{ts}"

    # CSV
    csv_path = OUTPUT_DIR / f"{stem}.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS, extrasaction="ignore")
        w.writeheader()
        w.writerows(leads)
    logger.info(f"[deliver] CSV → {csv_path}  ({len(leads)} rows)")

    # XLSX
    xlsx_path = None
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
        from openpyxl.utils import get_column_letter

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Leads"

        hdr_fill = PatternFill("solid", fgColor="0F172A")
        hdr_font = Font(bold=True, color="FFFFFF", size=10)
        for ci, col in enumerate(COLS, 1):
            cell = ws.cell(row=1, column=ci, value=col.replace("_", " ").title())
            cell.fill = hdr_fill
            cell.font = hdr_font
            cell.alignment = Alignment(horizontal="center")

        g = PatternFill("solid", fgColor="DCFCE7")
        y = PatternFill("solid", fgColor="FEF9C3")
        r = PatternFill("solid", fgColor="FEE2E2")

        for ri, lead in enumerate(leads, 2):
            fill = g if lead["score"] >= 70 else y if lead["score"] >= 40 else r
            for ci, col in enumerate(COLS, 1):
                cell = ws.cell(row=ri, column=ci, value=lead.get(col, ""))
                cell.fill = fill

        for ci, col in enumerate(COLS, 1):
            maxw = max(len(col), *(len(str(l.get(col, ""))) for l in leads[:50])) + 2
            ws.column_dimensions[get_column_letter(ci)].width = min(maxw, 40)

        xlsx_path = OUTPUT_DIR / f"{stem}.xlsx"
        wb.save(xlsx_path)
        logger.info(f"[deliver] XLSX → {xlsx_path}")
    except ImportError:
        logger.warning("[deliver] openpyxl not installed, skipping XLSX")
    except Exception as e:
        logger.error(f"[deliver] XLSX error: {e}")

    return {
        **state,
        "final_csv_path":  str(csv_path),
        "final_xlsx_path": str(xlsx_path) if xlsx_path else "",
        "status": "done",
    }