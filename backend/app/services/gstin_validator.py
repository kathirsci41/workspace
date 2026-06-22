from __future__ import annotations

import re

_GSTIN_PATTERN = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")

VALID_STATE_CODES = {
    "01",
    "02",
    "03",
    "04",
    "05",
    "06",
    "07",
    "08",
    "09",
    "10",
    "11",
    "12",
    "13",
    "14",
    "15",
    "16",
    "17",
    "18",
    "19",
    "20",
    "21",
    "22",
    "23",
    "24",
    "25",
    "26",
    "27",
    "28",
    "29",
    "30",
    "31",
    "32",
    "33",
    "34",
    "35",
    "36",
    "37",
    "38",
    "97",
}


def normalize_gstin(gstin: str | None) -> str:
    return re.sub(r"\s+", "", str(gstin or "")).upper()


def validate_gstin(gstin: str | None) -> tuple[bool, str]:
    value = normalize_gstin(gstin)
    if not value:
        return False, "GSTIN empty"
    if not _GSTIN_PATTERN.match(value):
        return False, f"GSTIN format invalid: {value}"
    state_code = value[:2]
    if state_code not in VALID_STATE_CODES:
        return False, f"Invalid state code: {state_code}"
    return True, ""
