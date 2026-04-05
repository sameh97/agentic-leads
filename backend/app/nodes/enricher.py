"""
Node 3: Email Enricher
========================
Waterfall enrichment strategy:
  1. Scrape the business website for mailto: links and contact pages
  2. Hunter.io Domain Search API (primary enrichment provider)
  3. Apollo.io People Search (secondary, if Hunter fails)
  
Only charges external API credits when website scraping fails (cost efficiency).
"""

import os
import re
import logging
import asyncio
from urllib.parse import urljoin, urlparse
import httpx
from bs4 import BeautifulSoup

from app.agents.graph import LeadState

logger = logging.getLogger(__name__)

HUNTER_API_KEY = os.getenv("HUNTER_API_KEY", "")
APOLLO_API_KEY = os.getenv("APOLLO_API_KEY", "")

# Patterns to find emails in HTML
EMAIL_REGEX = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
)

# Roles that indicate a decision-maker (not generic info@)
DECISION_MAKER_PATTERNS = ["owner", "ceo", "founder", "manager", "director", "president"]
GENERIC_PREFIXES = {"info", "contact", "hello", "support", "admin", "noreply", "no-reply", "sales", "office"}


async def _scrape_website_emails(website: str) -> list[str]:
    """
    Scrape a business website for email addresses.
    Checks: homepage, /contact, /about pages.
    """
    if not website or not website.startswith("http"):
        website = f"https://{website}" if website else ""
    if not website:
        return []

    found_emails = set()
    pages_to_check = [website, urljoin(website, "/contact"), urljoin(website, "/about")]

    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; LeadBot/1.0; +https://yourapp.com/bot)"
    }

    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
        for url in pages_to_check:
            try:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200 and "text/html" in resp.headers.get("content-type", ""):
                    soup = BeautifulSoup(resp.text, "html.parser")
                    text = soup.get_text()
                    # Also check mailto: links
                    for a in soup.find_all("a", href=True):
                        if a["href"].startswith("mailto:"):
                            email = a["href"].replace("mailto:", "").split("?")[0].strip()
                            if email:
                                found_emails.add(email.lower())
                    # Regex scan
                    for match in EMAIL_REGEX.finditer(text):
                        found_emails.add(match.group().lower())
            except Exception:
                pass  # Page not found, timeout, etc — continue

    # Filter obvious junk
    cleaned = [
        e for e in found_emails
        if not any(e.endswith(x) for x in [".png", ".jpg", ".gif", ".css"])
        and "@" in e
    ]
    return cleaned


async def _hunter_domain_search(domain: str) -> list[dict]:
    """
    Hunter.io Domain Search: finds all emails associated with a domain.
    Returns list of {email, first_name, last_name, position, confidence}
    """
    if not HUNTER_API_KEY:
        return []

    url = "https://api.hunter.io/v2/domain-search"
    params = {"domain": domain, "api_key": HUNTER_API_KEY, "limit": 10}

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, params=params)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("data", {}).get("emails", [])
    except Exception as e:
        logger.warning(f"[hunter] Domain search failed for {domain}: {e}")

    return []


