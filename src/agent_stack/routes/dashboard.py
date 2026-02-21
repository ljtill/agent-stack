"""Dashboard route — pipeline overview."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["dashboard"])


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Render the dashboard overview page."""
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request},
    )
