"""Tests for dashboard route handler."""

from unittest.mock import MagicMock

import pytest

from agent_stack.routes.dashboard import dashboard


@pytest.mark.asyncio
async def test_dashboard_renders_template():
    request = MagicMock()
    request.app.state.templates = MagicMock()
    request.app.state.templates.TemplateResponse = MagicMock(return_value="<html>")

    await dashboard(request)

    request.app.state.templates.TemplateResponse.assert_called_once_with(
        "dashboard.html",
        {"request": request},
    )
