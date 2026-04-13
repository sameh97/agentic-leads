"""
Node 4 — Email Verifier
========================
3-layer verification:
  1. Syntax regex (free, local)
  2. DNS MX record (free, local)
  3. RapidAPI "Email Verifier" (rapidapi.com/mr_admin/api/email-verifier) — free tier
"""
import os, re, logging, asyncio
import dns.resolver
import httpx
from app.agents.state import LeadState

logger = logging.getLogger(__name__)

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "")
EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")


def _syntax_ok(email: str) -> bool:
    return bool(EMAIL_RE.match(email.strip()))


async def _has_mx(domain: str) -> bool:
    try:
        loop = asyncio.get_event_loop()
        recs = await loop.run_in_executor(None, lambda: dns.resolver.resolve(domain, "MX"))
        return len(recs) > 0
    except Exception:
        return False


async def _rapidapi_verify(email: str) -> dict:
    """
    RapidAPI Email Verifier by mr_admin
    https://rapidapi.com/mr_admin/api/email-verifier
    Free tier available.
    """
    if not RAPIDAPI_KEY:
        return {"status": "unknown"}
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(
                "https://email-verifier.p.rapidapi.com/verify",
                params={"email": email},
                headers={
                    "X-RapidAPI-Key":  RAPIDAPI_KEY,
                    "X-RapidAPI-Host": "email-verifier.p.rapidapi.com",
                },
            )
            if r.status_code == 200:
                return r.json()
    except Exception as e:
        logger.warning(f"[verifier] RapidAPI verify failed for {email}: {e}")
    return {"status": "unknown"}


async def _verify_one(lead: dict) -> dict:
    email = lead.get("primary_email", "")

    # Demo records skip verification
    if lead.get("source") == "demo" and lead.get("email_verified"):
        return lead

    if not email:
        return {**lead, "email_valid": False, "email_status": "no_email"}

    # Layer 1: syntax
    if not _syntax_ok(email):
        return {**lead, "email_valid": False, "email_status": "bad_syntax"}

    # Layer 2: MX record
    domain = email.split("@")[1]
    if not await _has_mx(domain):
        return {**lead, "email_valid": False, "email_status": "no_mx"}

    # Layer 3: RapidAPI SMTP verification
    result  = await _rapidapi_verify(email)

    # Normalize response — different APIs use different field names
    status   = (result.get("status") or result.get("result") or "unknown").lower()
    valid    = status in ("valid", "deliverable")
    catchall = status in ("catch-all", "catchall", "catch_all", "risky")
    dnm      = status in ("invalid", "undeliverable", "spam_trap", "abuse", "disposable")

    return {
        **lead,
        "email_valid":    valid or catchall,
        "email_verified": valid,
        "email_catchall": catchall,
        "email_status":   status,
        "do_not_mail":    dnm,
    }


async def _run_all(leads: list[dict]) -> tuple[list[dict], list[str]]:
    sem = asyncio.Semaphore(20)
    errors: list[str] = []

    async def safe(l: dict) -> dict:
        async with sem:
            try:
                return await _verify_one(l)
            except Exception as e:
                errors.append(f"{l.get('name','?')}: {e}")
                return {**l, "email_valid": False, "email_status": "error"}

    results = await asyncio.gather(*[safe(l) for l in leads])
    return list(results), errors


def verify_emails_node(state: LeadState) -> LeadState:
    leads = state.get("enriched_leads", [])
    logger.info(f"[verifier] {len(leads)} emails to verify")

    verified, errors = asyncio.run(_run_all(leads))
    safe_leads = [l for l in verified if not l.get("do_not_mail")]

    valid = sum(1 for l in safe_leads if l.get("email_valid"))
    logger.info(f"[verifier] {valid}/{len(safe_leads)} valid")
    return {**state, "verified_leads": safe_leads, "verification_errors": errors}