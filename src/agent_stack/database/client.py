"""Async Cosmos DB client initialization."""

from __future__ import annotations

from azure.cosmos.aio import CosmosClient as AzureCosmosClient
from azure.cosmos.aio import DatabaseProxy

from agent_stack.config import CosmosConfig


class CosmosClient:
    """Manages the async Cosmos DB client and database reference."""

    def __init__(self, config: CosmosConfig) -> None:
        self._config = config
        self._client: AzureCosmosClient | None = None
        self._database: DatabaseProxy | None = None

    async def initialize(self) -> None:
        """Create the client and obtain a database reference."""
        self._client = AzureCosmosClient(self._config.endpoint, credential=self._config.key)
        self._database = self._client.get_database_client(self._config.database)

    async def close(self) -> None:
        """Close the underlying client."""
        if self._client:
            await self._client.close()
            self._client = None
            self._database = None

    @property
    def database(self) -> DatabaseProxy:
        if self._database is None:
            raise RuntimeError("CosmosClient not initialized — call initialize() first")
        return self._database
