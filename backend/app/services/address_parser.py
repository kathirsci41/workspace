from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher


@dataclass(slots=True)
class AddressMatchResult:
    result: str
    message: str
    left_pin: str | None = None
    right_pin: str | None = None
    similarity: float = 0.0


def parse_delivery_address(address: str | None) -> dict[str, str | None]:
    text = str(address or "").strip()
    pin = _first_match(text, r"\b\d{6}\b")
    state = _first_match(
        text,
        r"\b(TAMIL NADU|KARNATAKA|MAHARASHTRA|DELHI|TELANGANA|KERALA|ANDHRA PRADESH|GUJARAT)\b",
    )
    city = None
    if pin:
        before_pin = text[: text.find(pin)]
        tokens = [part.strip(" ,.-") for part in re.split(r"[,|\n]", before_pin) if part.strip()]
        if tokens:
            city = tokens[-1]
    return {"address": text or None, "pin": pin, "city": city, "state": state}


def validate_addresses(left: str | None, right: str | None) -> AddressMatchResult:
    left_parsed = parse_delivery_address(left)
    right_parsed = parse_delivery_address(right)
    if not left_parsed["address"] or not right_parsed["address"]:
        return AddressMatchResult("REVIEW_REQUIRED", "Address missing on one document.")
    if left_parsed["pin"] and right_parsed["pin"]:
        if left_parsed["pin"] == right_parsed["pin"]:
            return AddressMatchResult("PASS", "Delivery PIN codes match.", left_parsed["pin"], right_parsed["pin"], 1.0)
        return AddressMatchResult("MISMATCH", "Delivery PIN codes differ.", left_parsed["pin"], right_parsed["pin"], 0.0)
    similarity = SequenceMatcher(
        None,
        _normalize_address(left_parsed["address"]),
        _normalize_address(right_parsed["address"]),
    ).ratio()
    if similarity >= 0.72:
        return AddressMatchResult("PARTIAL_PASS", "PIN missing but address text is similar.", similarity=round(similarity, 3))
    return AddressMatchResult("REVIEW_REQUIRED", "PIN missing and address match is uncertain.", similarity=round(similarity, 3))


def _first_match(text: str, pattern: str) -> str | None:
    match = re.search(pattern, text, flags=re.I)
    return match.group(0).upper() if match else None


def _normalize_address(value: str | None) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^A-Z0-9 ]+", " ", str(value or "").upper())).strip()
