"""
Node 1 — Query Parser
======================
Uses init_chat_model (LangChain's unified model interface).

Set LLM_MODEL in your .env using "provider:model" format.
For Ollama models that contain colons in the name (e.g. qwen2.5:3b),
use LLM_PROVIDER + LLM_MODEL separately:

  # Simple providers (no colon in model name):
  LLM_MODEL=openai:gpt-4o-mini
  LLM_MODEL=groq:llama-3.1-8b-instant
  LLM_MODEL=anthropic:claude-haiku-3-5

  # Ollama (model names often contain colons like qwen2.5:3b):
  LLM_PROVIDER=ollama
  LLM_MODEL=qwen2.5:3b          ← just the model, no provider prefix
  LLM_MODEL=phi4-mini
  LLM_MODEL=gemma2:2b
"""

import os
import json
import re
import logging

from langchain.chat_models import init_chat_model
from langchain_core.messages import SystemMessage, HumanMessage

from app.agents.state import LeadState

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
# LLM_PROVIDER: explicit provider override (required for Ollama)
# LLM_MODEL:    model name — with or without "provider:" prefix
#
# Resolution order:
#   1. If LLM_PROVIDER is set → use it as model_provider, LLM_MODEL as model
#   2. Else if LLM_MODEL contains ":" and first part is a known provider → split it
#   3. Else pass LLM_MODEL as-is and let init_chat_model infer the provider

_LLM_PROVIDER = os.getenv("LLM_PROVIDER", "").strip().lower()
_LLM_MODEL_ENV = os.getenv("LLM_MODEL", "openai:gpt-4o-mini").strip()
# When running in Docker, Ollama is on the HOST machine not localhost.
# docker-compose sets OLLAMA_BASE_URL=http://host.docker.internal:11434
_OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
_KNOWN_PROVIDERS = {
    "openai", "anthropic", "google_genai", "google_vertexai",
    "groq", "mistralai", "cohere", "fireworks", "together",
    "bedrock", "bedrock_converse", "azure_openai", "nvidia",
    "perplexity", "xai", "deepseek",
    # NOTE: "ollama" is NOT in this set because ollama model names
    # themselves contain ":" (e.g. qwen2.5:3b) which breaks the split.
}


def _resolve_model_and_provider() -> tuple[str, str | None]:
    """
    Returns (model_name, model_provider_or_None) for init_chat_model.
    Handles the Ollama colon-in-model-name edge case.
    """
    # Explicit provider env var always wins (needed for Ollama)
    if _LLM_PROVIDER:
        return _LLM_MODEL_ENV, _LLM_PROVIDER

    # Try splitting "provider:model" — but only if first segment is a known provider
    parts = _LLM_MODEL_ENV.split(":", 1)
    if len(parts) == 2 and parts[0].lower() in _KNOWN_PROVIDERS:
        return parts[1], parts[0].lower()

    # Pass full string to init_chat_model and let it infer (works for most cases)
    return _LLM_MODEL_ENV, None


_MODEL_NAME, _MODEL_PROVIDER = _resolve_model_and_provider()

logger.info(f"[parse_query] init_chat_model → model={_MODEL_NAME!r}  provider={_MODEL_PROVIDER!r}")

# Extra kwargs for specific providers
_extra_kwargs: dict = {}
if _MODEL_PROVIDER == "ollama":
    # langchain-ollama expects base_url without the /v1 suffix
    _extra_kwargs["base_url"] = _OLLAMA_BASE_URL

# Build the LLM instance once at module load — reused for every request
_llm = init_chat_model(
    _MODEL_NAME,
    model_provider=_MODEL_PROVIDER,
    configurable_fields=("model", "model_provider"),
    temperature=0,
    **_extra_kwargs,
)

# ── Prompt ────────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are a lead generation query parser.
Convert the user query into a JSON object with EXACTLY these keys:

{
  "business_type": "<Google Maps search term, e.g. 'plumber', 'HVAC company', 'dentist'>",
  "location":      "<city + state or country for Google Maps, e.g. 'Austin, TX'>",
  "radius_km":     <number, default 25, increase for 'area' or 'region' queries>,
  "enrichment_reqs": ["email"],
  "max_results":   <integer 20-500, default 100>
}

Rules:
- For tri-state / metro area queries: use the largest city + radius_km 80-100
- Always include "email" in enrichment_reqs
- Respond with ONLY valid JSON — no markdown fences, no explanation
"""

# ── Rule-based fallback ───────────────────────────────────────────────────────
_US_STATES = {
    "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA",
    "KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ",
    "NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT",
    "VA","WA","WV","WI","WY","DC",
}
_BUSINESS_KWS = [
    "plumber","hvac","dentist","doctor","lawyer","restaurant","hotel","gym",
    "electrician","contractor","roofer","painter","cleaner","accountant",
    "real estate","salon","spa","mechanic","auto","store","shop","agency",
]

def _rule_based_parse(query: str) -> dict:
    """Offline fallback — no LLM required."""
    q             = query.lower()
    business_type = next((kw for kw in _BUSINESS_KWS if kw in q), "business")
    location      = query

    m = re.search(r"\bin\s+([A-Za-z\s,]+?)(?:\s+with|\s+near|\s+that|$)", query, re.I)
    if m:
        location = m.group(1).strip()

    words = query.upper().split()
    for i, word in enumerate(words):
        if word.strip(",.") in _US_STATES and i > 0:
            location = f"{words[i-1].strip(',. ').title()}, {word.strip(',.')}"
            break

    logger.info(f"[parse_query] rule-based → type='{business_type}' location='{location}'")
    return {
        "business_type":   business_type,
        "location":        location,
        "radius_km":       25,
        "enrichment_reqs": ["email"],
        "max_results":     100,
    }


# ── Node ──────────────────────────────────────────────────────────────────────
def parse_query_node(state: LeadState) -> LeadState:
    query = state["raw_query"]
    logger.info(f"[parse_query] model={_MODEL_NAME!r} provider={_MODEL_PROVIDER!r} query='{query}'")

    parsed: dict | None = None

    try:
        response = _llm.invoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=query),
        ])

        content = response.content.strip()
        # Strip markdown fences some local models add despite instructions
        content = re.sub(r"^```(?:json)?\s*", "", content, flags=re.MULTILINE)
        content = re.sub(r"\s*```\s*$",        "", content, flags=re.MULTILINE)

        parsed = json.loads(content)
        logger.info(f"[parse_query] LLM result → {parsed}")

    except Exception as e:
        logger.warning(f"[parse_query] LLM failed ({e}) — rule-based fallback")
        parsed = _rule_based_parse(query)

    return {
        **state,
        "business_type":   str(parsed.get("business_type", "business")),
        "location":        str(parsed.get("location", query)),
        "radius_km":       float(parsed.get("radius_km", 25)),
        "enrichment_reqs": list(parsed.get("enrichment_reqs", ["email"])),
        "max_results":     int(parsed.get("max_results", 100)),
        "retry_count":     0,
        "max_retries":     state.get("max_retries", 3),
        "status":          "running",
    }