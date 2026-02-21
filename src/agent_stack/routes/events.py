"""SSE events route — real-time status updates."""

from __future__ import annotations

from fastapi import APIRouter, Request

from agent_stack.events.sse import EventManager

router = APIRouter(tags=["events"])


@router.get("/events")
async def events(request: Request):
    """SSE endpoint for real-time pipeline status updates."""
    manager = EventManager.get_instance()
    return manager.create_response(request)
