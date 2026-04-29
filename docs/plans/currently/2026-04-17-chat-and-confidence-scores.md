# Implementation Plan — Intelligent Chat Page + Per-Field Confidence Scores
**Date:** 2026-04-17
**Status:** In Progress

---

## Context

Two features being added before client demo:

1. **Per-field confidence scores** — extraction pipeline already stores `field_confidences` in DB and ReviewModal UI already reads it, but the two-layer pipeline (glm-ocr + gemma4:e2b) never populates it. Fix: update the Layer 2 prompt to return confidence per field alongside each value.

2. **Intelligent Chat Page** — a dedicated assistant page where operators/managers can ask plain-English questions about orders and documents. Uses `gemma4:e2b` (already installed) as the LLM, the existing PostgreSQL data as context, and streams responses back to the frontend.

---

## Feature 1 — Per-Field Confidence Scores

### Problem
`document_metadata.field_confidences` is always `NULL` from the current pipeline.
Only `layoutlm_extractor.py` (Phase 7 / future) populates it.
The two-layer client (`two_layer_client.py`) and all providers ignore per-field confidence.

### Solution
Change the Layer 2 extraction prompt to return confidence alongside each value:

```json
{
  "po_number":    { "value": "PO-2024-123", "confidence": 0.97 },
  "total_amount": { "value": "150000",      "confidence": 0.82 },
  "vendor_name":  { "value": "Acme Corp",   "confidence": 0.61 }
}
```

Then split value vs confidence in the response parser, store in `_field_confidences`.

### Files to Change

| File | Change |
|------|--------|
| `backend/app/services/extraction/prompts.py` | Update extraction prompt to request `{"value": ..., "confidence": 0-1}` per field |
| `backend/app/services/extraction/response_parser.py` | Parse new format — extract value from `result["field"]["value"]`, build `_field_confidences` dict |
| `backend/app/services/extraction/two_layer_client.py` | Pass `_field_confidences` through from parsed result to task |

### No Frontend Changes Needed
`ReviewModal.tsx` already handles `field_confidences`:
- Line 163-164: reads `metadata.field_confidences`
- Line 610-680: renders per-field confidence badges with color coding
- Color logic: ≥80% green, ≥50% yellow, <50% red

### Confidence Thresholds
- **≥ 0.80** → High confidence (green) — safe to verify as-is
- **0.50–0.79** → Medium confidence (yellow) — reviewer should double-check
- **< 0.50** → Low confidence (red) — flag for mandatory manual check

---

## Feature 2 — Intelligent Chat Page

### Architecture

```
Frontend                    Backend                     Data
─────────────────────────   ───────────────────────────  ──────────────────────
ChatPage.tsx                POST /api/v1/chat            PostgreSQL
  │  user message           GET  /api/v1/chat/stream       purchase_orders
  │  optional po_id              │                          documents
  │                         chat_service.py               document_metadata
  │  EventSource (SSE)           │ intent detection         reference_index
  │  ◄── streaming chunks        │ context builder          chain validation
  │                         chat_context.py
  │  render markdown              │ build_order_context()
  │  clickable order links        │ build_search_context()
                                  │ build_platform_context()
                                  ▼
                            Ollama gemma4:e2b
                              /api/chat (stream=true)
```

### New Backend Files

#### `backend/app/api/v1/chat.py`
```
POST /api/v1/chat
  Body: { message: str, po_id?: UUID, session_id?: str }
  Returns: { response: str, references: [{ type, id, label }] }

GET /api/v1/chat/stream
  Query: message, po_id?, session_id?
  Returns: text/event-stream (SSE)
  Chunks: data: {"chunk": "...", "done": false}
          data: {"chunk": "", "done": true, "references": [...]}
```

#### `backend/app/services/chat_service.py`
Responsibilities:
- Detect intent: order_query / search_query / action_suggestion / general
- Build prompt from context
- Call gemma4:e2b via Ollama `/api/chat` with `stream=true`
- Yield chunks for SSE
- Extract references (order IDs, doc IDs) from response

System prompt (concise version):
```
You are an assistant for a logistics document platform. You help operators and managers
understand order status, find documents, and identify issues. Be concise and specific.
Reference exact document types, amounts, and reference numbers from the data provided.
If an issue exists, explain what it is and what action is needed.
```

#### `backend/app/services/chat_context.py`
Three context builders:

