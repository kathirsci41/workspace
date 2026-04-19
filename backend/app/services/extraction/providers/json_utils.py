"""Shared JSON parsing utilities for all extraction providers.

Extracted from two_layer_client.py — used by Ollama, OpenAI-compat,
and any future provider that receives LLM text and must parse JSON from it.
"""
import json
import re
import logging

logger = logging.getLogger(__name__)


def parse_json_safe(text: str, context: str = "") -> dict:
    """Safely parse JSON from an LLM response.

    Uses a 4-strategy cascade:
      1. Direct json.loads()
      2. Extract from ```json ... ``` code blocks
      3. Find first { and last }, parse substring
      4. Clean common issues (trailing commas, control chars, comma-numbers) and retry

    Returns {} on total failure (never raises).
    """
    text = text.strip()

    # Strategy 1: Direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Strategy 2: Extract from ```json ... ``` code blocks
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Strategy 3: Find first { and last }
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace > first_brace:
        substring = text[first_brace: last_brace + 1]
        try:
            return json.loads(substring)
        except json.JSONDecodeError:
            # Strategy 4: Clean common issues and retry
            cleaned = clean_json(substring)
            try:
                return json.loads(cleaned)
            except json.JSONDecodeError:
                pass

    label = f"[{context}] " if context else ""
    logger.warning(f"{label}Could not parse JSON from LLM response: {text[:200]}")
    return {}


def unwrap_field_confidences(fields: dict) -> dict:
    """Unwrap LLM confidence-wrapped scalar values.

    The extraction prompt asks the LLM to return each scalar field as
    {"value": <extracted>, "confidence": 0.0-1.0}. This function:
    - Replaces each such dict with its bare value in-place
    - Collects all confidence scores into fields["_field_confidences"]
    - Leaves arrays, None values, and plain scalars unchanged
    """
    field_confidences: dict[str, float] = {}
    for key in list(fields.keys()):
        val = fields[key]
        if (
            isinstance(val, dict)
            and "value" in val
            and "confidence" in val
            and not isinstance(val.get("value"), list)
        ):
            try:
                confidence = round(float(val["confidence"]), 3)
            except (TypeError, ValueError):
                confidence = 0.5
            field_confidences[key] = confidence
            fields[key] = val["value"]
    if field_confidences:
        fields["_field_confidences"] = {
            **fields.get("_field_confidences", {}),
            **field_confidences,
        }
    return fields


def clean_json(text: str) -> str:
    """Clean common JSON issues from LLM output."""
    # Remove trailing commas before } or ]
    cleaned = re.sub(r",\s*([}\]])", r"\1", text)
    # Remove control characters
    cleaned = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", cleaned)
    # Fix comma-formatted numbers in JSON values (e.g. "1,234,567" → "1234567")
    cleaned = re.sub(
        r'("\s*:\s*)(\d{1,3}(?:,\d{3})+(?:\.\d+)?)',
        lambda m: m.group(1) + m.group(2).replace(",", ""),
        cleaned,
    )
    return cleaned
