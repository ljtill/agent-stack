"""Edition document model — living documents refined by agents."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field

from agent_stack.models.base import DocumentBase


class EditionStatus(StrEnum):
    CREATED = "created"
    DRAFTING = "drafting"
    IN_REVIEW = "in_review"
    PUBLISHED = "published"


class Edition(DocumentBase):
    """A newsletter edition continuously refined by the agent pipeline."""

    status: EditionStatus = EditionStatus.CREATED
    content: dict = Field(default_factory=dict)
    link_ids: list[str] = Field(default_factory=list)
    published_at: datetime | None = None
