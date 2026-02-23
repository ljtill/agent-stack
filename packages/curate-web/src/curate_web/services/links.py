"""Link business logic — submit, associate, disassociate, retry, delete."""

from __future__ import annotations

from typing import TYPE_CHECKING

from curate_common.models.edition import EditionStatus
from curate_common.models.link import Link, LinkStatus

if TYPE_CHECKING:
    from curate_common.database.repositories.editions import EditionRepository
    from curate_common.database.repositories.links import LinkRepository
    from curate_common.models.edition import Edition


async def submit_link(
    url: str,
    links_repo: LinkRepository,
) -> Link:
    """Create a link in the global store (not associated with any edition)."""
    link = Link(url=url)
    await links_repo.create(link)
    return link


async def associate_link(
    link_id: str,
    edition_id: str,
    links_repo: LinkRepository,
    editions_repo: EditionRepository,
) -> Link | None:
    """Associate a store link with an edition. Returns None if rejected."""
    edition = await editions_repo.get(edition_id, edition_id)
    if not edition or edition.status == EditionStatus.PUBLISHED:
        return None

    link = await links_repo.get(link_id, link_id)
    if not link or link.edition_id is not None:
        return None

    link = await links_repo.associate(link, edition_id)

    if link.id not in edition.link_ids:
        edition.link_ids.append(link.id)
        await editions_repo.update(edition, edition_id)

    return link


async def disassociate_link(
    link_id: str,
    links_repo: LinkRepository,
    editions_repo: EditionRepository,
) -> Link | None:
    """Remove a link's association with its edition. Returns None if rejected."""
    link = await links_repo.get(link_id, link_id)
    if not link or link.edition_id is None:
        return None

    edition_id = link.edition_id
    edition = await editions_repo.get(edition_id, edition_id)
    if edition and edition.status == EditionStatus.PUBLISHED:
        return None

    link = await links_repo.disassociate(link)

    if edition and link_id in edition.link_ids:
        edition.link_ids.remove(link_id)
        await editions_repo.update(edition, edition_id)

    return link


async def retry_link(
    link_id: str,
    links_repo: LinkRepository,
) -> bool:
    """Reset a failed link to submitted. Returns True if reset succeeded."""
    link = await links_repo.get(link_id, link_id)
    if not link or link.status != LinkStatus.FAILED:
        return False

    link.status = LinkStatus.SUBMITTED
    link.title = None
    link.content = None
    await links_repo.update(link, link_id)
    return True


async def delete_link(
    link_id: str,
    links_repo: LinkRepository,
    editions_repo: EditionRepository,
) -> Edition | None:
    """Soft-delete a link and update its edition if associated.

    Returns the edition if applicable, None if link not found.
    """
    link = await links_repo.get(link_id, link_id)
    if not link:
        return None

    await links_repo.soft_delete(link, link_id)

    if link.edition_id:
        edition = await editions_repo.get(link.edition_id, link.edition_id)
        if edition:
            if link_id in edition.link_ids:
                edition.link_ids.remove(link_id)
                edition.content = {}
                await editions_repo.update(edition, link.edition_id)

                remaining = await links_repo.get_by_status(
                    link.edition_id, LinkStatus.DRAFTED
                )
                for remaining_link in remaining:
                    remaining_link.status = LinkStatus.REVIEWED
                    await links_repo.update(remaining_link, remaining_link.id)
            return edition
    return None
