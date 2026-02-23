"""Tests for Revision model defaults and fields."""

import pytest

from curate_common.models.revision import Revision, RevisionSource


class TestRevisionModel:
    """Test the Revision document model."""

    def test_defaults(self) -> None:
        """Verify default field values on a new revision."""
        rev = Revision(edition_id="ed-1", sequence=1, source=RevisionSource.DRAFT)

        assert rev.edition_id == "ed-1"
        assert rev.sequence == 1
        assert rev.source == RevisionSource.DRAFT
        assert rev.trigger_id is None
        assert rev.content == {}
        assert rev.summary == ""
        assert rev.id is not None
        assert rev.created_at is not None
        assert rev.deleted_at is None

    def test_all_sources(self) -> None:
        """Verify all RevisionSource enum values exist."""
        assert RevisionSource.DRAFT == "draft"
        assert RevisionSource.EDIT == "edit"
        assert RevisionSource.REVERT == "revert"
        assert RevisionSource.PUBLISH == "publish"

    def test_with_content(self) -> None:
        """Verify revision stores content dict."""
        content = {"title": "Issue #1", "signals": [{"headline": "test"}]}
        rev = Revision(
            edition_id="ed-1",
            sequence=2,
            source=RevisionSource.EDIT,
            trigger_id="fb-1",
            content=content,
            summary="Applied feedback",
        )

        assert rev.content == content
        assert rev.trigger_id == "fb-1"
        assert rev.summary == "Applied feedback"

    @pytest.mark.parametrize("source", list(RevisionSource))
    def test_all_source_values_are_valid(self, source: RevisionSource) -> None:
        """Verify revision can be created with any source."""
        rev = Revision(edition_id="ed-1", sequence=1, source=source)
        assert rev.source == source
