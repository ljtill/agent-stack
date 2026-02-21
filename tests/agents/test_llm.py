"""Tests for the LLM client factory."""

from unittest.mock import patch

import pytest

from agent_stack.config import OpenAIConfig


@pytest.mark.unit
class TestCreateChatClient:
    """Test the Create Chat Client."""

    def test_creates_client_with_api_key(self, openai_config: OpenAIConfig) -> None:
        """Verify creates client with api key."""
        with patch("agent_stack.agents.llm.AzureOpenAIChatClient") as MockClient:
            from agent_stack.agents.llm import create_chat_client

            client = create_chat_client(openai_config, use_key="test-api-key")

            MockClient.assert_called_once_with(
                endpoint=openai_config.endpoint,
                deployment_name=openai_config.deployment,
                api_key="test-api-key",
            )
            assert client == MockClient.return_value

    def test_creates_client_with_managed_identity(self, openai_config: OpenAIConfig) -> None:
        """Verify creates client with managed identity."""
        with (
            patch("agent_stack.agents.llm.AzureOpenAIChatClient") as MockClient,
            patch("agent_stack.agents.llm.DefaultAzureCredential") as MockCred,
        ):
            from agent_stack.agents.llm import create_chat_client

            client = create_chat_client(openai_config)

            MockClient.assert_called_once_with(
                endpoint=openai_config.endpoint,
                deployment_name=openai_config.deployment,
                credential=MockCred.return_value,
            )
            assert client == MockClient.return_value
