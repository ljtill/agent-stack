"""Tests for shared event contracts."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from curate_common.config import ServiceBusConfig
from curate_common.events import EventEnvelope, PublishRequest, ServiceBusPublisher


def test_event_envelope_parses_object_data() -> None:
    """Event envelopes preserve object payloads."""
    body = '{"event":"publish-request","data":{"edition_id":"ed-1"}}'
    envelope = EventEnvelope.from_message_body(body)
    assert envelope.event == "publish-request"
    assert envelope.data == {"edition_id": "ed-1"}


def test_event_envelope_parses_legacy_stringified_json_data() -> None:
    """Event envelopes decode legacy stringified JSON payloads."""
    body = '{"event":"agent-run-complete","data":"{\\"id\\":\\"run-1\\"}"}'
    envelope = EventEnvelope.from_message_body(body)
    assert envelope.event == "agent-run-complete"
    assert envelope.data == {"id": "run-1"}


def test_event_envelope_preserves_plain_string_data() -> None:
    """Event envelopes keep plain string payloads as-is."""
    body = '{"event":"link-update","data":"<tr id=\\"link-1\\"></tr>"}'
    envelope = EventEnvelope.from_message_body(body)
    assert envelope.event == "link-update"
    assert envelope.data == '<tr id="link-1"></tr>'


def test_publish_request_requires_edition_id() -> None:
    """Publish requests must include an edition identifier."""
    with pytest.raises(ValidationError):
        PublishRequest.model_validate({})


async def test_servicebus_publisher_uses_explicit_topic() -> None:
    """Publisher sends messages to an explicitly configured topic."""
    config = ServiceBusConfig(
        connection_string="Endpoint=sb://test.servicebus.windows.net/;SharedAccessKeyName=key;SharedAccessKey=abc",
        topic_name="legacy-topic",
        command_topic_name="pipeline-commands",
        event_topic_name="pipeline-events",
    )
    sender = MagicMock()
    sender.send_messages = AsyncMock()
    client = MagicMock()
    client.get_topic_sender.return_value = sender
    publisher = ServiceBusPublisher(config, topic_name=config.command_topic_name)

    with patch("curate_common.events.servicebus.ServiceBusClient") as servicebus_cls:
        servicebus_cls.from_connection_string.return_value = client
        await publisher.publish("publish-request", {"edition_id": "ed-1"})

    client.get_topic_sender.assert_called_once_with(
        topic_name=config.command_topic_name,
    )
