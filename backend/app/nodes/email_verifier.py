import os
import re
import logging
import asyncio
import time
import dns.resolver
import httpx
from app.agents.state import LeadState

logger = logging.getLogger(__name__)

# --- Configuration ---
RAPIDAPI_KEY  = os.getenv("RAPIDAPI_KEY", "")
RAPIDAPI_HOST = "verify-email-pro.p.rapidapi.com"
EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")

# --- Rate Limiting Globals ---
# Ensures only one task accesses the API at a time and maintains a 1s gap
_api_lock = asyncio.Lock()
_last_call_time = 0.0

# ── Layer 1: syntax ───────────────────────────────────────────────────────────

def _syntax_ok(email: str) -> bool:
    return bool(EMAIL_RE.match(email.strip()))


# ── Layer 2: MX record ────────────────────────────────────────────────────────

async def _has_mx(domain: str) -> bool:
    try:
        loop = asyncio.get_event_loop()
        recs = await loop.run_in_executor(
            None, lambda: dns.resolver.resolve(domain, "MX")
        )
        return len(recs) > 0
    except Exception:
        return False


# ── Layer 3: Verify Email Pro (Rate Limited) ──────────────────────────────────

async def _verify_email_pro(email: str) -> dict:
    global _last_call_time
    
    if not RAPIDAPI_KEY:
        return {}

    # Acquire lock to queue up requests sequentially
    async with _api_lock:
        # Calculate how long to wait to respect the 1 req/sec limit
        now = time.monotonic()
        elapsed = now - _last_call_time
        wait_needed = 1.0 - elapsed
        
        if wait_needed > 0:
            await asyncio.sleep(wait_needed)

        headers = {
            "X-RapidAPI-Key":  RAPIDAPI_KEY,
            "X-RapidAPI-Host": RAPIDAPI_HOST,
        }

        urls = [
            "https://verify-email-pro.p.rapidapi.com/check",
            "https://verify-email-pro.p.rapidapi.com/",
        ]

        # Record the time right before we initiate the network call
        _last_call_time = time.monotonic()

        async with httpx.AsyncClient(timeout=15) as c:
            for url in urls:
                try:
                    r = await c.get(url, params={"email": email}, headers=headers)
                    if r.status_code == 200:
                        data = r.json()
                        logger.debug(f"[verifier] raw response: {data}")
                        return data
                    elif r.status_code == 404:
                        continue
                    else:
                        logger.warning(f"[verifier] HTTP {r.status_code} for {email}: {r.text[:200]}")
                        return {}
                except Exception as e:
                    logger.warning(f"[verifier] Request error for {email}: {e}")
                    return {}

    return {}


def _parse_result(data: dict) -> dict:
    """Parse exact Verify Email Pro response schema."""
    if not data:
        return {
            "email_valid":     False,
            "email_verified": False,
            "email_catchall": False,
            "email_status":   "unknown",
            "do_not_mail":    False,
            "deliverability": 0,
        }

    email_valid = bool(data.get("email_valid",  False))
    catch_all   = bool(data.get("catch_all",    False))
    disposable  = bool(data.get("disposable",   False))
    smtp_valid  = bool(data.get("smtp_valid",   False))
    domain_ok   = bool(data.get("domain_valid", True))
    dns_ok      = bool(data.get("dns_valid",    True))
    status      = str(data.get("status", "unknown")).lower()
    score       = int(data.get("deliverability", 0))

    # Strict "verified": smtp confirmed + not catch-all + not disposable
    verified = email_valid and smtp_valid and not catch_all and not disposable

    do_not_mail = (
        disposable or
        not domain_ok or
        not dns_ok or
        status in ("invalid", "spam_trap", "abuse")
    )

    if disposable:
        final_status = "disposable"
    elif catch_all:
        final_status = "catch-all"
    elif email_valid:
        final_status = "valid"
    else:
        final_status = status

    return {
        "email_valid":    email_valid or catch_all,
        "email_verified": verified,
        "email_catchall": catch_all,
        "email_status":   final_status,
        "do_not_mail":    do_not_mail,
        "deliverability": score,
    }


# ── Per-lead orchestration ────────────────────────────────────────────────────

async def _verify_one(lead: dict) -> dict:
    email = lead.get("primary_email", "")

    # Demo records skip API call
    if lead.get("source") == "demo" and lead.get("email_verified"):
        return lead

    if not email:
        return {**lead, "email_valid": False, "email_verified": False,
                "email_catchall": False, "email_status": "no_email",
                "do_not_mail": False, "deliverability": 0}

    # Layer 1: syntax (Instant)
    if not _syntax_ok(email):
        return {**lead, "email_valid": False, "email_verified": False,
                "email_catchall": False, "email_status": "bad_syntax",
                "do_not_mail": False, "deliverability": 0}

    # Layer 2: MX record (Fast)
    domain = email.split("@")[1]
    if not await _has_mx(domain):
        return {**lead, "email_valid": False, "email_verified": False,
                "email_catchall": False, "email_status": "no_mx",
                "do_not_mail": False, "deliverability": 0}

    # Layer 3: Verify Email Pro (Throttled to 1 req/sec)
    raw    = await _verify_email_pro(email)
    result = _parse_result(raw)

    return {**lead, **result}


async def _run_all(leads: list[dict]) -> tuple[list[dict], list[str]]:
    # Semaphore is still useful to prevent over-saturating local DNS/CPU resources
    sem    = asyncio.Semaphore(10)
    errors: list[str] = []

    async def safe(lead: dict) -> dict:
        async with sem:
            try:
                return await _verify_one(lead)
            except Exception as e:
                errors.append(f"{lead.get('name','?')}: {e}")
                return {**lead, "email_valid": False, "email_status": "error"}

    # All leads start Layer 1/2 in parallel, but will queue up for Layer 3
    results = await asyncio.gather(*[safe(l) for l in leads])
    return list(results), errors


# ── Node entry point ──────────────────────────────────────────────────────────

def verify_emails_node(state: LeadState) -> LeadState:
    leads = state.get("enriched_leads", [])
    logger.info(f"[verifier] Verifying {len(leads)} emails via Verify Email Pro")

    # asyncio.run is used here assuming this is a synchronous entry point
    verified, errors = asyncio.run(_run_all(leads))
    
    safe_leads = [l for l in verified if not l.get("do_not_mail")]

    v = sum(1 for l in safe_leads if l.get("email_verified"))
    c = sum(1 for l in safe_leads if l.get("email_catchall"))
    logger.info(f"[verifier] {v} verified · {c} catch-all · {len(safe_leads)} total safe")

    return {**state, "verified_leads": safe_leads, "verification_errors": errors}