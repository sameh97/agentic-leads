"""
Node 3 — Email Enricher
========================
Waterfall (free → free → paid):
  1. Check if RapidAPI Local Business Data already returned an email (free, already done)
  2. Website scrape (BeautifulSoup, completely free)
  3. RapidAPI Email Finder (rapidapi.com/theCele/api/email-finder7)
"""
import os, re, logging, asyncio
from urllib.parse import urljoin, urlparse
import httpx
from bs4 import BeautifulSoup
from app.agents.state import LeadState

logger = logging.getLogger(__name__)

RAPIDAPI_KEY  = os.getenv("RAPIDAPI_KEY", "")
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
DECISION_KWS  = {"owner", "ceo", "founder", "president", "director", "manager"}
GENERIC_PFX   = {"info", "contact", "hello", "support", "admin", "noreply",
                  "no-reply", "sales", "office", "team", "enquiries"}
UA = "Mozilla/5.0 (compatible; LeadBot/1.0)"


# ── Layer 1: already in RapidAPI response ─────────────────────────────────────
# (handled in maps_scraper — if primary_email already set, we skip enrichment)


# ── Layer 2: website scrape ───────────────────────────────────────────────────

async def _scrape_site(url: str) -> list[str]:
    if not url:
        return []
    if not url.startswith("http"):
        url = f"https://{url}"
    pages = [url, urljoin(url, "/contact"), urljoin(url, "/about")]
    found: set[str] = set()
    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as c:
        for page in pages:
            try:
                r = await c.get(page, headers={"User-Agent": UA})
                if "text/html" not in r.headers.get("content-type", ""):
                    continue
                soup = BeautifulSoup(r.text, "lxml")
                for a in soup.find_all("a", href=True):
                    if a["href"].startswith("mailto:"):
                        e = a["href"].replace("mailto:", "").split("?")[0].strip().lower()
                        if e:
                            found.add(e)
                for m in EMAIL_RE.finditer(soup.get_text()):
                    found.add(m.group().lower())
            except Exception:
                pass
    return [e for e in found if "@" in e and not e.endswith((".png", ".jpg", ".css"))]


# ── Layer 3: RapidAPI Email Finder ────────────────────────────────────────────

async def _rapidapi_email_finder(domain: str, company: str) -> list[dict]:
    """
    RapidAPI Email Finder by theCele
    https://rapidapi.com/theCele/api/email-finder7
    """
    if not RAPIDAPI_KEY or not domain:
        return []
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(
                "https://email-finder7.p.rapidapi.com/find",
                params={"domain": domain, "company": company},
                headers={
                    "X-RapidAPI-Key":  RAPIDAPI_KEY,
                    "X-RapidAPI-Host": "email-finder7.p.rapidapi.com",
                },
            )
            if r.status_code == 200:
                data = r.json()
                emails = data.get("emails", []) or []
                return [{"value": e if isinstance(e, str) else e.get("value",""),
                         "position": e.get("position","") if isinstance(e, dict) else "",
                         "confidence": e.get("confidence", 70) if isinstance(e, dict) else 70}
                        for e in emails if e]
    except Exception as e:
        logger.warning(f"[enricher] RapidAPI email finder failed for {domain}: {e}")
    return []


# ── Helpers ───────────────────────────────────────────────────────────────────

def _email_score(email: str, position: str = "") -> int:
    pfx = email.split("@")[0].lower()
    s = 50
    if any(k in pfx      for k in DECISION_KWS): s += 30
    if any(k in position.lower() for k in DECISION_KWS): s += 20
    if pfx in GENERIC_PFX: s -= 30
    return max(0, min(100, s))


def _domain(website: str) -> str:
    if not website:
        return ""
    if not website.startswith("http"):
        website = f"https://{website}"
    try:
        return urlparse(website).netloc.lstrip("www.")
    except Exception:
        return ""


async def _enrich_one(biz: dict) -> dict:
    # Layer 0: already have email from RapidAPI maps response
    if biz.get("primary_email") and biz.get("source") != "demo":
        return {**biz, "enriched": True}

    # Demo records already have emails
    if biz.get("source") == "demo" and biz.get("primary_email"):
        return biz

    site   = biz.get("website", "")
    domain = _domain(site)
    pool: list[dict] = []

    # Layer 1: website scrape (free)
    if site:
        raw = await _scrape_site(site)
        for e in raw:
            pool.append({"value": e, "position": "", "confidence": 60, "src": "scrape"})

    # Layer 2: RapidAPI email finder (free tier)
    if not pool and domain:
        results = await _rapidapi_email_finder(domain, biz.get("name", ""))
        for r in results:
            pool.append({**r, "src": "rapidapi_email_finder"})

    if not pool:
        return {**biz, "enriched": False}

    scored = sorted(pool, key=lambda e: _email_score(e["value"], e.get("position", "")), reverse=True)
    best   = scored[0]
    owner  = f"{best.get('first_name','')} {best.get('last_name','')}".strip()

    return {
        **biz,
        "emails":         [e["value"] for e in scored if e.get("value")],
        "primary_email":  best["value"],
        "owner_name":     owner or biz.get("owner_name", ""),
        "owner_position": best.get("position", ""),
        "enriched":       True,
    }


async def _run_all(businesses: list[dict]) -> tuple[list[dict], list[str]]:
    sem = asyncio.Semaphore(10)
    errors: list[str] = []

    async def safe(b: dict) -> dict:
        async with sem:
            try:
                return await _enrich_one(b)
            except Exception as e:
                errors.append(f"{b.get('name','?')}: {e}")
                return b

    results = await asyncio.gather(*[safe(b) for b in businesses])
    return list(results), errors


def enrich_websites_node(state: LeadState) -> LeadState:
    businesses = state.get("raw_businesses", [])
    logger.info(f"[enricher] {len(businesses)} businesses to enrich")

    enriched, errors = asyncio.run(_run_all(businesses))
    with_email = [b for b in enriched if b.get("primary_email")]

    logger.info(f"[enricher] {len(with_email)}/{len(enriched)} got email")
    return {**state, "enriched_leads": with_email, "enrichment_errors": errors}