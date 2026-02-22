"""Feedback routes — submit per-section editor comments."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from agent_stack.database.repositories.feedback import FeedbackRepository
from agent_stack.services import feedback as feedback_svc

router = APIRouter(tags=["feedback"])

logger = logging.getLogger(__name__)


@router.post("/editions/{edition_id}/feedback")
async def submit_feedback(
    request: Request,
    edition_id: str,
    section: Annotated[str, Form(...)],
    comment: Annotated[str, Form(...)],
) -> RedirectResponse:
    """Submit editor feedback for a specific section of an edition."""
    cosmos = request.app.state.cosmos
    repo = FeedbackRepository(cosmos.database)
    await feedback_svc.submit_feedback(edition_id, section, comment, repo)
    logger.info("Feedback submitted — edition=%s section=%s", edition_id, section)
    return RedirectResponse(f"/editions/{edition_id}", status_code=303)
