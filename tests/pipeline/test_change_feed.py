"""Tests for ChangeFeedProcessor."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from agent_stack.pipeline.change_feed import ChangeFeedProcessor


@pytest.fixture
def mock_orchestrator():
    orch = AsyncMock()
    orch.handle_link_change = AsyncMock()
    orch.handle_feedback_change = AsyncMock()
    return orch


@pytest.fixture
def processor(mock_orchestrator):
    db = MagicMock()
    db.get_container_client = MagicMock(return_value=MagicMock())
    return ChangeFeedProcessor(db, mock_orchestrator)


@pytest.mark.asyncio
async def test_process_feed_delegates_to_handler(processor):
    """Test that _process_feed calls the handler for each change item."""
    items = [{"id": "link-1"}, {"id": "link-2"}]

    async def mock_change_feed(**kwargs):
        for item in items:
            yield item

    container = MagicMock()
    container.query_items_change_feed = mock_change_feed
    handler = AsyncMock()

    await processor._process_feed(container, None, handler)

    assert handler.call_count == 2
    handler.assert_any_call({"id": "link-1"})
    handler.assert_any_call({"id": "link-2"})


@pytest.mark.asyncio
async def test_process_feed_passes_continuation_token(processor):
    """Test that continuation token is passed to change feed query."""
    calls = []

    async def mock_change_feed(**kwargs):
        calls.append(kwargs)
        return
        yield  # make it an async generator

    container = MagicMock()
    container.query_items_change_feed = mock_change_feed

    await processor._process_feed(container, "token-123", AsyncMock())

    assert calls[0]["continuation"] == "token-123"


@pytest.mark.asyncio
async def test_process_feed_no_token_on_first_call(processor):
    """Test that no continuation key is passed on the first call."""
    calls = []

    async def mock_change_feed(**kwargs):
        calls.append(kwargs)
        return
        yield

    container = MagicMock()
    container.query_items_change_feed = mock_change_feed

    await processor._process_feed(container, None, AsyncMock())

    assert "continuation" not in calls[0]


@pytest.mark.asyncio
async def test_process_feed_handles_handler_error(processor):
    """Test that errors in handler don't stop processing remaining items."""
    items = [{"id": "link-1"}, {"id": "link-2"}]

    async def mock_change_feed(**kwargs):
        for item in items:
            yield item

    container = MagicMock()
    container.query_items_change_feed = mock_change_feed
    handler = AsyncMock(side_effect=[RuntimeError("fail"), None])

    # Should not raise — errors are caught per item
    await processor._process_feed(container, None, handler)
    assert handler.call_count == 2


@pytest.mark.asyncio
async def test_start_creates_background_task(processor):
    await processor.start()
    assert processor._running is True
    assert processor._task is not None
    await processor.stop()


@pytest.mark.asyncio
async def test_stop_cancels_task(processor):
    await processor.start()
    await processor.stop()
    assert processor._running is False
