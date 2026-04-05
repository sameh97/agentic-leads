"""Node 1 — Query Parser: NL string → structured search parameters via LLM."""
import json
import logging
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from app.agents.state import LeadState

logger = logging.getLogger(__name__)

SYSTEM = """You are a lead generation query parser.
Convert the user's natural language query into a JSON object with EXACTLY these keys:

{
  "business_type": "<Google Maps search term, e.g. 'plumber', 'HVAC company', 'dentist'>",
  "location":      "<city + state or country, specific enough for Google Maps, e.g. 'Austin, TX'>",
  "radius_km":     <number, default 25, increase for 'area' or 'region' queries>,
  "enrichment_reqs": ["email"],
  "max_results":   <integer 20-500, default 100>
}

Rules:
- For tri-state / metro area queries: use the largest city + increase radius_km to 80-100
- Always include "email" in enrichment_reqs
- Respond with ONLY the JSON object, no markdown, no explanation
"""


def parse_query_node(state: LeadState) -> LeadState:
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    try:
        response = llm.invoke([
            SystemMessage(content=SYSTEM),
            HumanMessage(content=state["raw_query"]),
        ])
        parsed = json.loads(response.content.strip())
    except Exception as e:
        logger.warning(f"[parse_query] Parse failed ({e}), using fallback")
        parsed = {
            "business_type": "business",
            "location": state["raw_query"],
            "radius_km": 25,
            "enrichment_reqs": ["email"],
            "max_results": 100,
        }

    logger.info(f"[parse_query] {parsed}")
    return {
        **state,
        "business_type":   str(parsed.get("business_type", "business")),
        "location":        str(parsed.get("location", state["raw_query"])),
        "radius_km":       float(parsed.get("radius_km", 25)),
        "enrichment_reqs": list(parsed.get("enrichment_reqs", ["email"])),
        "max_results":     int(parsed.get("max_results", 100)),
        "retry_count":     0,
        "max_retries":     state.get("max_retries", 3),
        "status":          "running",
    }