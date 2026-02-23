"""Tests for web Service Bus event consumer resilience and wiring."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from curate_common.config import ServiceBusConfig
from curate_web.events.consumer import ServiceBusConsumer

_EXPECTED_RETRY_ATTEMPTS = 2
_TRANSIENT_ERROR = "transient"


def _servicebus_config() -> ServiceBusConfig:
    """Create a minimal Service Bus config for web consumer tests."""
    return ServiceBusConfig(
        connection_string="Endpoint=sb://test.servicebus.windows.net/;SharedAccessKeyName=key;SharedAccessKey=abc",
        topic_name="pipeline-events",
        command_topic_name="pipeline-commands",
        event_topic_name="pipeline-events",
        subscription_name="web-consumer",
        worker_subscription_name="worker-consumer",
    )


async def test_consume_once_uses_event_topic_subscription() -> None:
    """Web consumer listens on the configured events topic/subscription."""
    config = _servicebus_config()
    event_manager = MagicMock()
    event_manager.publish = AsyncMock()
    consumer = ServiceBusConsumer(config, event_manager)
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
        topic_name=config.event_topic_name,
        subscription_name=config.subscription_name,
    )


async def test_consume_retries_after_transient_error() -> None:
    """Transient consumer failures trigger reconnect and continue consuming."""
    event_manager = MagicMock()
    event_manager.publish = AsyncMock()
    consumer = ServiceBusConsumer(_servicebus_config(), event_manager)
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
        patch(
            "curate_web.events.consumer.asyncio.sleep", new=AsyncMock()
        ) as sleep_mock,
        patch("curate_web.events.consumer.secrets.randbelow", return_value=0),
    ):
        consumer._running = True  # noqa: SLF001
        await consumer._consume()  # noqa: SLF001

    assert attempts == _EXPECTED_RETRY_ATTEMPTS
    sleep_mock.assert_awaited_once_with(1.0)
