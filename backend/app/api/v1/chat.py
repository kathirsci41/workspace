"""
Chat API router — POST (non-streaming) and GET (SSE streaming) endpoints.
"""
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.chat_service import stream_chat_response

router = APIRouter()


@router.get("/stream")
async def chat_stream(
    message: str = Query(..., min_length=1, max_length=2000),
    po_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Server-Sent Events endpoint for streaming chat responses.
    Each event: data: {"chunk": "...", "done": false}
    Final event: data: {"chunk": "", "done": true}
    """
    return StreamingResponse(
        stream_chat_response(message=message, po_id=po_id, db=db),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
