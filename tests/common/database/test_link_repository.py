"""Tests for LinkRepository custom query methods."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from azure.core import MatchConditions
from azure.cosmos.exceptions import CosmosHttpResponseError

from curate_common.database.repositories.links import LinkRepository
from curate_common.models.link import Link, LinkStatus


class TestLinkRepository:
    """Test the Link Repository."""

    @pytest.fixture
    def repo(self) -> LinkRepository:
        """Create a repo for testing."""
        mock_db = MagicMock()
        mock_container = AsyncMock()
        mock_db.get_container_client.return_value = mock_container
        return LinkRepository(mock_db)

    async def test_get_by_edition(self, repo: LinkRepository) -> None:
        """Verify get_by_edition returns links for a given edition."""
        link = Link(id="link-1", url="https://example.com", edition_id="ed-1")
        repo.query = AsyncMock(return_value=[link])

        result = await repo.get_by_edition("ed-1")

        assert len(result) == 1
        assert result[0].id == "link-1"
        call_args = repo.query.call_args
        assert "@edition_id" in call_args[0][0]

    async def test_get_by_edition_empty(self, repo: LinkRepository) -> None:
        """Verify get_by_edition returns empty list when no links found."""
        repo.query = AsyncMock(return_value=[])

        result = await repo.get_by_edition("ed-missing")

        assert result == []

    async def test_get_by_status(self, repo: LinkRepository) -> None:
        """Verify get_by_status filters by edition and status."""
        link = Link(
            id="link-1",
            url="https://example.com",
            edition_id="ed-1",
            status=LinkStatus.REVIEWED,
        )
        repo.query = AsyncMock(return_value=[link])

        result = await repo.get_by_status("ed-1", LinkStatus.REVIEWED)

        assert len(result) == 1
        call_args = repo.query.call_args
        assert "@edition_id" in call_args[0][0]
        assert "@status" in call_args[0][0]
        params = call_args[0][1]
        status_param = next(p for p in params if p["name"] == "@status")
        assert status_param["value"] == LinkStatus.REVIEWED.value

    async def test_get_by_status_empty(self, repo: LinkRepository) -> None:
        """Verify get_by_status returns empty list when no matching links."""
        repo.query = AsyncMock(return_value=[])

        result = await repo.get_by_status("ed-1", LinkStatus.SUBMITTED)

        assert result == []

    async def test_claim_submitted_uses_etag_match(self, repo: LinkRepository) -> None:
        """Verify submitted-link claims use optimistic concurrency."""
        repo._container.read_item.return_value = {  # noqa: SLF001
            "id": "link-1",
            "url": "https://example.com",
            "edition_id": "ed-1",
            "status": "submitted",
            "_etag": "etag-1",
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
        }

        claimed = await repo.claim_submitted("link-1")

        assert claimed is not None
        assert claimed.id == "link-1"
        kwargs = repo._container.replace_item.call_args.kwargs  # noqa: SLF001
        assert kwargs["etag"] == "etag-1"
        assert kwargs["match_condition"] is MatchConditions.IfNotModified
        assert kwargs["body"]["processing_claimed_at"]

    async def test_claim_submitted_returns_none_on_status_mismatch(
        self, repo: LinkRepository
    ) -> None:
        """Verify non-submitted links are not claimed."""
        repo._container.read_item.return_value = {  # noqa: SLF001
            "id": "link-1",
            "url": "https://example.com",
            "edition_id": "ed-1",
            "status": "reviewed",
            "_etag": "etag-1",
        }

        claimed = await repo.claim_submitted("link-1")

        assert claimed is None
        repo._container.replace_item.assert_not_called()  # noqa: SLF001

    async def test_claim_submitted_returns_none_when_already_claimed(
        self, repo: LinkRepository
    ) -> None:
        """Verify claim attempts skip links that already have a durable claim."""
        repo._container.read_item.return_value = {  # noqa: SLF001
            "id": "link-1",
            "url": "https://example.com",
            "edition_id": "ed-1",
            "status": "submitted",
            "_etag": "etag-1",
            "processing_claimed_at": datetime.now(UTC).isoformat(),
        }

        claimed = await repo.claim_submitted("link-1")

        assert claimed is None
        repo._container.replace_item.assert_not_called()  # noqa: SLF001

    async def test_claim_submitted_reclaims_stale_claim(
        self, repo: LinkRepository
    ) -> None:
        """Verify stale claim markers can be reclaimed after TTL."""
        stale_claim = (datetime.now(UTC) - timedelta(minutes=20)).isoformat()
        repo._container.read_item.return_value = {  # noqa: SLF001
            "id": "link-1",
            "url": "https://example.com",
            "edition_id": "ed-1",
            "status": "submitted",
            "_etag": "etag-1",
            "processing_claimed_at": stale_claim,
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
        }

        claimed = await repo.claim_submitted("link-1")

        assert claimed is not None
        repo._container.replace_item.assert_called_once()  # noqa: SLF001

    async def test_claim_submitted_returns_none_on_conflict(
        self, repo: LinkRepository
    ) -> None:
        """Verify etag conflicts are treated as claim misses."""
        repo._container.read_item.return_value = {  # noqa: SLF001
            "id": "link-1",
            "url": "https://example.com",
            "edition_id": "ed-1",
            "status": "submitted",
            "_etag": "etag-1",
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
        }
        repo._container.replace_item.side_effect = CosmosHttpResponseError(  # noqa: SLF001
            status_code=412,
            message="Precondition failed",
        )

        claimed = await repo.claim_submitted("link-1")

        assert claimed is None
