"""Tests for worker app observability initialization."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from curate_worker.app import run


@pytest.mark.unit
async def test_run_configures_azure_monitor_when_connection_string_set() -> None:
    """Azure Monitor and agent instrumentation are enabled."""
    mock_settings = MagicMock()
    mock_settings.monitor.connection_string = "InstrumentationKey=test-key"
    mock_settings.app.log_level = "INFO"
    mock_settings.app.is_development = True

    with (
        patch("curate_worker.app.load_settings", return_value=mock_settings),
        patch("curate_worker.app.configure_logging"),
        patch("curate_worker.app.configure_azure_monitor") as mock_configure_monitor,
        patch("curate_worker.app.create_resource") as mock_create_resource,
        patch(
            "curate_worker.app.enable_instrumentation"
        ) as mock_enable_instrumentation,
        patch("curate_worker.app.check_emulators", return_value=False),
    ):
        await run()

        mock_create_resource.assert_called_once_with(service_name="curate-worker")
        mock_configure_monitor.assert_called_once_with(
            connection_string="InstrumentationKey=test-key",
            resource=mock_create_resource.return_value,
        )
        mock_enable_instrumentation.assert_called_once()


@pytest.mark.unit
async def test_run_skips_azure_monitor_when_no_connection_string() -> None:
    """Azure Monitor is not configured when connection string is empty."""
    mock_settings = MagicMock()
    mock_settings.monitor.connection_string = ""
    mock_settings.app.log_level = "INFO"
    mock_settings.app.is_development = True

    with (
        patch("curate_worker.app.load_settings", return_value=mock_settings),
        patch("curate_worker.app.configure_logging"),
        patch("curate_worker.app.configure_azure_monitor") as mock_configure_monitor,
        patch(
            "curate_worker.app.enable_instrumentation"
        ) as mock_enable_instrumentation,
        patch("curate_worker.app.check_emulators", return_value=False),
    ):
        await run()

        mock_configure_monitor.assert_not_called()
        mock_enable_instrumentation.assert_not_called()


@pytest.mark.unit
async def test_run_wires_event_and_command_channels() -> None:
    """Worker uses events topic for publishing and command channel for consume."""
    settings = MagicMock()
    settings.monitor.connection_string = ""
    settings.app.log_level = "INFO"
    settings.app.is_development = True
    settings.servicebus.event_topic_name = "pipeline-events"
    cosmos = MagicMock()
    cosmos.database = MagicMock()
    cosmos.close = AsyncMock()
    storage = MagicMock()
    storage.close = AsyncMock()
    renderer = MagicMock()
    renderer.render_edition = MagicMock()
    processor = MagicMock()
    processor.stop = AsyncMock()
    processor.orchestrator.handle_publish = AsyncMock()
    command_consumer = MagicMock()
    command_consumer.start = AsyncMock()
    command_consumer.stop = AsyncMock()
    event_publisher = MagicMock()
    event_publisher.close = AsyncMock()
    stop_event = MagicMock()
    stop_event.wait = AsyncMock(return_value=None)
    loop = MagicMock()

    with (
        patch("curate_worker.app.load_settings", return_value=settings),
        patch("curate_worker.app.configure_logging"),
        patch("curate_worker.app.check_emulators", new=AsyncMock(return_value=True)),
        patch("curate_worker.app.init_database", new=AsyncMock(return_value=cosmos)),
        patch("curate_worker.app.init_chat_client", return_value=MagicMock()),
        patch(
            "curate_worker.app.init_storage",
            new=AsyncMock(return_value=(storage, renderer)),
        ),
        patch("curate_worker.app.init_memory", new=AsyncMock(return_value=[])),
        patch("curate_worker.app.init_pipeline", new=AsyncMock(return_value=processor)),
        patch(
            "curate_worker.app.ServiceBusPublisher",
            return_value=event_publisher,
        ) as publisher_cls,
        patch(
            "curate_worker.app.ServiceBusCommandConsumer",
            return_value=command_consumer,
        ) as command_consumer_cls,
        patch("curate_worker.app.asyncio.Event", return_value=stop_event),
        patch("curate_worker.app.asyncio.get_running_loop", return_value=loop),
    ):
        await run()

    publisher_cls.assert_called_once_with(
        settings.servicebus,
        topic_name=settings.servicebus.event_topic_name,
    )
    command_consumer_cls.assert_called_once_with(
        settings.servicebus,
        on_publish=processor.orchestrator.handle_publish,
    )
