"""Tests for the require_auth decorator."""

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from agent_stack.auth.middleware import require_auth


@require_auth
async def protected_view(request):
    return {"user": "authenticated"}


@pytest.mark.asyncio
async def test_require_auth_raises_401_when_no_session():
    request = MagicMock()
    del request.session  # no session attribute
    with pytest.raises(HTTPException) as exc_info:
        await protected_view(request)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_require_auth_raises_401_when_no_user():
    request = MagicMock()
    request.session = {}
    with pytest.raises(HTTPException) as exc_info:
        await protected_view(request)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_require_auth_passes_when_user_present():
    request = MagicMock()
    request.session = {"user": {"name": "Test User"}}
    result = await protected_view(request)
    assert result == {"user": "authenticated"}
