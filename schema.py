"""
schema.py
---------
Single source of truth for the structured profile shape. Both the AI
synthesis step (which must produce JSON matching this) and the report
renderer (which reads it) import from here, so the two never drift apart.
"""

NOT_AVAILABLE = "Not publicly available"

PROFILE_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "full_name": {"type": "string"},
        "executive_summary": {
            "type": "string",
            "description": "2-4 sentence high-level summary of who this person is and why they're notable.",
        },
        "basic_details": {
            "type": "object",
            "properties": {
                "full_name": {"type": "string"},
                "age_or_dob": {"type": "string"},
                "occupation": {"type": "string"},
                "industry": {"type": "string"},
                "current_city": {"type": "string"},
                "current_country": {"type": "string"},
            },
            "required": [
                "full_name",
                "age_or_dob",
                "occupation",
                "industry",
                "current_city",
                "current_country",
            ],
        },
        "biography": {
            "type": "string",
            "description": "A few paragraphs covering background, education, and rise to prominence.",
        },
        "career_timeline": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "period": {"type": "string"},
                    "role_or_event": {"type": "string"},
                },
                "required": ["period", "role_or_event"],
            },
        },
        "interests": {"type": "array", "items": {"type": "string"}},
        "network": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Notable professional or personal connections (colleagues, co-founders, mentors, family in the same industry, etc.)",
        },
        "recent_activity": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "date": {"type": "string"},
                    "headline": {"type": "string"},
                },
                "required": ["date", "headline"],
            },
        },
        "references": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "url": {"type": "string"},
                },
                "required": ["title", "url"],
            },
        },
    },
    "required": [
        "full_name",
        "executive_summary",
        "basic_details",
        "biography",
        "career_timeline",
        "interests",
        "network",
        "recent_activity",
        "references",
    ],
}

REQUIRED_TOP_LEVEL_FIELDS = list(PROFILE_JSON_SCHEMA["required"])
