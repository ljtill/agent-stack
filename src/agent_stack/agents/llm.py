"""Azure OpenAI / Microsoft Foundry chat client factory."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from agent_framework.azure import AzureOpenAIChatClient
from azure.identity import DefaultAzureCredential

if TYPE_CHECKING:
    from agent_stack.config import OpenAIConfig

logger = logging.getLogger(__name__)


def create_chat_client(config: OpenAIConfig) -> AzureOpenAIChatClient:
    """Create an AzureOpenAIChatClient authenticated via DefaultAzureCredential.

    Uses Azure CLI credentials in local development and managed identity
    in deployed environments.
    """
    logger.info(
        "Chat client created — endpoint=%s deployment=%s",
        config.endpoint,
        config.deployment,
    )
    return AzureOpenAIChatClient(
        endpoint=config.endpoint,
        deployment_name=config.deployment,
        credential=DefaultAzureCredential(),
    )
