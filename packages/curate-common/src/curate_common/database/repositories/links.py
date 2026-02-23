"""Repository for the links container (partitioned by /id)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, cast

from azure.core import MatchConditions
from azure.cosmos.exceptions import CosmosHttpResponseError

from curate_common.database.repositories.base import BaseRepository
from curate_common.models.link import Link, LinkStatus

_CLAIM_FIELD = "processing_claimed_at"
_HTTP_PRECONDITION_FAILED = 412
_CLAIM_TTL = timedelta(minutes=15)


def _is_active_claim(claimed_at_raw: object, *, now: datetime) -> bool:
    """Return True when a durable claim marker is still active."""
    if isinstance(claimed_at_raw, str):
        try:
            claimed_at = datetime.fromisoformat(claimed_at_raw)
        except ValueError:
            return False
        if claimed_at.tzinfo is None:
            claimed_at = claimed_at.replace(tzinfo=UTC)
        return now - claimed_at < _CLAIM_TTL
    return claimed_at_raw is not None


class LinkRepository(BaseRepository[Link]):
    """Provide data access for the links container."""

    container_name = "links"
    model_class = Link

    async def list_all(self) -> list[Link]:
        """Fetch all active links across all editions."""
        return await self.query(
            "SELECT * FROM c WHERE NOT IS_DEFINED(c.deleted_at)"
            " ORDER BY c.created_at DESC",
        )

    async def list_unattached(self) -> list[Link]:
        """Fetch links not yet associated with any edition."""
        return await self.query(
            "SELECT * FROM c WHERE NOT IS_DEFINED(c.edition_id)"
            " AND NOT IS_DEFINED(c.deleted_at)"
            " ORDER BY c.created_at DESC",
        )

    async def get_by_edition(self, edition_id: str) -> list[Link]:
        """Fetch all active links for a given edition."""
        return await self.query(
            "SELECT * FROM c WHERE c.edition_id = @edition_id"
            " AND NOT IS_DEFINED(c.deleted_at)",
            [{"name": "@edition_id", "value": edition_id}],
        )

    async def get_by_status(self, edition_id: str, status: LinkStatus) -> list[Link]:
        """Fetch links with a specific status within an edition."""
        return await self.query(
            "SELECT * FROM c WHERE c.edition_id = @edition_id"
            " AND c.status = @status"
            " AND NOT IS_DEFINED(c.deleted_at)",
            [
                {"name": "@edition_id", "value": edition_id},
                {"name": "@status", "value": status.value},
            ],
        )

    async def claim_submitted(self, link_id: str) -> Link | None:
        """Atomically claim a submitted link for processing."""
        try:
            data = cast(
                "dict[str, Any]",
                await self._container.read_item(item=link_id, partition_key=link_id),
            )
        except CosmosHttpResponseError:
            return None

        now = datetime.now(UTC)

        if (
            data.get("deleted_at") is not None
            or data.get("edition_id") is None
            or data.get("status") != LinkStatus.SUBMITTED.value
            or _is_active_claim(data.get(_CLAIM_FIELD), now=now)
        ):
            return None
        etag = data.get("_etag")
        if not isinstance(etag, str):
            return None

        link = self.model_class.model_validate(data)
        body = {
            **link.model_dump(mode="json", exclude_none=True),
            _CLAIM_FIELD: now.isoformat(),
        }

        try:
            await self._container.replace_item(
                item=link.id,
                body=body,
                etag=etag,
                match_condition=MatchConditions.IfNotModified,
            )
        except CosmosHttpResponseError as exc:
            if exc.status_code == _HTTP_PRECONDITION_FAILED:
                return None
            raise

        return link

    async def associate(self, link: Link, edition_id: str) -> Link:
        """Associate a link with an edition."""
        link.edition_id = edition_id
        link.status = LinkStatus.SUBMITTED
        return await self.update(link, link.id)

    async def disassociate(self, link: Link) -> Link:
        """Remove a link's association with an edition."""
        link.edition_id = None
        link.status = LinkStatus.SUBMITTED
        link.title = None
        link.content = None
        link.review = None
        return await self.update(link, link.id)

    async def count_all(self) -> int:
        """Return the total number of active links across all editions."""
        total = 0
        async for item in self._container.query_items(
            "SELECT VALUE COUNT(1) FROM c WHERE NOT IS_DEFINED(c.deleted_at)",
        ):
            total = cast("int", item)
        return total
