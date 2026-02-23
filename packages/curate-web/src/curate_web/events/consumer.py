"""Service Bus consumer — receives pipeline events and feeds SSE EventManager."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import secrets
from typing import TYPE_CHECKING

from curate_common.events import EventEnvelope

if TYPE_CHECKING:
    from curate_common.config import ServiceBusConfig
    from curate_web.events import EventManager

logger = logging.getLogger(__name__)
_BASE_RECONNECT_DELAY_SECONDS = 1.0
_MAX_RECONNECT_DELAY_SECONDS = 30.0
_JITTER_SCALE = 1000


def _compute_reconnect_delay_seconds(attempt: int) -> float:
    """Return bounded exponential backoff delay with jitter."""
    base_delay = _BASE_RECONNECT_DELAY_SECONDS * (2 ** min(attempt, 10))
    jitter_ratio = secrets.randbelow(_JITTER_SCALE) / _JITTER_SCALE
    return min(
        _MAX_RECONNECT_DELAY_SECONDS,
        base_delay + (base_delay * jitter_ratio),
    )


class ServiceBusConsumer:
    """Receives events from Azure Service Bus and forwards to local EventManager."""

    def __init__(self, config: ServiceBusConfig, event_manager: EventManager) -> None:
        """Initialize with Service Bus config and local event manager."""
        self._config = config
        self._event_manager = event_manager
        self._task: asyncio.Task | None = None
        self._running = False

    async def start(self) -> None:
        """Start the background consumer task."""
        self._running = True
        self._task = asyncio.create_task(self._consume())
        logger.info(
            "Service Bus consumer started — topic=%s",
            self._config.event_topic_name,
        )

    async def stop(self) -> None:
        """Stop the background consumer task."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        logger.info("Service Bus consumer stopped")

    async def _consume(self) -> None:
        """Consume messages from Service Bus subscription with reconnect backoff."""
        from azure.servicebus.exceptions import (  # noqa: PLC0415
            ServiceBusConnectionError,
        )

        attempt = 0
        while self._running:
            try:
                await self._consume_once()
                attempt = 0
            except asyncio.CancelledError:
                raise
            except ServiceBusConnectionError as exc:
                if not self._running:
                    break
                delay = _compute_reconnect_delay_seconds(attempt)
                attempt += 1
                logger.warning(
                    "Service Bus consumer connection failed — %s; retrying in %.1fs",
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)
            except Exception:  # noqa: BLE001
                if not self._running:
                    break
                delay = _compute_reconnect_delay_seconds(attempt)
                attempt += 1
                logger.warning(
                    "Service Bus consumer error; retrying in %.1fs",
                    delay,
                    exc_info=True,
                )
                await asyncio.sleep(delay)

    async def _consume_once(self) -> None:
        """Run a single Service Bus receive session."""
        from azure.servicebus.aio import ServiceBusClient  # noqa: PLC0415

        client = ServiceBusClient.from_connection_string(self._config.connection_string)
        async with client:
            receiver = client.get_subscription_receiver(
                topic_name=self._config.event_topic_name,
                subscription_name=self._config.subscription_name,
            )
            async with receiver:
                while self._running:
                    messages = await receiver.receive_messages(
                        max_message_count=10, max_wait_time=5
                    )
                    for message in messages:
                        try:
                            envelope = EventEnvelope.from_message_body(str(message))
                            await self._event_manager.publish(
                                envelope.event,
                                envelope.data,
                            )
                            await receiver.complete_message(message)
                        except json.JSONDecodeError:
                            logger.warning(
                                "Invalid Service Bus message payload",
                                exc_info=True,
                            )
                            await receiver.abandon_message(message)
                        except Exception:  # noqa: BLE001
                            logger.warning(
                                "Failed to process Service Bus message",
                                exc_info=True,
                            )
                            await receiver.abandon_message(message)
