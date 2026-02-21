"""Tests for ReviewAgent tool methods."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_stack.agents.review import ReviewAgent
from agent_stack.models.link import Link, LinkStatus


@pytest.fixture
def links_repo():
    return AsyncMock()


@pytest.fixture
def review_agent(links_repo):
    client = MagicMock()
    with patch("agent_stack.agents.review.Agent"):
        return ReviewAgent(client, links_repo)


@pytest.mark.asyncio
async def test_get_link_content_returns_json(review_agent, links_repo):
    link = Link(id="link-1", url="https://example.com", edition_id="ed-1", title="Title", content="Body text")
    links_repo.get.return_value = link

    result = json.loads(await review_agent._get_link_content("link-1", "ed-1"))

    assert result["title"] == "Title"
    assert result["content"] == "Body text"
    assert result["url"] == "https://example.com"


@pytest.mark.asyncio
async def test_get_link_content_not_found(review_agent, links_repo):
    links_repo.get.return_value = None
    result = json.loads(await review_agent._get_link_content("missing", "ed-1"))
    assert "error" in result


@pytest.mark.asyncio
async def test_save_review_updates_link(review_agent, links_repo):
    link = Link(id="link-1", url="https://example.com", edition_id="ed-1")
    links_repo.get.return_value = link

    insights = json.dumps(["insight1", "insight2"])
    result = json.loads(await review_agent._save_review("link-1", "ed-1", insights, "AI/ML", 8, "Highly relevant"))

    assert result["status"] == "reviewed"
    assert link.status == LinkStatus.REVIEWED
    assert link.review["category"] == "AI/ML"
    assert link.review["relevance_score"] == 8
    assert link.review["insights"] == ["insight1", "insight2"]
    links_repo.update.assert_called_once()


@pytest.mark.asyncio
async def test_save_review_link_not_found(review_agent, links_repo):
    links_repo.get.return_value = None
    result = json.loads(await review_agent._save_review("missing", "ed-1", "[]", "cat", 5, "justification"))
    assert "error" in result
