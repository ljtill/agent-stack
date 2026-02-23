"""Service Bus event utilities for the worker process."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from typing import TYPE_CHECKING

from pydantic import ValidationError

from curate_common.events import EventEnvelope, PublishRequest, ServiceBusPublisher

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from curate_common.config import ServiceBusConfig

logger = logging.getLogger(__name__)
_MAX_DEDUPE_IDS = 10_000


class ServiceBusCommandConsumer:
    """Consume worker commands from Service Bus and dispatch handlers."""

    def __init__(
        self,
        config: ServiceBusConfig,
        on_publish: Callable[[str], Awaitable[None]],
    ) -> None:
        """Initialize with Service Bus configuration and publish handler."""
        self._config = config
        self._on_publish = on_publish
        self._task: asyncio.Task | None = None
        self._running = False
        self._disabled = not config.connection_string
        self._processed_request_ids: set[str] = set()
        if self._disabled:
            logger.warning(
                "AZURE_SERVICEBUS_CONNECTION_STRING is not set — "
                "publish commands will not be consumed"
            )

    async def start(self) -> None:
        """Start the background command consumer task."""
        if self._disabled:
            return
        self._running = True
        self._task = asyncio.create_task(self._consume())
        logger.info(
            "Service Bus command consumer started — topic=%s subscription=%s",
            self._config.topic_name,
            self._config.worker_subscription_name,
        )

    async def stop(self) -> None:
        """Stop the background command consumer task."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        logger.info("Service Bus command consumer stopped")

    def _remember_request_id(self, request_id: str) -> None:
        """Remember processed command IDs for at-least-once delivery deduplication."""
        self._processed_request_ids.add(request_id)
        if len(self._processed_request_ids) > _MAX_DEDUPE_IDS:
            self._processed_request_ids.clear()

    async def _handle_event(
        self, envelope: EventEnvelope, *, message_id: str | None
    ) -> bool:
        """Handle a decoded event envelope. Returns True when event is handled."""
        if envelope.event != "publish-request":
            return False
        if not isinstance(envelope.data, dict):
            logger.warning("Ignoring invalid publish-request payload (non-object data)")
            return True

        try:
            request = PublishRequest.model_validate(envelope.data)
        except ValidationError:
            logger.warning(
                "Ignoring invalid publish-request payload",
                exc_info=True,
            )
            return True

        dedupe_id = request.request_id or message_id
        if dedupe_id and dedupe_id in self._processed_request_ids:
            logger.info("Ignoring duplicate publish request id=%s", dedupe_id)
            return True

        await self._on_publish(request.edition_id)
        if dedupe_id:
            self._remember_request_id(dedupe_id)
        logger.info("Handled publish request — edition=%s", request.edition_id)
        return True

    async def _consume(self) -> None:
        """Consume worker commands from Service Bus subscription."""
        from azure.servicebus.aio import ServiceBusClient  # noqa: PLC0415

        try:
            client = ServiceBusClient.from_connection_string(
                self._config.connection_string
            )
            async with client:
                receiver = client.get_subscription_receiver(
                    topic_name=self._config.topic_name,
                    subscription_name=self._config.worker_subscription_name,
                )
                async with receiver:
                    while self._running:
                        messages = await receiver.receive_messages(
                            max_message_count=10,
                            max_wait_time=5,
                        )
                        for message in messages:
                            try:
                                envelope = EventEnvelope.from_message_body(str(message))
                                handled = await self._handle_event(
                                    envelope,
                                    message_id=str(message.message_id)
                                    if message.message_id
                                    else None,
                                )
                                await receiver.complete_message(message)
                                if not handled:
                                    logger.debug(
                                        "Ignored non-command event from worker "
                                        "subscription: %s",
                                        envelope.event,
                                    )
                            except asyncio.CancelledError:
                                raise
                            except json.JSONDecodeError:
                                logger.warning(
                                    "Invalid Service Bus message payload, "
                                    "abandoning message",
                                )
                                await receiver.abandon_message(message)
                            except Exception:  # noqa: BLE001
                                logger.warning(
                                    "Failed to process Service Bus command message",
                                    exc_info=True,
                                )
                                await receiver.abandon_message(message)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            logger.warning(
                "Service Bus command consumer error, will not reconnect",
                exc_info=True,
            )


__all__ = ["ServiceBusCommandConsumer", "ServiceBusPublisher"]
