"""
Node 2 — Maps Scraper
=====================
Primary:  Outscraper Google Maps API  ($3 / 1K records)
Fallback: Google Places Text Search   (free up to $200/mo credit)
"""
import os, logging, asyncio
from urllib.parse import urlencode
import httpx
from app.agents.state import LeadState

logger = logging.getLogger(__name__)

OUTSCRAPER_KEY  = os.getenv("OUTSCRAPER_API_KEY", "")
PLACES_KEY      = os.getenv("GOOGLE_PLACES_API_KEY", "")


# ── Outscraper ────────────────────────────────────────────────────────────────

async def _outscraper(query: str, location: str, limit: int) -> list[dict]:
    url = "https://api.app.outscraper.com/maps/search-v3"
    params = {
        "query":    f"{query} in {location}",
        "limit":    limit,
        "async":    False,
        "fields":   "name,full_address,phone,site,rating,reviews,latitude,longitude,type",
        "language": "en",
    }
    headers = {"X-API-KEY": OUTSCRAPER_KEY}
    async with httpx.AsyncClient(timeout=90) as c:
        r = await c.get(url, params=params, headers=headers)
        r.raise_for_status()
        raw = r.json().get("data", [[]])[0] or []
    return [_norm_outscraper(b) for b in raw]


def _norm_outscraper(r: dict) -> dict:
    return {
        "name":         r.get("name", ""),
        "address":      r.get("full_address", ""),
        "phone":        r.get("phone", ""),
        "website":      r.get("site", ""),
        "rating":       float(r.get("rating") or 0),
        "review_count": int(r.get("reviews") or 0),
        "latitude":     r.get("latitude"),
        "longitude":    r.get("longitude"),
        "category":     r.get("type", ""),
        "source":       "outscraper",
        # enrichment placeholders
        "emails": [], "primary_email": "", "owner_name": "",
        "owner_position": "", "email_valid": False,
        "email_verified": False, "email_catchall": False,
        "email_status": "", "score": 0,
    }


# ── Google Places fallback ────────────────────────────────────────────────────

async def _places(query: str, location: str, limit: int) -> list[dict]:
    base = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    results, token = [], None
    async with httpx.AsyncClient(timeout=30) as c:
        while len(results) < limit:
            params = {"query": f"{query} in {location}", "key": PLACES_KEY}
            if token:
                params = {"pagetoken": token, "key": PLACES_KEY}
            r = await c.get(base, params=params)
            r.raise_for_status()
            data = r.json()
            for p in data.get("results", []):
                results.append(_norm_places(p))
            token = data.get("next_page_token")
            if not token:
                break
            await asyncio.sleep(2)
    return results[:limit]


def _norm_places(r: dict) -> dict:
    geo = r.get("geometry", {}).get("location", {})
    return {
        "name":         r.get("name", ""),
        "address":      r.get("formatted_address", ""),
        "phone":        "",
        "website":      "",
        "rating":       float(r.get("rating") or 0),
        "review_count": int(r.get("user_ratings_total") or 0),
        "latitude":     geo.get("lat"),
        "longitude":    geo.get("lng"),
        "category":     ", ".join(r.get("types", [])),
        "place_id":     r.get("place_id", ""),
        "source":       "places_api",
        "emails": [], "primary_email": "", "owner_name": "",
        "owner_position": "", "email_valid": False,
        "email_verified": False, "email_catchall": False,
        "email_status": "", "score": 0,
    }


# ── Node ──────────────────────────────────────────────────────────────────────

def scrape_maps_node(state: LeadState) -> LeadState:
    q, loc, limit = state["business_type"], state["location"], state.get("max_results", 100)
    logger.info(f"[scrape_maps] '{q}' in '{loc}' limit={limit}")

    errors, businesses = [], []
    try:
        if OUTSCRAPER_KEY:
            businesses = asyncio.run(_outscraper(q, loc, limit))
        elif PLACES_KEY:
            businesses = asyncio.run(_places(q, loc, limit))
        else:
            # Demo mode: return synthetic records so the graph can still run
            businesses = _demo_records(q, loc, 20)
            logger.warning("[scrape_maps] No API keys — using demo data")
    except Exception as e:
        errors.append(str(e))
        logger.error(f"[scrape_maps] {e}")

    # Deduplicate
    seen, unique = set(), []
    for b in businesses:
        key = (b["name"].lower().strip(), b["address"].lower()[:30])
        if key not in seen:
            seen.add(key)
            unique.append(b)

    logger.info(f"[scrape_maps] {len(unique)} unique records")
    return {**state, "raw_businesses": unique, "scrape_errors": errors}


def _demo_records(btype: str, location: str, n: int) -> list[dict]:
    """Synthetic data for demo / testing without API keys."""
    import random
    companies = [
        ("Sunrise Services", "owner@sunriseservices.com", 4.8, 142),
        ("Metro Pro Solutions", "info@metropro.com", 4.5, 89),
        ("City Best Group", "contact@citybest.com", 4.2, 55),
        ("Valley Experts LLC", "mike@valleyexperts.com", 4.7, 203),
        ("Premier Local Co", "premier@local.com", 3.9, 31),
        ("Capital Works Inc", "ceo@capitalworks.com", 4.6, 178),
        ("Downtown Specialists", "hello@downtown.com", 4.1, 67),
        ("Neighborhood Pros", "owner@nbhpros.com", 4.9, 312),
        ("Regional Masters", "info@regionalmasters.com", 4.3, 44),
        ("Apex Local Services", "apex@services.com", 4.0, 22),
    ]
    records = []
    for i in range(n):
        name, email, rating, reviews = companies[i % len(companies)]
        name = f"{name} {i+1}" if i >= len(companies) else name
        records.append({
            "name": f"{btype.title()} — {name}",
            "address": f"{100+i} Main St, {location}",
            "phone": f"+1-555-{100+i:04d}",
            "website": f"https://www.{name.lower().replace(' ', '')}.com",
            "rating": rating,
            "review_count": reviews,
            "latitude": 40.7 + random.uniform(-0.1, 0.1),
            "longitude": -74.0 + random.uniform(-0.1, 0.1),
            "category": btype,
            "source": "demo",
            "emails": [email],
            "primary_email": email,
            "owner_name": "",
            "owner_position": "",
            "email_valid": True,
            "email_verified": True,
            "email_catchall": False,
            "email_status": "valid",
            "score": 0,
        })
    return records