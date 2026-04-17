"""
Chat service: intent detection, prompt building, Ollama streaming.
"""
from __future__ import annotations

import json
import re
import httpx
from typing import AsyncIterator
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.services.chat_context import (
    build_order_context,
    build_search_context,
    build_platform_context,
)

SYSTEM_PROMPT = """You are an assistant for a logistics document processing platform. \
You help operators and managers understand order status, find documents, and identify issues. \
Be concise and specific. Reference exact document types, amounts, and reference numbers from the \
data provided. If an issue exists, explain what it is and what action is needed. \
Format responses in plain text — avoid markdown headers. Use bullet points only for lists of 3+ items."""

# Keywords that suggest each intent
_ORDER_KEYWORDS = {"order", "po", "status", "chain", "invoice", "document", "missing", "wrong", "issue", "problem", "mismatch", "billing", "verify", "verified"}
_SEARCH_KEYWORDS = {"find", "search", "look", "locate", "where", "which", "ref", "reference", "number"}
_PLATFORM_KEYWORDS = {"today", "attention", "summary", "overview", "all orders", "dashboard", "pending", "total", "how many"}


def _detect_intent(message: str, po_id: str | None) -> str:
    """Simple keyword-based intent detection."""
    if po_id:
        return "order_query"

    lower = message.lower()
    tokens = set(re.findall(r"\b\w+\b", lower))

    if tokens & _PLATFORM_KEYWORDS:
        return "platform_query"
    if tokens & _SEARCH_KEYWORDS:
        return "search_query"
    if tokens & _ORDER_KEYWORDS:
        return "order_query"
    return "general"


async def stream_chat_response(
    message: str,
    po_id: str | None,
    db: AsyncSession,
) -> AsyncIterator[str]:
    """
    Build context, call Ollama, and yield SSE-formatted chunks.
    Each yielded string is a complete SSE line: 'data: {...}\n\n'
    Final chunk includes 'done: true'.
    """
    intent = _detect_intent(message, po_id)

    # Build context based on intent
    context_block = ""
    if intent == "order_query" and po_id:
        context_block = await build_order_context(po_id, db)
    elif intent == "search_query":
        context_block = await build_search_context(message, db)
    elif intent == "platform_query":
        context_block = await build_platform_context(db)

    system_content = SYSTEM_PROMPT
    if context_block:
        system_content = f"{SYSTEM_PROMPT}\n\n{context_block}"

    payload = {
        "model": settings.ocr_extractor_model,
        "messages": [
            {"role": "system", "content": system_content},
            {"role": "user", "content": message},
        ],
        "stream": True,
        "options": {
            "num_ctx": 8192,
            "num_predict": 1024,
            "temperature": 0.3,
        },
    }

    ollama_url = f"{settings.ocr_extractor_base_url}/api/chat"

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("POST", ollama_url, json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    chunk = data.get("message", {}).get("content", "")
                    done = data.get("done", False)

                    if done:
                        yield f"data: {json.dumps({'chunk': '', 'done': True})}\n\n"
                    elif chunk:
                        yield f"data: {json.dumps({'chunk': chunk, 'done': False})}\n\n"

    except httpx.HTTPError as exc:
        error_msg = f"Chat service unavailable: {exc}"
        yield f"data: {json.dumps({'chunk': error_msg, 'done': False})}\n\n"
        yield f"data: {json.dumps({'chunk': '', 'done': True})}\n\n"
    except Exception as exc:
        error_msg = f"Unexpected error: {exc}"
        yield f"data: {json.dumps({'chunk': error_msg, 'done': False})}\n\n"
        yield f"data: {json.dumps({'chunk': '', 'done': True})}\n\n"
