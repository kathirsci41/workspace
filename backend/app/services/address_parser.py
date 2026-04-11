"""Parse Indian delivery addresses into structured components."""
import enum as _enum
import re

INDIAN_STATES = {
    "andhra pradesh", "arunachal pradesh", "assam", "bihar", "chhattisgarh",
    "goa", "gujarat", "haryana", "himachal pradesh", "jharkhand", "karnataka",
    "kerala", "madhya pradesh", "maharashtra", "manipur", "meghalaya", "mizoram",
    "nagaland", "odisha", "punjab", "rajasthan", "sikkim", "tamil nadu",
    "telangana", "tripura", "uttar pradesh", "uttarakhand", "west bengal",
    "delhi", "jammu and kashmir", "ladakh", "chandigarh", "puducherry",
}


def parse_delivery_address(raw: str | None) -> dict:
    """Returns {pin_code, city, state, full_address}. All fields may be None."""
    if not raw:
        return {"pin_code": None, "city": None, "state": None, "full_address": None}

    raw = str(raw).strip()
    pin_match = re.search(r'\b(\d{6})\b', raw)
    pin_code = pin_match.group(1) if pin_match else None

    state = None
    raw_lower = raw.lower()
    for s in INDIAN_STATES:
        if s in raw_lower:
            state = s.title()
            break

    # City: word(s) immediately before PIN code, or last comma-separated part before state
    city = None
    if pin_match:
        before_pin = raw[:pin_match.start()].strip().rstrip(",- ")
        city_match = re.search(r'[\w\s]+$', before_pin)
        if city_match:
            candidate = city_match.group().strip().split(",")[-1].strip()
            if 2 < len(candidate) < 40:
                city = candidate
    else:
        # No PIN code: try to extract from comma-separated parts
        # Look for the part immediately before state, or last significant part
        parts = [p.strip() for p in raw.split(',')]
        if state:
            # Find the part before state name
            state_lower = state.lower()
            for i, part in enumerate(parts):
                if state_lower in part.lower():
                    # Try the part immediately before the state
                    if i > 0:
                        candidate = parts[i - 1].strip()
                        if 2 < len(candidate) < 40 and not re.search(r'\d{4,}', candidate):
                            city = candidate
                    break
        else:
            # No state found; try last non-empty, non-numeric part
            for part in reversed(parts):
                part = part.strip()
                if part and 2 < len(part) < 40 and not re.search(r'\d{4,}', part):
                    city = part
                    break

    return {"pin_code": pin_code, "city": city, "state": state, "full_address": raw}


class AddressMatchResult(str, _enum.Enum):
    MATCH = "match"
    PARTIAL = "partial"   # City + state match, no PIN code available
    MISMATCH = "mismatch"
    SKIP = "skip"         # One or both addresses missing/empty


def validate_addresses(
    address_a: str | None,
    address_b: str | None,
) -> AddressMatchResult:
    """
    Compare two address strings using extracted components.

    PIN code match → MATCH (most reliable).
    City + state match (no PIN) → PARTIAL.
    State differs → MISMATCH.
    Either address missing → SKIP.
    """
    if not address_a or not address_b:
        return AddressMatchResult.SKIP

    parsed_a = parse_delivery_address(address_a)
    parsed_b = parse_delivery_address(address_b)

    # PIN code is the most reliable signal
    if parsed_a["pin_code"] and parsed_b["pin_code"]:
        return (
            AddressMatchResult.MATCH
            if parsed_a["pin_code"] == parsed_b["pin_code"]
            else AddressMatchResult.MISMATCH
        )

    # Fall back to state + city
    state_a = (parsed_a["state"] or "").lower()
    state_b = (parsed_b["state"] or "").lower()
    city_a  = (parsed_a["city"] or "").lower()
    city_b  = (parsed_b["city"] or "").lower()

    if state_a and state_b and state_a != state_b:
        return AddressMatchResult.MISMATCH

    if state_a == state_b and city_a and city_b and city_a == city_b:
        return AddressMatchResult.PARTIAL

    return AddressMatchResult.SKIP
