"""Event contracts and publishing interfaces for cross-service communication."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from curate_common.events.contracts import EventEnvelope, PublishRequest
from curate_common.events.servicebus import ServiceBusPublisher


@runtime_checkable
class EventPublisher(Protocol):
    """Protocol for publishing pipeline events to connected consumers."""

    async def publish(self, event_type: str, data: dict[str, Any] | str) -> None:
        """Broadcast an event to all connected consumers."""
        ...


__all__ = [
    "EventEnvelope",
    "EventPublisher",
    "PublishRequest",
    "ServiceBusPublisher",
]
