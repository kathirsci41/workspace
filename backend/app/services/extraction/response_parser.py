import json
import re
import logging
from datetime import date, datetime

logger = logging.getLogger(__name__)


class ParseError(Exception):
    pass


class ResponseParser:
    def parse_response(self, raw_text: str) -> dict:
        """Try multiple strategies to extract JSON from OCR output."""
        text = raw_text.strip()

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
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            substring = text[first_brace : last_brace + 1]
            try:
                return json.loads(substring)
            except json.JSONDecodeError:
                # Strategy 4: Clean common issues
                cleaned = self._clean_json(substring)
                try:
                    return json.loads(cleaned)
                except json.JSONDecodeError:
                    pass

        raise ParseError(f"Could not parse JSON from: {text[:200]}")

    def parse_and_merge(self, raw_texts: list[str], document_type: str) -> dict:
        """Parse each raw text and merge, taking first non-null per field."""
        merged = {}
        for text in raw_texts:
            try:
                parsed = self.parse_response(text)
                for key, value in parsed.items():
                    if key not in merged or merged[key] is None:
                        merged[key] = value
            except ParseError:
                logger.warning(f"Failed to parse one page response")
                continue
        return merged

    def calculate_confidence(self, extracted: dict, schema_fields: list[str]) -> float:
        """Calculate extraction confidence based on filled fields.

        Fields flagged LOW_CONFIDENCE or AMOUNT_PARSE_FAILED in _validation
        count as half a point — present but suspect.
        """
        if not schema_fields:
            return 0.0
        validation = extracted.get("_validation", {})
        filled = 0.0
        for f in schema_fields:
            val = extracted.get(f)
            if val is not None and str(val).strip() != "":
                if validation.get(f) in ("LOW_CONFIDENCE", "AMOUNT_PARSE_FAILED"):
                    filled += 0.5
                else:
                    filled += 1.0
        return round((filled / len(schema_fields)) * 100, 1)

    def parse_date(self, date_str: str | None) -> date | None:
        """Try multiple date formats. Return None on failure."""
        if not date_str or not isinstance(date_str, str):
            return None

        date_str = date_str.strip()

        formats = [
            "%d-%m-%Y",
            "%d/%m/%Y",
            "%d.%m.%Y",
            "%Y-%m-%d",
            "%d-%b-%Y",
            "%d %b %Y",
            "%B %d, %Y",
            "%d-%m-%y",
            "%d/%m/%y",
            "%Y/%m/%d",
            "%m-%d-%Y",
            "%m/%d/%Y",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue

        return None

    @staticmethod
    def _clean_json(text: str) -> str:
        """Clean common JSON issues from OCR model output."""
        # Remove trailing commas before } or ]
        cleaned = re.sub(r",\s*([}\]])", r"\1", text)
        # Remove any control characters
        cleaned = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", cleaned)
        # Fix comma-formatted numbers (e.g. 86,678.5 → 86678.5)
        # Match digits followed by comma+3digits that are NOT inside quotes
        # We handle this by finding number patterns with commas
        cleaned = re.sub(
            r'(?<=[:\s,\[])\s*(\d{1,3}(?:,\d{3})+(?:\.\d+)?)(?=\s*[,}\]])',
            lambda m: m.group(1).replace(',', ''),
            cleaned,
        )
        # Also fix numbers with commas that appear as JSON values directly
        # e.g. "subtotal": 86,678.5 → "subtotal": 86678.5
        cleaned = re.sub(
            r'("\s*:\s*)(\d{1,3}(?:,\d{3})+(?:\.\d+)?)',
            lambda m: m.group(1) + m.group(2).replace(',', ''),
            cleaned,
        )
        return cleaned
