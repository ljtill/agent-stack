"""Tests for worker Service Bus command consumption."""

from __future__ import annotations

from unittest.mock import AsyncMock

from curate_common.config import ServiceBusConfig
from curate_common.events import EventEnvelope
from curate_worker.events import ServiceBusCommandConsumer


def _servicebus_config() -> ServiceBusConfig:
    """Create a minimal Service Bus config for command-consumer tests."""
    return ServiceBusConfig(
        connection_string="Endpoint=sb://test.servicebus.windows.net/;SharedAccessKeyName=key;SharedAccessKey=abc",
        topic_name="pipeline-events",
        subscription_name="web-consumer",
        worker_subscription_name="worker-consumer",
    )


async def test_handle_event_ignores_non_command_events() -> None:
    """Non-command events are ignored by the worker command consumer."""
    callback = AsyncMock()
    consumer = ServiceBusCommandConsumer(_servicebus_config(), callback)
    handled = await consumer._handle_event(  # noqa: SLF001
        EventEnvelope(event="agent-run-complete", data={"id": "run-1"}),
        message_id="msg-1",
    )
    assert handled is False
    callback.assert_not_awaited()


async def test_handle_event_dispatches_publish_request() -> None:
    """Publish commands dispatch to the publish handler."""
    callback = AsyncMock()
    consumer = ServiceBusCommandConsumer(_servicebus_config(), callback)
    handled = await consumer._handle_event(  # noqa: SLF001
        EventEnvelope(
            event="publish-request",
            data={"edition_id": "ed-1", "request_id": "req-1"},
        ),
        message_id="msg-1",
    )
    assert handled is True
    callback.assert_awaited_once_with("ed-1")


async def test_handle_event_deduplicates_publish_request_ids() -> None:
    """Duplicate publish commands with same request id are ignored."""
    callback = AsyncMock()
    consumer = ServiceBusCommandConsumer(_servicebus_config(), callback)
    envelope = EventEnvelope(
        event="publish-request",
        data={"edition_id": "ed-1", "request_id": "req-1"},
    )
    await consumer._handle_event(envelope, message_id="msg-1")  # noqa: SLF001
    await consumer._handle_event(envelope, message_id="msg-2")  # noqa: SLF001
    callback.assert_awaited_once_with("ed-1")


async def test_handle_event_ignores_invalid_publish_request_payload() -> None:
    """Invalid publish command payloads are ignored without dispatch."""
    callback = AsyncMock()
    consumer = ServiceBusCommandConsumer(_servicebus_config(), callback)
    handled = await consumer._handle_event(  # noqa: SLF001
        EventEnvelope(event="publish-request", data={"request_id": "req-1"}),
        message_id="msg-1",
    )
    assert handled is True
    callback.assert_not_awaited()
