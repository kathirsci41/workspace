"""LLM-assisted item description → part_no linking.

Two-tier approach:
  1. Exact case-insensitive description match  — zero latency, 100% confidence
  2. LLM match for remainder                  — ~3-8s first call, cached 1h in Redis
"""
import enum as _enum
import json
import logging
import httpx

from app.config import settings

logger = logging.getLogger(__name__)


def _safe_int(v) -> int:
    """Safely parse qty from LLM extraction. Handles '2,000'→2000, '3.00'→3, None→0. Unparseable strings like '5 Nos' return 0."""
    if v is None:
        return 0
    try:
        return int(float(str(v).replace(",", "")))
    except (ValueError, TypeError):
        return 0


async def match_items_by_description(
    customer_items: list[dict],   # from CUSTOMER_PO — have description, no part_no
    company_items: list[dict],    # from COMPANY_PO  — have part_no + description
    redis_client=None,
    cache_key: str | None = None,
) -> list[dict]:
    """
    Returns list of {sr_no, description, matched_part_no, confidence, match_type}.
    match_type: 'exact' | 'ai' | 'unmatched'
    """
    if not customer_items or not company_items:
        return []

    # Check Redis cache
    if redis_client and cache_key:
        try:
            cached = await redis_client.get(f"item_match:{cache_key}")
            if cached:
                return json.loads(cached)
        except Exception as e:
            logger.warning(f"Redis cache read failed: {e}")

    # Tier 1: exact description match (case-insensitive)
    company_by_desc = {
        str(it.get("description", "")).lower().strip(): it
        for it in company_items
        if it.get("description")
    }
    results: list[dict] = []
    unmatched: list[dict] = []

    for item in customer_items:
        desc = str(item.get("description", "")).lower().strip()
        if desc and desc in company_by_desc:
            results.append({
                "sr_no": item.get("sr_no"),
                "description": item.get("description"),
                "matched_part_no": company_by_desc[desc].get("part_no"),
                "confidence": 1.0,
                "match_type": "exact",
            })
        else:
            unmatched.append(item)

    # Tier 2: LLM match for remainder
    if unmatched:
        try:
            results.extend(await _llm_match(unmatched, company_items))
        except Exception as e:
            logger.warning(f"LLM item matching failed: {e} — marking as unmatched")
            for item in unmatched:
                results.append({
                    "sr_no": item.get("sr_no"),
                    "description": item.get("description"),
                    "matched_part_no": None,
                    "confidence": 0.0,
                    "match_type": "unmatched",
                })

    # Cache result
    if redis_client and cache_key and results:
        try:
            await redis_client.setex(f"item_match:{cache_key}", 3600, json.dumps(results))
        except Exception as e:
            logger.warning(f"Redis cache write failed: {e}")

    return results


async def _llm_match(unmatched: list[dict], company_items: list[dict]) -> list[dict]:
    catalog = [
        {"part_no": it.get("part_no"), "description": it.get("description")}
        for it in company_items
        if it.get("part_no")
    ]
    if not catalog:
        return [
            {
                "sr_no": item.get("sr_no"),
                "description": item.get("description"),
                "matched_part_no": None,
                "confidence": 0.0,
                "match_type": "unmatched",
            }
            for item in unmatched
        ]

    prompt = (
        "Match each customer item description to the best part number from the catalog. "
        "Return ONLY a valid JSON array with objects: "
        "{\"sr_no\": ..., \"matched_part_no\": ... or null, \"confidence\": 0-1}. "
        "No explanation — JSON only.\n\n"
        f"Customer items:\n{json.dumps([{'sr_no': i.get('sr_no'), 'description': i.get('description')} for i in unmatched])}\n\n"
        f"Catalog:\n{json.dumps(catalog)}"
    )

    base = (settings.ocr_extractor_base_url or settings.ocr_base_url).rstrip("/")
    model = settings.ocr_extractor_model

    verify = settings.ocr_extractor_ca_bundle if settings.ocr_extractor_ca_bundle else True
    async with httpx.AsyncClient(timeout=30, verify=verify) as client:
        resp = await client.post(
            f"{base}/api/chat",
            json={
                "model": model,
                "stream": False,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        resp.raise_for_status()
        raw = resp.json()["message"]["content"]

    # Extract JSON array from response (LLM may wrap in markdown fences)
    start = raw.find("[")
    end = raw.rfind("]")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON array in LLM response: {raw[:200]}")
    parsed: list[dict] = json.loads(raw[start : end + 1])

    sr_map = {str(i.get("sr_no")): i for i in unmatched}
    results = []
    for match in parsed:
        original = sr_map.get(str(match.get("sr_no")), {})
        results.append({
            "sr_no": match.get("sr_no"),
            "description": original.get("description"),
            "matched_part_no": match.get("matched_part_no"),
            "confidence": float(match.get("confidence", 0)),
            "match_type": "ai",
        })
    return results


class ItemMatchStatus(str, _enum.Enum):
    """Status of a line item comparison between PO and delivery document."""
    MATCHED = "matched"
    PARTIAL = "partial"    # Qty delivered < qty ordered
    MISSING = "missing"    # Item not in delivery at all


def compare_po_to_delivery(
    cpo_items: list[dict],
    delivery_items: list[dict],
) -> list[dict]:
    """
    Compare CPO line items against a delivery document (DC or Invoice).

    Args:
        cpo_items: List of order items from Customer/Company PO
        delivery_items: List of items from delivery document (DC or Invoice)

    Each item dict should contain:
        - part_no (str): Part number for matching
        - description (str): Item description
        - qty (int): Quantity

    Returns:
        List of comparison results, each with:
        - part_no: The part number from CPO
        - description: The description from CPO
        - qty_ordered: Quantity ordered in PO
        - qty_delivered: Quantity delivered (0 if missing)
        - qty_shortfall: qty_ordered - qty_delivered (0 if fully delivered)
        - status: ItemMatchStatus enum value

    Matching is case-insensitive on part_no.
    """
    # Build lookup map of delivery items by part_no (case-insensitive)
    delivery_by_part: dict[str, dict] = {
        str(it.get("part_no", "")).lower().strip(): it
        for it in (delivery_items or [])
        if it.get("part_no")
    }

    results = []
    for item in (cpo_items or []):
        part_no = str(item.get("part_no", "")).lower().strip()
        qty_ordered = _safe_int(item.get("qty"))
        matched = delivery_by_part.get(part_no)

        if not matched:
            # Item not found in delivery
            results.append({
                "part_no": item.get("part_no"),
                "description": item.get("description"),
                "qty_ordered": qty_ordered,
                "qty_delivered": 0,
                "qty_shortfall": qty_ordered,
                "status": ItemMatchStatus.MISSING,
            })
            continue

        # Item found, check quantity
        qty_delivered = _safe_int(matched.get("qty"))
        shortfall = max(0, qty_ordered - qty_delivered)
        status = ItemMatchStatus.MATCHED if shortfall == 0 else ItemMatchStatus.PARTIAL
        results.append({
            "part_no": item.get("part_no"),
            "description": item.get("description"),
            "qty_ordered": qty_ordered,
            "qty_delivered": qty_delivered,
            "qty_shortfall": shortfall,
            "status": status,
        })

    return results