async def _apollo_people_search(company_name: str, domain: str) -> list[dict]:
    """
    Apollo.io People Search: finds decision-makers at a company.
    Secondary fallback when Hunter returns nothing.
    """
    if not APOLLO_API_KEY:
        return []

    url = "https://api.apollo.io/v1/mixed_people/search"
    payload = {
        "api_key":              APOLLO_API_KEY,
        "q_organization_name":  company_name,
        "organization_domains": [domain],
        "person_titles":        ["owner", "ceo", "founder", "president", "general manager"],
        "per_page":             5,
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                people = resp.json().get("people", [])
                return [
                    {
                        "email":      p.get("email", ""),
                        "first_name": p.get("first_name", ""),
                        "last_name":  p.get("last_name", ""),
                        "position":   p.get("title", ""),
                        "confidence": 70,
                    }
                    for p in people if p.get("email")
                ]
    except Exception as e:
        logger.warning(f"[apollo] Search failed for {company_name}: {e}")

    return []


def _score_email(email: str, position: str = "") -> int:
    """Score an email 0-100: higher = more likely to be a decision-maker."""
    score = 50
    prefix = email.split("@")[0].lower()

    if any(kw in prefix for kw in DECISION_MAKER_PATTERNS):
        score += 30
    if any(kw in position.lower() for kw in DECISION_MAKER_PATTERNS):
        score += 20
    if prefix in GENERIC_PREFIXES:
        score -= 30

    return max(0, min(100, score))


def _extract_domain(website: str) -> str:
    if not website:
        return ""
    if not website.startswith("http"):
        website = f"https://{website}"
    try:
        return urlparse(website).netloc.lstrip("www.")
    except Exception:
        return ""


async def _enrich_one(business: dict) -> dict:
    """Run the full waterfall for a single business."""
    website = business.get("website", "")
    domain  = _extract_domain(website)
    name    = business.get("name", "")

    emails_data: list[dict] = []
    owner_name = ""

    # Layer 1: website scraping (free)
    if website:
        raw_emails = await _scrape_website_emails(website)
        for e in raw_emails:
            emails_data.append({
                "email":      e,
                "position":   "",
                "first_name": "",
                "last_name":  "",
                "confidence": 60,
                "source":     "website_scrape",
            })

    # Layer 2: Hunter.io (paid, only if needed)
    if domain and not emails_data:
        hunter_results = await _hunter_domain_search(domain)
        for r in hunter_results:
            emails_data.append({
                "email":      r.get("value", ""),
                "position":   r.get("position", ""),
                "first_name": r.get("first_name", ""),
                "last_name":  r.get("last_name", ""),
                "confidence": r.get("confidence", 70),
                "source":     "hunter",
            })

    # Layer 3: Apollo (only if both above failed)
    if domain and not emails_data:
        apollo_results = await _apollo_people_search(name, domain)
        for r in apollo_results:
            emails_data.append({**r, "source": "apollo"})

    # Find best email (prefer decision-makers over generic)
    if emails_data:
        scored = sorted(
            emails_data,
            key=lambda e: _score_email(e["email"], e.get("position", "")),
            reverse=True,
        )
        best = scored[0]
        if best.get("first_name") and best.get("last_name"):
            owner_name = f"{best['first_name']} {best['last_name']}".strip()

        # Attach enriched data
        business = {
            **business,
            "emails":         [e["email"] for e in scored if e.get("email")],
            "primary_email":  best.get("email", ""),
            "owner_name":     owner_name,
            "owner_position": best.get("position", ""),
            "enriched":       True,
        }
    else:
        business = {**business, "enriched": False}

    return business


async def _enrich_all(businesses: list[dict], concurrency: int = 10) -> tuple[list[dict], list[str]]:
    """Enrich all businesses with rate-limited concurrency."""
    semaphore = asyncio.Semaphore(concurrency)
    errors: list[str] = []

    async def enrich_with_sem(b: dict) -> dict:
        async with semaphore:
            try:
                return await _enrich_one(b)
            except Exception as e:
                logger.warning(f"[enricher] Failed for {b.get('name')}: {e}")
                errors.append(f"{b.get('name', '?')}: {e}")
                return b

    tasks = [enrich_with_sem(b) for b in businesses]
    enriched = await asyncio.gather(*tasks)
    return list(enriched), errors


def enrich_websites_node(state: LeadState) -> LeadState:
    businesses = state.get("raw_businesses", [])
    logger.info(f"[enricher] Enriching {len(businesses)} businesses")

    enriched, errors = asyncio.run(_enrich_all(businesses))

    # Only keep records where we found at least one email
    with_email = [b for b in enriched if b.get("primary_email")]
    logger.info(f"[enricher] {len(with_email)}/{len(enriched)} records enriched with email")

    return {
        **state,
        "enriched_leads":    with_email,
        "enrichment_errors": errors,
    }