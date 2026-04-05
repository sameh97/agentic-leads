"""
Node 3 — Email Enricher
========================
Waterfall (free → paid → paid):
  1. Website scrape      — BeautifulSoup, free
  2. Hunter.io           — domain search, ~$0.005/call
  3. Apollo.io           — people search, ~$0.01/call
"""
import os, re, logging, asyncio
from urllib.parse import urljoin, urlparse
import httpx
from bs4 import BeautifulSoup
from app.agents.state import LeadState

logger = logging.getLogger(__name__)

HUNTER_KEY = os.getenv("HUNTER_API_KEY", "")
APOLLO_KEY  = os.getenv("APOLLO_API_KEY", "")

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
DECISION_KWS = {"owner", "ceo", "founder", "president", "director", "manager"}
GENERIC_PFX  = {"info", "contact", "hello", "support", "admin", "noreply",
                 "no-reply", "sales", "office", "team", "enquiries"}

UA = "Mozilla/5.0 (compatible; LeadBot/1.0)"


# ── Layer 1: website scrape ───────────────────────────────────────────────────

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


# ── Layer 2: Hunter.io ────────────────────────────────────────────────────────

async def _hunter(domain: str) -> list[dict]:
    if not HUNTER_KEY or not domain:
        return []
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(
                "https://api.hunter.io/v2/domain-search",
                params={"domain": domain, "api_key": HUNTER_KEY, "limit": 10},
            )
            if r.status_code == 200:
                return r.json().get("data", {}).get("emails", [])
    except Exception as e:
        logger.warning(f"[hunter] {domain}: {e}")
    return []


# ── Layer 3: Apollo.io ────────────────────────────────────────────────────────

async def _apollo(company: str, domain: str) -> list[dict]:
    if not APOLLO_KEY or not domain:
        return []
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.post(
                "https://api.apollo.io/v1/mixed_people/search",
                json={
                    "api_key": APOLLO_KEY,
                    "q_organization_name": company,
                    "organization_domains": [domain],
                    "person_titles": ["owner", "ceo", "founder", "president", "general manager"],
                    "per_page": 5,
                },
            )
            if r.status_code == 200:
                return [
                    {"value": p["email"], "first_name": p.get("first_name", ""),
                     "last_name": p.get("last_name", ""), "position": p.get("title", ""),
                     "confidence": 70}
                    for p in r.json().get("people", []) if p.get("email")
                ]
    except Exception as e:
        logger.warning(f"[apollo] {company}: {e}")
    return []


# ── Scoring + selection ───────────────────────────────────────────────────────

def _email_score(email: str, position: str = "") -> int:
    pfx = email.split("@")[0].lower()
    s = 50
    if any(k in pfx for k in DECISION_KWS):      s += 30
    if any(k in position.lower() for k in DECISION_KWS): s += 20
    if pfx in GENERIC_PFX:                        s -= 30
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
    # Skip if demo already populated
    if biz.get("primary_email") and biz.get("source") == "demo":
        return biz

    site   = biz.get("website", "")
    domain = _domain(site)
    pool: list[dict] = []

    # Layer 1
    raw = await _scrape_site(site)
    for e in raw:
        pool.append({"value": e, "first_name": "", "last_name": "",
                     "position": "", "confidence": 60, "src": "scrape"})

    # Layer 2 — only if scrape found nothing
    if not pool and domain:
        for h in await _hunter(domain):
            pool.append({**h, "src": "hunter"})

    # Layer 3 — only if still nothing
    if not pool and domain:
        for a in await _apollo(biz.get("name", ""), domain):
            pool.append({**a, "src": "apollo"})

    if not pool:
        return {**biz, "enriched": False}

    scored = sorted(pool, key=lambda e: _email_score(e["value"], e.get("position", "")), reverse=True)
    best   = scored[0]
    owner  = f"{best.get('first_name','')} {best.get('last_name','')}".strip()

    return {
        **biz,
        "emails":         [e["value"] for e in scored if e.get("value")],
        "primary_email":  best["value"],
        "owner_name":     owner,
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