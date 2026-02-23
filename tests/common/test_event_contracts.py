"""Tests for shared event contracts."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from curate_common.events import EventEnvelope, PublishRequest


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
