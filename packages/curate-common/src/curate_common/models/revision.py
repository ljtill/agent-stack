"""Revision document model — immutable content snapshots for editions."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from curate_common.models.base import DocumentBase


class RevisionSource(StrEnum):
    """Enumerate the event types that create a revision."""

    DRAFT = "draft"
    EDIT = "edit"
    REVERT = "revert"
    PUBLISH = "publish"


class Revision(DocumentBase):
    """An immutable snapshot of edition content at a point in time."""

    edition_id: str
    sequence: int
    source: RevisionSource
    trigger_id: str | None = None
    content: dict = Field(default_factory=dict)
    summary: str = ""
