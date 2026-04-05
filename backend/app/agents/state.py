"""Shared LangGraph state — the single source of truth flowing through every node."""
from typing import Annotated
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class LeadState(TypedDict):
    # Trace
    messages: Annotated[list[BaseMessage], add_messages]

    # ── Input ────────────────────────────────────────────────
    raw_query:        str

    # ── Parsed intent ────────────────────────────────────────
    business_type:    str
    location:         str
    radius_km:        float
    enrichment_reqs:  list[str]
    max_results:      int

    # ── Scrape ───────────────────────────────────────────────
    raw_businesses:   list[dict]
    scrape_errors:    list[str]

    # ── Enrichment ───────────────────────────────────────────
    enriched_leads:   list[dict]
    enrichment_errors: list[str]

    # ── Verification ─────────────────────────────────────────
    verified_leads:    list[dict]
    verification_errors: list[str]

    # ── Scored + delivery ────────────────────────────────────
    scored_leads:     list[dict]
    final_csv_path:   str
    final_xlsx_path:  str

    # ── Control ──────────────────────────────────────────────
    retry_count:      int
    max_retries:      int
    status:           str   # queued | running | done | failed
    error_message:    str