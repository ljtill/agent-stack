"""Repository for the links container (partitioned by /id)."""

from __future__ import annotations

from typing import cast

from curate_common.database.repositories.base import BaseRepository
from curate_common.models.link import Link, LinkStatus


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
