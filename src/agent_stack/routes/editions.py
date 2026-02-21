"""Editions routes — list, create, view detail, publish."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from agent_stack.database.repositories.editions import EditionRepository
from agent_stack.database.repositories.links import LinkRepository
from agent_stack.models.edition import Edition, EditionStatus

router = APIRouter(prefix="/editions", tags=["editions"])


@router.get("/", response_class=HTMLResponse)
async def list_editions(request: Request):
    """Render the editions list page."""
    templates = request.app.state.templates
    cosmos = request.app.state.cosmos
    repo = EditionRepository(cosmos.database)
    editions = await repo.list_all()
    return templates.TemplateResponse(
        "editions.html",
        {"request": request, "editions": editions},
    )


@router.post("/")
async def create_edition(request: Request):
    """Create a new edition."""
    cosmos = request.app.state.cosmos
    repo = EditionRepository(cosmos.database)
    edition = Edition(content={"title": "", "sections": []})
    await repo.create(edition)
    return RedirectResponse("/editions/", status_code=303)


@router.get("/{edition_id}", response_class=HTMLResponse)
async def edition_detail(request: Request, edition_id: str):
    """Render the edition detail page."""
    templates = request.app.state.templates
    cosmos = request.app.state.cosmos
    editions_repo = EditionRepository(cosmos.database)
    links_repo = LinkRepository(cosmos.database)

    edition = await editions_repo.get(edition_id, edition_id)
    links = await links_repo.get_by_edition(edition_id) if edition else []

    return templates.TemplateResponse(
        "edition_detail.html",
        {"request": request, "edition": edition, "links": links},
    )


@router.post("/{edition_id}/publish")
async def publish_edition(request: Request, edition_id: str):
    """Trigger the publish pipeline for an edition."""
    cosmos = request.app.state.cosmos
    repo = EditionRepository(cosmos.database)
    edition = await repo.get(edition_id, edition_id)
    if edition:
        edition.status = EditionStatus.IN_REVIEW
        await repo.update(edition, edition_id)
    return RedirectResponse(f"/editions/{edition_id}", status_code=303)