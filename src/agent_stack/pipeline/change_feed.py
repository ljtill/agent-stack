"""Cosmos DB change feed processor — listens for document changes and delegates to the orchestrator."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any

from azure.cosmos.aio import ContainerProxy, DatabaseProxy

from agent_stack.pipeline.orchestrator import PipelineOrchestrator

logger = logging.getLogger(__name__)


class ChangeFeedProcessor:
    """Consumes Cosmos DB change feed for links and feedback containers.

    Runs as a background task within the FastAPI lifespan, processing changes
    sequentially to avoid race conditions on the edition document.
    """

    def __init__(self, database: DatabaseProxy, orchestrator: PipelineOrchestrator) -> None:
        self._database = database
        self._orchestrator = orchestrator
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start polling the change feed in a background task."""
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("Change feed processor started")

    async def stop(self) -> None:
        """Stop the change feed processor gracefully."""
        self._running = False
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        logger.info("Change feed processor stopped")

    async def _poll_loop(self) -> None:
        """Continuously poll change feeds for links and feedback."""
        links_container: ContainerProxy = self._database.get_container_client("links")
        feedback_container: ContainerProxy = self._database.get_container_client("feedback")

        # Track continuation tokens per container
        links_token: str | None = None
        feedback_token: str | None = None

        while self._running:
            try:
                links_token = await self._process_feed(
                    links_container, links_token, self._orchestrator.handle_link_change
                )
                feedback_token = await self._process_feed(
                    feedback_container, feedback_token, self._orchestrator.handle_feedback_change
                )
            except Exception:
                logger.exception("Error processing change feed")

            await asyncio.sleep(1.0)

    async def _process_feed(
        self,
        container: ContainerProxy,
        continuation_token: str | None,
        handler,
    ) -> str | None:
        """Read a batch of changes from a container's change feed and process them sequentially."""
        query_kwargs: dict[str, Any] = {"max_item_count": 100}
        if continuation_token:
            query_kwargs["continuation"] = continuation_token

        response = container.query_items_change_feed(**query_kwargs)
        new_token = continuation_token

        async for item in response:
            try:
                await handler(item)
            except Exception:
                logger.exception("Failed to process change feed item %s", item.get("id"))

        if hasattr(response, "continuation_token"):
            token = response.continuation_token
            if isinstance(token, str):
                new_token = token

        return new_token
