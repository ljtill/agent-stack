"""Typed contracts for pipeline events and command payloads."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel


class EventEnvelope(BaseModel):
    """Canonical event envelope used on Service Bus."""

    event: str
    data: dict[str, Any] | str

    @classmethod
    def from_message_body(cls, body: str) -> EventEnvelope:
        """Parse an event envelope from a JSON message body.

        Supports backward-compatible payloads where ``data`` was stringified JSON.
        """
        payload = json.loads(body)
        envelope = cls.model_validate(payload)
        if isinstance(envelope.data, str):
            try:
                decoded = json.loads(envelope.data)
            except json.JSONDecodeError:
                return envelope
            if isinstance(decoded, dict):
                envelope.data = decoded
        return envelope


class PublishRequest(BaseModel):
    """Command payload requesting publication of an edition."""

    edition_id: str
    request_id: str | None = None
