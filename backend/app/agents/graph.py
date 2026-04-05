"""
Prompt-to-Leads: LangGraph Agent Pipeline
==========================================
Graph flow:
  parse_query → scrape_maps → enrich_websites → verify_emails → score_leads → deliver
  Each node can loop back on failure (agentic retry pattern).
"""

from typing import Annotated, Any
from typing_extensions import TypedDict

from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage

from app.nodes.query_parser   import parse_query_node
from app.nodes.maps_scraper   import scrape_maps_node
from app.nodes.enricher       import enrich_websites_node
from app.nodes.email_verifier import verify_emails_node
from app.nodes.lead_scorer    import score_leads_node
from app.nodes.delivery       import deliver_leads_node


# ── Shared state that flows through every node ────────────────────────────────

class LeadState(TypedDict):
    # Conversation / trace
    messages: Annotated[list[BaseMessage], add_messages]

    # Input
    raw_query:       str          # "Find plumbers in NYC with owner emails"

    # Parsed intent
    business_type:   str          # "plumber"
    location:        str          # "New York, NY"
    radius_km:       float        # 25.0
    enrichment_reqs: list[str]    # ["email", "phone", "owner_name"]

    # Scrape results
    raw_businesses:  list[dict]   # raw Google Maps records
    scrape_errors:   list[str]

    # Enriched results
    enriched_leads:  list[dict]   # records with website emails added
    enrichment_errors: list[str]

    # Verified results
    verified_leads:  list[dict]   # records with verification status
    verification_errors: list[str]

    # Scored + final
    scored_leads:    list[dict]   # sorted by score desc
    final_csv_path:  str          # path to output file

    # Control
    retry_count:     int
    max_retries:     int
    status:          str          # "running" | "done" | "failed"
    error_message:   str


# ── Conditional routing functions ─────────────────────────────────────────────

def route_after_scrape(state: LeadState) -> str:
    """Retry scrape or continue to enrichment."""
    if not state.get("raw_businesses") and state["retry_count"] < state["max_retries"]:
        return "retry_scrape"
    if not state.get("raw_businesses"):
        return "fail"
    return "enrich"


def route_after_enrich(state: LeadState) -> str:
    """Continue even with partial enrichment; fail only if nothing enriched."""
    enriched = state.get("enriched_leads", [])
    if not enriched and state["retry_count"] < state["max_retries"]:
        return "retry_enrich"
    if not enriched:
        return "fail"
    return "verify"


def route_after_verify(state: LeadState) -> str:
    verified = [l for l in state.get("verified_leads", []) if l.get("email_valid")]
    if not verified and state["retry_count"] < state["max_retries"]:
        return "retry_verify"
    return "score"   # always score whatever we have


def increment_retry(state: LeadState) -> LeadState:
    return {**state, "retry_count": state["retry_count"] + 1}


def fail_node(state: LeadState) -> LeadState:
    return {**state, "status": "failed",
            "error_message": "Pipeline exhausted retries with no usable leads."}


# ── Build the graph ───────────────────────────────────────────────────────────

def build_lead_graph() -> StateGraph:
    graph = StateGraph(LeadState)

    # Register nodes
    graph.add_node("parse_query",    parse_query_node)
    graph.add_node("scrape_maps",    scrape_maps_node)
    graph.add_node("enrich_websites",enrich_websites_node)
    graph.add_node("verify_emails",  verify_emails_node)
    graph.add_node("score_leads",    score_leads_node)
    graph.add_node("deliver",        deliver_leads_node)
    graph.add_node("increment_retry",increment_retry)
    graph.add_node("fail",           fail_node)

    # Entry
    graph.set_entry_point("parse_query")

    # Linear happy path
    graph.add_edge("parse_query", "scrape_maps")

    # Conditional after scrape
    graph.add_conditional_edges(
        "scrape_maps",
        route_after_scrape,
        {
            "enrich":       "enrich_websites",
            "retry_scrape": "increment_retry",
            "fail":         "fail",
        },
    )
    graph.add_edge("increment_retry", "scrape_maps")  # loop back

    # Conditional after enrich
    graph.add_conditional_edges(
        "enrich_websites",
        route_after_enrich,
        {
            "verify":       "verify_emails",
            "retry_enrich": "enrich_websites",  # retry in-place
            "fail":         "fail",
        },
    )

    # Conditional after verify
    graph.add_conditional_edges(
        "verify_emails",
        route_after_verify,
        {
            "score":        "score_leads",
            "retry_verify": "verify_emails",
        },
    )

    graph.add_edge("score_leads", "deliver")
    graph.add_edge("deliver",     END)
    graph.add_edge("fail",        END)

    return graph.compile()


# Singleton for import
lead_graph = build_lead_graph()