"""Status route — dependency health checks and operational statistics."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from agent_stack.agents.llm import create_chat_client
from agent_stack.services.health import StorageHealthConfig, check_all
from agent_stack.services.status import collect_stats

router = APIRouter(tags=["status"])


@router.get("/status", response_class=HTMLResponse)
async def status(request: Request) -> HTMLResponse:
    """Render the status page with live health probe results and stats."""
    cosmos = request.app.state.cosmos
    settings = request.app.state.settings
    processor = request.app.state.processor
    storage = request.app.state.storage
    start_time = request.app.state.start_time
    chat_client = create_chat_client(settings.openai)

    health_coro = check_all(
        cosmos.database,
        chat_client,
        processor,
        cosmos_config=settings.cosmos,
        openai_config=settings.openai,
        storage_health=StorageHealthConfig(client=storage, config=settings.storage),
    )
    stats_coro = collect_stats(
        cosmos.database,
        environment=settings.app.env,
        start_time=start_time,
    )

    results, stats = await asyncio.gather(health_coro, stats_coro)

    templates = request.app.state.templates
    return templates.TemplateResponse(
        "status.html",
        {
            "request": request,
            "checks": results,
            "info": stats,
        },
    )
