import json
import re
import logging
from typing import Dict, Any, Optional, Tuple
from datetime import date, datetime as dt

logger = logging.getLogger(__name__)


def parse_ocr_response(
    raw_response: str,
    expected_schema: dict,
    primary_ref_field: str,
    date_field: str
) -> Tuple[Dict[str, Any], Optional[str], Optional[date], float]:
    """
    Parse the raw GLM-OCR response into structured data.

    Args:
        raw_response: Raw text from GLM-OCR
        expected_schema: Expected JSON schema (for validation)
        primary_ref_field: Key name for the primary reference
        date_field: Key name for the date field

    Returns:
        Tuple of (extracted_data, primary_ref_no, doc_date, confidence_score)
    """
    # Step 1: Extract JSON from response
    extracted_json = _extract_json(raw_response)

    if not extracted_json:
        logger.warning("Failed to extract JSON from OCR response")
        return {}, None, None, 0.0

    # Step 2: Validate against expected schema
    validated_data = _validate_against_schema(extracted_json, expected_schema)

    # Step 3: Extract promoted fields
    primary_ref = validated_data.get(primary_ref_field, "").strip() or None
    doc_date = _parse_date(validated_data.get(date_field, ""))

    # Step 4: Calculate confidence score
    confidence = _calculate_confidence(validated_data, expected_schema)

    logger.info(
        f"Parsed extraction: ref={primary_ref}, date={doc_date}, "
        f"confidence={confidence:.2f}, fields_found={sum(1 for v in validated_data.values() if v)}"
    )

    return validated_data, primary_ref, doc_date, confidence


def _extract_json(raw_text: str) -> Optional[dict]:
    """
    Extract a JSON object from raw model output.
    Handles common issues like markdown code blocks, extra text, etc.
    """
    text = raw_text.strip()

    # Try 1: Direct JSON parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try 2: Extract from markdown code block
    json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Try 3: Find first { ... } block
    brace_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass

    # Try 4: Fix common JSON issues (trailing commas, single quotes)
    cleaned = text
    cleaned = re.sub(r',\s*}', '}', cleaned)   # trailing commas
    cleaned = re.sub(r',\s*]', ']', cleaned)
    cleaned = cleaned.replace("'", '"')          # single -> double quotes
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    logger.error(f"Could not extract JSON from response: {text[:200]}...")
    return None


def _validate_against_schema(data: dict, schema: dict) -> dict:
    """
    Validate extracted data against the expected schema.
    Only keeps keys that are in the schema. Ensures all values are strings.
    """
    validated = {}
    for key in schema:
        value = data.get(key, "")
        # Ensure string type
        if value is None:
            value = ""
        elif not isinstance(value, str):
            value = str(value)
        validated[key] = value.strip()

    return validated


def _parse_date(date_str: str) -> Optional[date]:
    """
    Try to parse a date string in various formats.
    Returns None if parsing fails.
    """
    if not date_str or not date_str.strip():
        return None

    date_str = date_str.strip()

    # Common date formats found in Indian business documents
    formats = [
        "%d-%m-%Y",      # 15-01-2026
        "%d/%m/%Y",      # 15/01/2026
        "%d.%m.%Y",      # 15.01.2026
        "%Y-%m-%d",      # 2026-01-15
        "%d-%b-%Y",      # 15-Jan-2026
        "%d %b %Y",      # 15 Jan 2026
        "%d %B %Y",      # 15 January 2026
        "%d-%m-%y",      # 15-01-26
        "%d/%m/%y",      # 15/01/26
        "%m/%d/%Y",      # 01/15/2026
        "%b %d, %Y",     # Jan 15, 2026
        "%B %d, %Y",     # January 15, 2026
    ]

    for fmt in formats:
        try:
            return dt.strptime(date_str, fmt).date()
        except ValueError:
            continue

    logger.warning(f"Could not parse date: {date_str}")
    return None


def _calculate_confidence(data: dict, schema: dict) -> float:
    """
    Calculate a confidence score based on how many fields were extracted.

    Score = (non-empty fields / total expected fields) * 100

    This is a basic heuristic. In future, GLM-OCR's internal confidence
    scores could be used if available.
    """
    total_fields = len(schema)
    if total_fields == 0:
        return 0.0

    filled_fields = sum(1 for key in schema if data.get(key, "").strip())
    return round((filled_fields / total_fields) * 100, 2)
