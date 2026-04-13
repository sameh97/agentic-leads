"""
Node 2 — Maps Scraper
=====================
Primary:  RapidAPI "Local Business Data" (OpenWeb Ninja) — 100 free req/month
Fallback: Demo data (if no API key)

RapidAPI endpoint: https://rapidapi.com/letscrape-6bRBa3QguO5/api/local-business-data
"""
import os, logging, asyncio
import httpx
from app.agents.state import LeadState

logger = logging.getLogger(__name__)

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "")


async def _search_local_business(query: str, location: str, limit: int) -> list[dict]:
    """
    RapidAPI Local Business Data — OpenWeb Ninja
    Endpoint: /search
    Returns: business name, address, phone, website, rating, reviews, coords, email
    """
    url = "https://local-business-data.p.rapidapi.com/search"
    params = {
        "query":           f"{query} in {location}",
        "limit":           min(limit, 20),   # free plan: 20 results per request
        "lat":             "0",
        "lng":             "0",
        "zoom":            "13",
        "language":        "en",
        "region":          "us",
        "extract_emails_and_contacts": "true",  # includes emails if available
    }
    headers = {
        "X-RapidAPI-Key":  RAPIDAPI_KEY,
        "X-RapidAPI-Host": "local-business-data.p.rapidapi.com",
    }

    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(url, params=params, headers=headers)
        r.raise_for_status()
        data = r.json()

    results = data.get("data", [])
    logger.info(f"[maps_scraper] RapidAPI returned {len(results)} results")
    return [_normalize(b) for b in results]


def _normalize(r: dict) -> dict:
    """Normalize RapidAPI Local Business Data response to our schema."""
    # Email may be in top-level or nested contacts
    emails = r.get("emails", []) or []
    primary_email = emails[0] if emails else ""

    return {
        "name":          r.get("name", ""),
        "address":       r.get("full_address", "") or r.get("address", ""),
        "phone":         r.get("phone_number", "") or r.get("phone", ""),
        "website":       r.get("website", ""),
        "rating":        float(r.get("rating", 0) or 0),
        "review_count":  int(r.get("reviews", 0) or r.get("review_count", 0) or 0),
        "latitude":      r.get("latitude") or (r.get("coordinates") or {}).get("lat"),
        "longitude":     r.get("longitude") or (r.get("coordinates") or {}).get("lng"),
        "category":      (r.get("subtypes") or [None])[0] or r.get("type", ""),
        "source":        "rapidapi_local_business",
        # pre-populate email if already in response
        "emails":        emails,
        "primary_email": primary_email,
        "owner_name":    "",
        "owner_position": "",
        "email_valid":   False,
        "email_verified": False,
        "email_catchall": False,
        "email_status":  "",
        "score":         0,
        "enriched":      bool(primary_email),
    }


def _demo_records(btype: str, location: str, n: int = 15) -> list[dict]:
    """Synthetic data for demo / testing without any API keys."""
    import random
    samples = [
        ("Sunrise Services",      "owner@sunriseservices.com",   4.8, 142),
        ("Metro Pro Solutions",   "ceo@metropro.com",            4.6, 98),
        ("City Best Group",       "founder@citybest.com",        4.5, 67),
        ("Valley Experts LLC",    "mike@valleyexperts.com",      4.7, 203),
        ("Premier Local Co",      "info@premierlocal.com",       3.9, 31),
        ("Capital Works Inc",     "ceo@capitalworks.com",        4.6, 178),
        ("Downtown Specialists",  "hello@downtown.com",          4.1, 67),
        ("Neighborhood Pros",     "owner@nbhpros.com",           4.9, 312),
        ("Regional Masters",      "contact@regionalmasters.com", 4.3, 44),
        ("Apex Local Services",   "apex@services.com",           4.0, 22),
    ]
    records = []
    for i in range(n):
        name, email, rating, reviews = samples[i % len(samples)]
        name = f"{btype.title()} — {name}"
        records.append({
            "name":          name,
            "address":       f"{100+i} Main St, {location}",
            "phone":         f"+1-555-{100+i:04d}",
            "website":       f"https://www.{name.lower().replace(' ', '').replace('—','')}.com",
            "rating":        rating,
            "review_count":  reviews,
            "latitude":      40.7 + random.uniform(-0.1, 0.1),
            "longitude":     -74.0 + random.uniform(-0.1, 0.1),
            "category":      btype,
            "source":        "demo",
            "emails":        [email],
            "primary_email": email,
            "owner_name":    "",
            "owner_position": "",
            "email_valid":   True,
            "email_verified": True,
            "email_catchall": False,
            "email_status":  "valid",
            "enriched":      True,
            "score":         0,
        })
    return records


def scrape_maps_node(state: LeadState) -> LeadState:
    q   = state["business_type"]
    loc = state["location"]
    lim = state.get("max_results", 100)

    logger.info(f"[maps_scraper] '{q}' in '{loc}'")
    errors, businesses = [], []

    try:
        if RAPIDAPI_KEY:
            businesses = asyncio.run(_search_local_business(q, loc, lim))
        else:
            logger.warning("[maps_scraper] No RAPIDAPI_KEY — using demo data")
            businesses = _demo_records(q, loc)
    except Exception as e:
        errors.append(str(e))
        logger.error(f"[maps_scraper] {e}")
        businesses = _demo_records(q, loc)

    # Deduplicate
    seen, unique = set(), []
    for b in businesses:
        key = (b["name"].lower().strip(), b["address"].lower()[:30])
        if key not in seen:
            seen.add(key)
            unique.append(b)

    logger.info(f"[maps_scraper] {len(unique)} unique records")
    return {**state, "raw_businesses": unique, "scrape_errors": errors}