**`build_order_context(po_id, db)`**
Fetches and formats:
- PO details (number, customer, amount, status, billing type)
- Chain validation result (status, missing slots, reference checks, billing)
- All documents (type, status, primary_ref_no, confidence_score, total_amount)
- SO number if set

**`build_search_context(query, db)`**
- Queries `reference_index` for matching ref values
- Queries `document_metadata` for matching primary_ref_no
- Returns matching orders/documents with status summary

**`build_platform_context(db)`**
- Order counts by status
- Document counts by status
- Orders with MISMATCH or INCOMPLETE chain

### New Frontend Files

#### `frontend/src/pages/ChatPage.tsx`
UI structure:
```
┌─────────────────────────────────────────────────────┐
│  Assistant                              [PO Context ▼]│
├─────────────────────────────────────────────────────┤
│                                                       │
│  ┌───────────────────────────────────────────────┐   │
│  │ AI  What can I help you with?                 │   │
│  └───────────────────────────────────────────────┘   │
│                                                       │
│  ┌─────────────────────────────────────────┐         │
│  │ You  What's wrong with this order?      │         │
│  └─────────────────────────────────────────┘         │
│                                                       │
│  ┌───────────────────────────────────────────────┐   │
│  │ AI  This order has 2 issues:                  │   │
│  │  • Company Invoice amount (₹2,98,000) doesn't │   │
│  │    match Stage 1 milestone (₹3,00,000)         │   │
│  │  • SO number on Company DC doesn't match       │   │
│  │    entered SO number SO-2024-456               │   │
│  │  → [View PO-2024-123]                         │   │
│  └───────────────────────────────────────────────┘   │
│                                                       │
│  Quick: [What needs attention?] [Find missing docs]   │
│         [Summarize billing]     [What to do next?]    │
├─────────────────────────────────────────────────────┤
│  [Type your question...                    ] [Send]   │
└─────────────────────────────────────────────────────┘
```

Key behaviors:
- PO Context selector: attach a specific order to the conversation
- Quick chips: pre-filled prompts for common actions
- Streaming: typewriter effect via `EventSource`
- References: AI mentions "PO-2024-123" → auto-linked to `/purchase-orders/{id}`
- Message history: kept in component state (not persisted)

#### `frontend/src/api/chat.ts`
```typescript
sendMessage(message, poId?, sessionId?) → Promise<ChatResponse>
streamMessage(message, poId?, onChunk, onDone) → () => void  // returns cleanup fn
```

### App Wiring
- `frontend/src/App.tsx` — add `/chat` route
- `frontend/src/components/layout/AppShell.tsx` — add "Assistant" nav item with MessageSquare icon
- `backend/app/api/v1/__init__.py` — register chat router

---

## Build Order

### Step 1 — Confidence Scores (do first)
- [ ] Update extraction prompt in `prompts.py`
- [ ] Update response parser in `response_parser.py`
- [ ] Pass through in `two_layer_client.py`
- [ ] Test: re-extract one document, verify `field_confidences` is non-null in DB
- [ ] Test: open ReviewModal, verify colored confidence badges appear

### Step 2 — Chat Backend
- [ ] Create `chat_context.py` with 3 context builders
- [ ] Create `chat_service.py` with intent detection + prompt builder + Ollama streaming
- [ ] Create `chat.py` API router with POST + SSE GET endpoints
- [ ] Register router in `backend/app/main.py`
- [ ] Test: `curl` the chat endpoint with a real PO ID

### Step 3 — Chat Frontend
- [ ] Create `frontend/src/api/chat.ts`
- [ ] Create `frontend/src/pages/ChatPage.tsx` with full UI
- [ ] Add route to `App.tsx`
- [ ] Add sidebar link to `AppShell.tsx`
- [ ] Test: open chat page, send a message, verify streaming response

### Step 4 — Integration Testing
- [ ] Ask "What's wrong with PO-{id}?" → verify AI explains chain issues
- [ ] Ask "Find invoice INV-{ref}" → verify reference lookup works
- [ ] Ask "What needs attention today?" → verify platform-wide summary
- [ ] Verify streaming works (typewriter effect appears)
- [ ] Verify PO links in responses are clickable

---

## Out of Scope (Phase 2)
- Floating chat widget (plan separately)
- Autonomous actions via chat (verify/reject from chat)
- Persistent chat history across sessions
- Fine-tuning gemma4 on platform-specific data
