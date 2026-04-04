"""
Node 1: Query Parser
====================
Uses an LLM to convert a natural-language query into structured search parameters.
Example:
  "Find all plumbing businesses in the tri-state area with verified owner emails"
  → { business_type: "plumber", location: "New York, NJ, CT", radius_km: 50, ... }
"""

import json
import logging
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.graph import LeadState

logger = logging.getLogger(__name__)

PARSE_SYSTEM_PROMPT = """
You are a lead generation query parser. Extract structured search parameters from the user's query.

Return ONLY a valid JSON object with these exact keys:
{
  "business_type": "<primary business category, singular, e.g. 'plumber'>",
  "location": "<city, state or region as a Google Maps search string>",
  "radius_km": <search radius in kilometers, default 25>,
  "enrichment_reqs": ["email", "phone", "owner_name"],
  "max_results": <integer, default 100, max 500>,
  "min_rating": <float 0-5, default 0, use 0 if not specified>
}

Rules:
- business_type: use common Google Maps category terms
- location: be specific enough for Google Maps (e.g. "New York, NY" not "tri-state area")
  For multi-region queries, use the primary metro center and increase radius_km
- enrichment_reqs: always include "email"; add "phone" and "owner_name" if mentioned
- If user asks for "verified", add "email_verified": true to enrichment_reqs
- Never include explanation, only the JSON object
"""


def parse_query_node(state: LeadState) -> LeadState:
    """LLM-powered NL → structured params."""
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

    try:
        response = llm.invoke([
            SystemMessage(content=PARSE_SYSTEM_PROMPT),
            HumanMessage(content=state["raw_query"]),
        ])

        parsed = json.loads(response.content)

        logger.info(f"[parse_query] Parsed intent: {parsed}")

        return {
            **state,
            "business_type":   parsed.get("business_type", "business"),
            "location":        parsed.get("location", state["raw_query"]),
            "radius_km":       float(parsed.get("radius_km", 25)),
            "enrichment_reqs": parsed.get("enrichment_reqs", ["email"]),
            "status":          "running",
            "retry_count":     0,
            "max_retries":     state.get("max_retries", 3),
            "messages":        state.get("messages", []) + [
                HumanMessage(content=f"Parsed query: {json.dumps(parsed, indent=2)}")
            ],
        }

    except json.JSONDecodeError as e:
        logger.warning(f"[parse_query] JSON parse failed, using fallback: {e}")
        # Graceful fallback — treat entire query as location+business
        words = state["raw_query"].lower().split()
        return {
            **state,
            "business_type":   "business",
            "location":        state["raw_query"],
            "radius_km":       25.0,
            "enrichment_reqs": ["email"],
            "status":          "running",
            "retry_count":     0,
            "max_retries":     state.get("max_retries", 3),
        }