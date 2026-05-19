"""Anthropic-compatible JSON schemas for the 3 built-in agent tools."""

from typing import Any

KG_SEARCH: dict[str, Any] = {
    "name": "kg_search",
    "description": (
        "Search the tenant knowledge graph for entities matching a query. "
        "Returns up to top_k entities with their type and payload summary."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Natural-language search query.",
            },
            "top_k": {
                "type": "integer",
                "description": "Maximum number of results to return.",
                "default": 5,
                "minimum": 1,
                "maximum": 20,
            },
        },
        "required": ["query"],
    },
}

RENDER_HIGHLIGHT: dict[str, Any] = {
    "name": "render_highlight",
    "description": (
        "Emit a highlight rendering directive for a specific entity. "
        "The frontend will visually emphasise the entity on the current page."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "entity_id": {
                "type": "string",
                "description": "UUID of the entity to highlight.",
            },
            "reason": {
                "type": "string",
                "description": "Human-readable reason for highlighting (used in debug panel).",
            },
        },
        "required": ["entity_id", "reason"],
    },
}

LEAD_UPDATE_SCORE: dict[str, Any] = {
    "name": "lead_update_score",
    "description": (
        "Update the current visitor lead score by recording a scoring signal. "
        "Signals accumulate in-memory for the duration of the conversation."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "signal": {
                "type": "string",
                "description": "Signal name (e.g. 'asked_price', 'requested_visit', 'clicked_cta').",
            },
            "weight": {
                "type": "number",
                "description": "Signal weight in the range [0, 1].",
                "minimum": 0.0,
                "maximum": 1.0,
            },
        },
        "required": ["signal", "weight"],
    },
}

SPATIAL_NAVIGATE: dict[str, Any] = {
    "name": "spatial_navigate",
    "description": (
        "Navigate the 360° spatial viewer to a specific scene. "
        "Use when the visitor's message references a specific area of the property "
        "(e.g. master suite, pool, entrance). The viewer transitions smoothly to the scene."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "scene_id": {
                "type": "string",
                "description": (
                    "ID of the scene to navigate to. "
                    "Valid values: 'villa-entrance', 'master-suite', 'infinity-pool'."
                ),
                "enum": ["villa-entrance", "master-suite", "infinity-pool"],
            },
            "reason": {
                "type": "string",
                "description": "Why this scene is relevant to the visitor's current interest.",
            },
        },
        "required": ["scene_id", "reason"],
    },
}

ALL_TOOLS: list[dict[str, Any]] = [KG_SEARCH, RENDER_HIGHLIGHT, LEAD_UPDATE_SCORE, SPATIAL_NAVIGATE]
