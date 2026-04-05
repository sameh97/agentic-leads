"""
LangGraph Pipeline
==================
Graph topology (with retry loops):

  [parse_query]
       │
  [scrape_maps] ◄──────────────────────┐
       │                               │
       ├─ no results & retries left ───┘ (increment_retry → scrape_maps)
       ├─ no results & exhausted ──────► [fail]
       └─ ok ──────────────────────────► [enrich_websites]
                                               │
                              ┌────────────────┘
                              │
                       [verify_emails] ◄──── retry in-place
                              │
                       [score_leads]
                              │
                          [deliver]
                              │
                            END
"""

from langgraph.graph import StateGraph, END

from app.agents.state import LeadState
from app.nodes.query_parser   import parse_query_node
from app.nodes.maps_scraper   import scrape_maps_node
from app.nodes.enricher       import enrich_websites_node
from app.nodes.email_verifier import verify_emails_node
from app.nodes.lead_scorer    import score_leads_node
from app.nodes.delivery       import deliver_leads_node


# ── Routing functions ─────────────────────────────────────────────────────────

def route_after_scrape(state: LeadState) -> str:
    has_results = bool(state.get("raw_businesses"))
    retries_left = state["retry_count"] < state["max_retries"]

    if has_results:
        return "enrich"
    if retries_left:
        return "retry"
    return "fail"


def route_after_enrich(state: LeadState) -> str:
    has_results = bool(state.get("enriched_leads"))
    retries_left = state["retry_count"] < state["max_retries"]

    if has_results:
        return "verify"
    if retries_left:
        return "retry_enrich"
    return "fail"


def route_after_verify(state: LeadState) -> str:
    usable = [l for l in state.get("verified_leads", []) if l.get("email_valid")]
    if usable:
        return "score"
    retries_left = state["retry_count"] < state["max_retries"]
    if retries_left:
        return "retry_verify"
    return "score"   # score whatever we have, even if empty


# ── Helper nodes ──────────────────────────────────────────────────────────────

def increment_retry(state: LeadState) -> LeadState:
    return {**state, "retry_count": state["retry_count"] + 1}


def fail_node(state: LeadState) -> LeadState:
    return {
        **state,
        "status": "failed",
        "error_message": (
            f"Pipeline failed after {state['retry_count']} retries. "
            "Check API keys and try a different query."
        ),
    }


# ── Graph builder ─────────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    g = StateGraph(LeadState)

    # Register all nodes
    g.add_node("parse_query",      parse_query_node)
    g.add_node("scrape_maps",      scrape_maps_node)
    g.add_node("enrich_websites",  enrich_websites_node)
    g.add_node("verify_emails",    verify_emails_node)
    g.add_node("score_leads",      score_leads_node)
    g.add_node("deliver",          deliver_leads_node)
    g.add_node("increment_retry",  increment_retry)
    g.add_node("fail",             fail_node)

    # Entry point
    g.set_entry_point("parse_query")

    # Fixed edges
    g.add_edge("parse_query", "scrape_maps")

    # Scrape → conditional
    g.add_conditional_edges(
        "scrape_maps",
        route_after_scrape,
        {"enrich": "enrich_websites", "retry": "increment_retry", "fail": "fail"},
    )
    g.add_edge("increment_retry", "scrape_maps")   # loop back to scrape

    # Enrich → conditional
    g.add_conditional_edges(
        "enrich_websites",
        route_after_enrich,
        {"verify": "verify_emails", "retry_enrich": "enrich_websites", "fail": "fail"},
    )

    # Verify → conditional
    g.add_conditional_edges(
        "verify_emails",
        route_after_verify,
        {"score": "score_leads", "retry_verify": "verify_emails"},
    )

    # Final linear chain
    g.add_edge("score_leads", "deliver")
    g.add_edge("deliver", END)
    g.add_edge("fail", END)

    return g.compile()


# Singleton — import this everywhere
lead_graph = build_graph()