"""
Node 4: Email Verifier
========================
Triple-layer verification:
  1. Syntax check (regex)
  2. MX record DNS check (domain can receive email)
  3. SMTP handshake via ZeroBounce API (or NeverBounce)
  
Only emails passing all 3 layers are marked email_valid=True.
Catch-all domains get a separate flag for special handling.
"""

import os
import re
import logging
import asyncio
import dns.resolver
import httpx

from app.agents.graph import LeadState

logger = logging.getLogger(__name__)

ZEROBOUNCE_API_KEY = os.getenv("ZEROBOUNCE_API_KEY", "")
NEVER_BOUNCE_API_KEY = os.getenv("NEVER_BOUNCE_API_KEY", "")

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")


def _check_syntax(email: str) -> bool:
    return bool(EMAIL_REGEX.match(email.strip()))


async def _check_mx_record(domain: str) -> bool:
    """Check if domain has MX records (can receive email)."""
    try:
        loop = asyncio.get_event_loop()
        records = await loop.run_in_executor(
            None, lambda: dns.resolver.resolve(domain, "MX")
        )
        return len(records) > 0
    except Exception:
        return False


async def _check_zerobounce(email: str) -> dict:
    """
    ZeroBounce API validation.
    Returns status: "valid" | "invalid" | "catch-all" | "unknown" | "do_not_mail"
    """
    if not ZEROBOUNCE_API_KEY:
        return {"status": "unknown", "sub_status": "no_api_key"}

    url = "https://api.zerobounce.net/v2/validate"
    params = {"api_key": ZEROBOUNCE_API_KEY, "email": email}

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, params=params)
            if resp.status_code == 200:
                return resp.json()
    except Exception as e:
        logger.warning(f"[zerobounce] {email}: {e}")

    return {"status": "unknown"}


async def _check_neverbounce(email: str) -> dict:
    """
    NeverBounce fallback if ZeroBounce unavailable.
    Returns result: "valid" | "invalid" | "catchall" | "unknown" | "disposable"
    """
    if not NEVER_BOUNCE_API_KEY:
        return {"result": "unknown"}

    url = "https://api.neverbounce.com/v4/single/check"
    params = {"api_key": NEVER_BOUNCE_API_KEY, "email": email}

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, params=params)
            if resp.status_code == 200:
                return resp.json()
    except Exception as e:
        logger.warning(f"[neverbounce] {email}: {e}")

    return {"result": "unknown"}


async def _verify_one(lead: dict) -> dict:
    email = lead.get("primary_email", "")
    if not email:
        return {**lead, "email_valid": False, "email_status": "no_email"}

    # Layer 1: syntax
    if not _check_syntax(email):
        return {**lead, "email_valid": False, "email_status": "invalid_syntax"}

    # Layer 2: MX record
    domain = email.split("@")[1]
    has_mx = await _check_mx_record(domain)
    if not has_mx:
        return {**lead, "email_valid": False, "email_status": "no_mx_record"}

    # Layer 3: SMTP / API
    zb_result = await _check_zerobounce(email)
    zb_status = zb_result.get("status", "unknown").lower()

    # If ZeroBounce unavailable, try NeverBounce
    if zb_status == "unknown" and not ZEROBOUNCE_API_KEY and NEVER_BOUNCE_API_KEY:
        nb_result = await _check_neverbounce(email)
        nb_status = nb_result.get("result", "unknown").lower()
        is_valid    = nb_status == "valid"
        is_catchall = nb_status == "catchall"
        final_status = nb_status
    else:
        is_valid    = zb_status == "valid"
        is_catchall = zb_status == "catch-all"
        final_status = zb_status

    return {
        **lead,
        "email_valid":    is_valid or is_catchall,  # include catch-all as usable
        "email_verified": is_valid,                  # strict valid only
        "email_catchall": is_catchall,
        "email_status":   final_status,
        "do_not_mail":    final_status in ("do_not_mail", "abuse", "disposable"),
    }


async def _verify_all(leads: list[dict], concurrency: int = 20) -> tuple[list[dict], list[str]]:
    semaphore = asyncio.Semaphore(concurrency)
    errors: list[str] = []

    async def verify_with_sem(lead: dict) -> dict:
        async with semaphore:
            try:
                return await _verify_one(lead)
            except Exception as e:
                errors.append(f"{lead.get('name', '?')}: {e}")
                return {**lead, "email_valid": False, "email_status": "error"}

    results = await asyncio.gather(*[verify_with_sem(l) for l in leads])
    return list(results), errors


def verify_emails_node(state: LeadState) -> LeadState:
    leads = state.get("enriched_leads", [])
    logger.info(f"[verify] Verifying {len(leads)} emails")

    verified, errors = asyncio.run(_verify_all(leads))

    valid_count = sum(1 for l in verified if l.get("email_valid"))
    strict_count = sum(1 for l in verified if l.get("email_verified"))
    logger.info(f"[verify] {strict_count} strict-valid, {valid_count} usable (incl. catch-all)")

    # Filter out do_not_mail
    safe = [l for l in verified if not l.get("do_not_mail", False)]

    return {
        **state,
        "verified_leads":        safe,
        "verification_errors":   errors,
    }