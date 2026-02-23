"""Tests for RevisionRepository custom query methods."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from curate_common.database.repositories.revisions import RevisionRepository
from curate_common.models.revision import Revision, RevisionSource

_EXPECTED_REVISION_COUNT = 2


class TestRevisionRepository:
    """Test the Revision Repository."""

    @pytest.fixture
    def repo(self) -> RevisionRepository:
        """Create a repo for testing."""
        mock_db = MagicMock()
        mock_container = AsyncMock()
        mock_db.get_container_client.return_value = mock_container
        return RevisionRepository(mock_db)

    async def test_list_by_edition(self, repo: RevisionRepository) -> None:
        """Verify list by edition returns ordered results."""
        revisions = [
            Revision(edition_id="ed-1", sequence=1, source=RevisionSource.DRAFT),
            Revision(edition_id="ed-1", sequence=2, source=RevisionSource.EDIT),
        ]
        repo.query = AsyncMock(return_value=revisions)

        result = await repo.list_by_edition("ed-1")

        assert len(result) == _EXPECTED_REVISION_COUNT
        repo.query.assert_called_once()
        query_str = repo.query.call_args[0][0]
        assert "@edition_id" in query_str
        assert "ORDER BY c.sequence ASC" in query_str

    async def test_get_latest_returns_first(self, repo: RevisionRepository) -> None:
        """Verify get latest returns first result."""
        rev = Revision(edition_id="ed-1", sequence=3, source=RevisionSource.EDIT)
        repo.query = AsyncMock(return_value=[rev])

        result = await repo.get_latest("ed-1")

        assert result == rev

    async def test_get_latest_returns_none_when_empty(
        self, repo: RevisionRepository
    ) -> None:
        """Verify get latest returns none when no revisions exist."""
        repo.query = AsyncMock(return_value=[])

        result = await repo.get_latest("ed-1")

        assert result is None
