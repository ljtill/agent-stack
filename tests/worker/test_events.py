"""Tests for worker Service Bus command consumption."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from curate_common.config import ServiceBusConfig
from curate_common.events import EventEnvelope
from curate_worker.events import ServiceBusCommandConsumer

_EXPECTED_RETRY_ATTEMPTS = 2
_TRANSIENT_ERROR = "transient"


def _servicebus_config() -> ServiceBusConfig:
    """Create a minimal Service Bus config for command-consumer tests."""
    return ServiceBusConfig(
        connection_string="Endpoint=sb://test.servicebus.windows.net/;SharedAccessKeyName=key;SharedAccessKey=abc",
        topic_name="pipeline-events",
        command_topic_name="pipeline-commands",
        event_topic_name="pipeline-events",
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


async def test_consume_uses_command_topic_subscription() -> None:
    """Command consumer listens on the configured command topic/subscription."""
    callback = AsyncMock()
    config = _servicebus_config()
    consumer = ServiceBusCommandConsumer(config, callback)
    receiver = MagicMock()
    receiver.__aenter__ = AsyncMock(return_value=receiver)
    receiver.__aexit__ = AsyncMock(return_value=False)

    async def _receive_messages(*_: object, **__: object) -> list[object]:
        consumer._running = False  # noqa: SLF001
        return []

    receiver.receive_messages = AsyncMock(side_effect=_receive_messages)
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    client.get_subscription_receiver.return_value = receiver

    with patch("azure.servicebus.aio.ServiceBusClient") as servicebus_cls:
        servicebus_cls.from_connection_string.return_value = client
        consumer._running = True  # noqa: SLF001
        await consumer._consume_once()  # noqa: SLF001

    client.get_subscription_receiver.assert_called_once_with(
        topic_name=config.command_topic_name,
        subscription_name=config.worker_subscription_name,
    )


async def test_consume_retries_after_transient_error() -> None:
    """Transient consumer failures trigger reconnect and continue consuming."""
    callback = AsyncMock()
    consumer = ServiceBusCommandConsumer(_servicebus_config(), callback)
    attempts = 0

    async def _consume_once() -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError(_TRANSIENT_ERROR)
        consumer._running = False  # noqa: SLF001

    with (
        patch.object(
            consumer,
            "_consume_once",
            new=AsyncMock(side_effect=_consume_once),
        ),
        patch("curate_worker.events.asyncio.sleep", new=AsyncMock()) as sleep_mock,
        patch("curate_worker.events.secrets.randbelow", return_value=0),
    ):
        consumer._running = True  # noqa: SLF001
        await consumer._consume()  # noqa: SLF001

    assert attempts == _EXPECTED_RETRY_ATTEMPTS
    sleep_mock.assert_awaited_once_with(1.0)
