"""Tests for the static site renderer."""

from datetime import UTC, datetime

import pytest

from agent_stack.models.edition import Edition, EditionStatus
from agent_stack.storage.renderer import NEWSLETTER_TEMPLATES


def test_newsletter_templates_dir_exists():
    assert NEWSLETTER_TEMPLATES.exists()
    assert (NEWSLETTER_TEMPLATES / "edition.html").exists()
    assert (NEWSLETTER_TEMPLATES / "index.html").exists()


@pytest.mark.asyncio
async def test_render_edition_produces_html():
    """Test that edition rendering produces valid HTML without needing a real DB or storage."""
    from jinja2 import Environment, FileSystemLoader

    env = Environment(loader=FileSystemLoader(str(NEWSLETTER_TEMPLATES)), autoescape=True)
    template = env.get_template("edition.html")

    edition = Edition(
        status=EditionStatus.PUBLISHED,
        content={
            "title": "Test Edition",
            "sections": [
                {"title": "Section One", "body": "Some content here."},
                {"title": "Section Two", "body": "More content.", "source_url": "https://example.com"},
            ],
        },
        published_at=datetime(2025, 1, 15, tzinfo=UTC),
    )

    html = template.render(edition=edition)
    assert "<!DOCTYPE html>" in html
    assert "Test Edition" in html
    assert "Section One" in html
    assert "Some content here." in html
    assert "https://example.com" in html
    assert "January 15, 2025" in html


@pytest.mark.asyncio
async def test_render_index_produces_html():
    """Test that index rendering produces valid HTML."""
    from jinja2 import Environment, FileSystemLoader

    env = Environment(loader=FileSystemLoader(str(NEWSLETTER_TEMPLATES)), autoescape=True)
    template = env.get_template("index.html")

    editions = [
        Edition(
            id="ed-1",
            status=EditionStatus.PUBLISHED,
            content={"title": "First Edition"},
            published_at=datetime(2025, 1, 15, tzinfo=UTC),
        ),
        Edition(
            id="ed-2",
            status=EditionStatus.PUBLISHED,
            content={"title": "Second Edition"},
            published_at=datetime(2025, 2, 1, tzinfo=UTC),
        ),
    ]

    html = template.render(editions=editions)
    assert "<!DOCTYPE html>" in html
    assert "First Edition" in html
    assert "Second Edition" in html
    assert "The Agent Stack" in html
