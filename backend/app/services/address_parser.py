"""Parse Indian delivery addresses into structured components."""
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

    # City: word(s) immediately before PIN code
    city = None
    if pin_match:
        before_pin = raw[:pin_match.start()].strip().rstrip(",- ")
        city_match = re.search(r'[\w\s]+$', before_pin)
        if city_match:
            candidate = city_match.group().strip().split(",")[-1].strip()
            if 2 < len(candidate) < 40:
                city = candidate

    return {"pin_code": pin_code, "city": city, "state": state, "full_address": raw}
