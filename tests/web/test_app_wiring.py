"""Tests for web app runtime wiring and lifecycle event bridge setup."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from curate_web.app import create_app


def _settings(*, servicebus_connection_string: str) -> SimpleNamespace:
    """Create minimal settings for app factory and lifespan wiring tests."""
    return SimpleNamespace(
        app=SimpleNamespace(
            secret_key="",
            is_development=True,
            log_level="INFO",
            slow_request_ms=800,
            env="test",
        ),
        monitor=SimpleNamespace(connection_string=""),
        servicebus=SimpleNamespace(
            connection_string=servicebus_connection_string,
            topic_name="pipeline-events",
            command_topic_name="pipeline-commands",
            event_topic_name="pipeline-events",
            subscription_name="web-consumer",
            worker_subscription_name="worker-consumer",
        ),
    )


@pytest.mark.unit
def test_lifespan_wires_event_bridge_when_servicebus_configured() -> None:
    """Web lifespan wires publisher/consumer and realtime state when configured."""
    settings = _settings(
        servicebus_connection_string="Endpoint=sb://test.servicebus.windows.net/;SharedAccessKeyName=key;SharedAccessKey=abc",
    )
    cosmos = MagicMock()
    cosmos.database = MagicMock()
    cosmos.close = AsyncMock()
    storage_client = MagicMock()
    storage_client.close = AsyncMock()
    storage_components = SimpleNamespace(client=storage_client)
    memory_components = SimpleNamespace(service=None)
    consumer = MagicMock()
    consumer.start = AsyncMock()
    consumer.stop = AsyncMock()
    publisher = MagicMock()
    publisher.close = AsyncMock()

    with (
        patch("curate_web.app.load_settings", return_value=settings),
        patch("curate_web.app.configure_logging"),
        patch("curate_web.app.init_database", new=AsyncMock(return_value=cosmos)),
        patch(
            "curate_web.app.init_storage",
            new=AsyncMock(return_value=storage_components),
        ),
        patch(
            "curate_web.app.init_memory", new=AsyncMock(return_value=memory_components)
        ),
        patch(
            "curate_web.app.ServiceBusConsumer", return_value=consumer
        ) as consumer_cls,
        patch(
            "curate_web.app.ServiceBusPublisher", return_value=publisher
        ) as publisher_cls,
    ):
        app = create_app()
        with TestClient(app):
            assert app.state.realtime_enabled is True
            assert app.state.event_publisher is publisher
            assert app.state.event_consumer is consumer

    publisher_cls.assert_called_once_with(
        settings.servicebus,
        topic_name=settings.servicebus.command_topic_name,
    )
    consumer_cls.assert_called_once()
    consumer.start.assert_awaited_once()
    consumer.stop.assert_awaited_once()
    publisher.close.assert_awaited_once()


@pytest.mark.unit
def test_lifespan_skips_event_bridge_when_servicebus_not_configured() -> None:
    """Web lifespan skips publisher/consumer wiring when Service Bus is disabled."""
    settings = _settings(servicebus_connection_string="")
    cosmos = MagicMock()
    cosmos.database = MagicMock()
    cosmos.close = AsyncMock()
    storage_client = MagicMock()
    storage_client.close = AsyncMock()
    storage_components = SimpleNamespace(client=storage_client)
    memory_components = SimpleNamespace(service=None)

    with (
        patch("curate_web.app.load_settings", return_value=settings),
        patch("curate_web.app.configure_logging"),
        patch("curate_web.app.init_database", new=AsyncMock(return_value=cosmos)),
        patch(
            "curate_web.app.init_storage",
            new=AsyncMock(return_value=storage_components),
        ),
        patch(
            "curate_web.app.init_memory", new=AsyncMock(return_value=memory_components)
        ),
        patch("curate_web.app.ServiceBusConsumer") as consumer_cls,
        patch("curate_web.app.ServiceBusPublisher") as publisher_cls,
    ):
        app = create_app()
        with TestClient(app):
            assert app.state.realtime_enabled is False
            assert app.state.event_publisher is None
            assert app.state.event_consumer is None

    consumer_cls.assert_not_called()
    publisher_cls.assert_not_called()
