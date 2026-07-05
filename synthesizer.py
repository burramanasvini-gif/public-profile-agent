"""
synthesizer.py
---------------
Takes the raw scraped ResearchBundle and asks an LLM (Claude, via the
Anthropic API) to synthesize it into a clean, structured profile that
matches schema.PROFILE_JSON_SCHEMA.

Key design choices:
- The model is instructed to ONLY use facts present in the supplied source
  text (grounding), and to explicitly write "Not publicly available" for
  any field it cannot support from the sources — never guess or invent.
- We use Claude's tool-calling (forced tool_choice) to get back strict,
  parseable JSON instead of parsing free-form prose.
- If no ANTHROPIC_API_KEY is configured, a lightweight offline fallback
  produces a best-effort profile directly from the scraped text so the
  pipeline still runs end-to-end (useful for demos without an API key).
"""

from __future__ import annotations

import json
import logging
import os

from .schema import NOT_AVAILABLE, PROFILE_JSON_SCHEMA, REQUIRED_TOP_LEVEL_FIELDS
from .scraper import ResearchBundle

logger = logging.getLogger("profile_agent.synthesizer")

SYSTEM_PROMPT = """You are a careful research analyst who builds structured public
profiles of named individuals STRICTLY from the source material you are given.

Rules you must follow exactly:
1. Use ONLY information present in the provided sources. Do not use outside
   knowledge, do not guess, and do not extrapolate beyond what the text supports.
2. For ANY field where the sources do not contain a clear answer, set that
   field's value to exactly: "Not publicly available" (for strings) or an
   empty array (for lists). Never fabricate a plausible-sounding value.
3. Keep the executive_summary and biography objective, neutral, and free of
   speculation or opinion.
4. career_timeline should be ordered chronologically (earliest first) and only
   include entries with a real, sourced period and event.
5. references must reflect the sources you actually drew from.
6. Return your answer ONLY by calling the `submit_profile` tool. Do not add
   any commentary outside the tool call.
"""

TOOL_DEFINITION = {
    "name": "submit_profile",
    "description": "Submit the final structured public profile for the requested person.",
    "input_schema": PROFILE_JSON_SCHEMA,
}


def _build_user_prompt(person_name: str, bundle: ResearchBundle) -> str:
    context = bundle.as_context_text()
    if not context.strip():
        context = "(No usable public sources were retrieved.)"
    return f"""Build a structured public profile for: {person_name}

Here are the publicly available sources retrieved via web search/scraping.
Each is labeled with its title and URL — cite these exact URLs in the
`references` field.

{context}

Now call the submit_profile tool with the completed profile for {person_name}.
Remember: any field not clearly supported by the sources above must be set to
"Not publicly available" (or an empty list, for list fields). Do not invent
information."""


def _empty_profile(person_name: str) -> dict:
    return {
        "full_name": person_name,
        "executive_summary": NOT_AVAILABLE,
        "basic_details": {
            "full_name": person_name,
            "age_or_dob": NOT_AVAILABLE,
            "occupation": NOT_AVAILABLE,
            "industry": NOT_AVAILABLE,
            "current_city": NOT_AVAILABLE,
            "current_country": NOT_AVAILABLE,
        },
        "biography": NOT_AVAILABLE,
        "career_timeline": [],
        "interests": [],
        "network": [],
        "recent_activity": [],
        "references": [],
    }


def _offline_fallback_profile(person_name: str, bundle: ResearchBundle) -> dict:
    """Used only when no ANTHROPIC_API_KEY is set. Produces a minimal but
    honest profile so the pipeline still completes end-to-end."""
    profile = _empty_profile(person_name)
    if bundle.sources:
        profile["executive_summary"] = (
            f"Automated summary unavailable without an AI model configured. "
            f"{len(bundle.sources)} public source(s) were retrieved for "
            f"{person_name}; see references below."
        )
        profile["biography"] = bundle.sources[0].text[:1500]
    profile["references"] = bundle.reference_list()
    return profile


def _validate_and_fill(profile: dict, person_name: str) -> dict:
    """Ensure every required field exists; fill sensible defaults if the
    model omitted something, so downstream rendering never KeyErrors."""
    base = _empty_profile(person_name)
    for key in REQUIRED_TOP_LEVEL_FIELDS:
        if key not in profile or profile[key] in (None, ""):
            profile[key] = base[key]
    for key in base["basic_details"]:
        profile.setdefault("basic_details", {})
        if key not in profile["basic_details"] or not profile["basic_details"][key]:
            profile["basic_details"][key] = NOT_AVAILABLE
    return profile


def synthesize_profile(person_name: str, bundle: ResearchBundle) -> dict:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        logger.warning(
            "ANTHROPIC_API_KEY not set — using offline fallback synthesis "
            "(profile quality will be limited)."
        )
        return _offline_fallback_profile(person_name, bundle)

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")

        response = client.messages.create(
            model=model,
            max_tokens=4000,
            system=SYSTEM_PROMPT,
            tools=[TOOL_DEFINITION],
            tool_choice={"type": "tool", "name": "submit_profile"},
            messages=[
                {
                    "role": "user",
                    "content": _build_user_prompt(person_name, bundle),
                }
            ],
        )

        for block in response.content:
            if block.type == "tool_use" and block.name == "submit_profile":
                profile = block.input
                return _validate_and_fill(profile, person_name)

        logger.error("Model response contained no tool_use block; falling back.")
        return _offline_fallback_profile(person_name, bundle)

    except Exception as exc:
        logger.error("AI synthesis failed (%s); using offline fallback.", exc)
        return _offline_fallback_profile(person_name, bundle)
