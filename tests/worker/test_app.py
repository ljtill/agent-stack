"""Tests for worker app observability initialization."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

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
