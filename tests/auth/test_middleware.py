"""Tests for the authentication middleware."""

from unittest.mock import MagicMock

from agent_stack.auth.middleware import get_user


def test_get_user_returns_none_without_session():
    request = MagicMock()
    del request.session  # Simulate no session attribute
    assert get_user(request) is None


def test_get_user_returns_none_for_empty_session():
    request = MagicMock()
    request.session = {}
    assert get_user(request) is None


def test_get_user_returns_user_from_session():
    request = MagicMock()
    request.session = {"user": {"name": "Test User"}}
    user = get_user(request)
    assert user == {"name": "Test User"}
