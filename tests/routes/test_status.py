"""Tests for the status route."""

from unittest.mock import AsyncMock, MagicMock, patch

from agent_stack.routes.status import status


class TestStatusRoute:
    """Test the Status Route."""

    async def test_renders_status_page(self) -> None:
        """Verify renders status page."""
        request = MagicMock()
        request.app.state.cosmos = MagicMock()
        request.app.state.settings = MagicMock()
        request.app.state.processor = MagicMock()
        request.app.state.storage = MagicMock()
        request.app.state.templates = MagicMock()

        mock_results = [{"name": "cosmos", "status": "healthy"}]

        with (
            patch("agent_stack.routes.status.create_chat_client"),
            patch(
                "agent_stack.routes.status.check_all",
                new_callable=AsyncMock,
                return_value=mock_results,
            ),
        ):
            await status(request)

        request.app.state.templates.TemplateResponse.assert_called_once()
        call_args = request.app.state.templates.TemplateResponse.call_args
        assert call_args[0][0] == "status.html"
        assert call_args[0][1]["checks"] == mock_results
