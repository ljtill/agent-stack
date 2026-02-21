"""Tests for PublishAgent tool methods."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_stack.agents.publish import PublishAgent
from agent_stack.models.edition import Edition, EditionStatus


@pytest.fixture
def editions_repo():
    return AsyncMock()


@pytest.fixture
def publish_agent(editions_repo):
    client = MagicMock()
    with patch("agent_stack.agents.publish.Agent"):
        return PublishAgent(client, editions_repo, render_fn=AsyncMock(), upload_fn=AsyncMock())


@pytest.fixture
def publish_agent_no_fns(editions_repo):
    client = MagicMock()
    with patch("agent_stack.agents.publish.Agent"):
        return PublishAgent(client, editions_repo)


@pytest.mark.asyncio
async def test_render_and_upload_calls_functions(publish_agent, editions_repo):
    edition = Edition(id="ed-1", content={"title": "Test"})
    editions_repo.get.return_value = edition
    publish_agent._render_fn.return_value = "<html>test</html>"

    result = json.loads(await publish_agent._render_and_upload("ed-1"))

    assert result["status"] == "uploaded"
    publish_agent._render_fn.assert_called_once_with(edition)
    publish_agent._upload_fn.assert_called_once_with("ed-1", "<html>test</html>")


@pytest.mark.asyncio
async def test_render_and_upload_skips_without_functions(publish_agent_no_fns, editions_repo):
    edition = Edition(id="ed-1", content={"title": "Test"})
    editions_repo.get.return_value = edition

    result = json.loads(await publish_agent_no_fns._render_and_upload("ed-1"))
    assert result["status"] == "skipped"


@pytest.mark.asyncio
async def test_render_and_upload_edition_not_found(publish_agent, editions_repo):
    editions_repo.get.return_value = None
    result = json.loads(await publish_agent._render_and_upload("missing"))
    assert "error" in result


@pytest.mark.asyncio
async def test_mark_published_updates_status(publish_agent, editions_repo):
    edition = Edition(id="ed-1", content={}, status=EditionStatus.IN_REVIEW)
    editions_repo.get.return_value = edition

    result = json.loads(await publish_agent._mark_published("ed-1"))

    assert result["status"] == "published"
    assert edition.status == EditionStatus.PUBLISHED
    assert edition.published_at is not None
    editions_repo.update.assert_called_once()


@pytest.mark.asyncio
async def test_mark_published_edition_not_found(publish_agent, editions_repo):
    editions_repo.get.return_value = None
    result = json.loads(await publish_agent._mark_published("missing"))
    assert "error" in result
