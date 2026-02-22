"""Authentication middleware — protects routes behind Microsoft Entra ID login."""

from __future__ import annotations

from functools import wraps
from typing import TYPE_CHECKING, Any

from fastapi import HTTPException, Request, status

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine


def get_user(request: Request) -> dict[str, Any] | None:
    """Extract the authenticated user from the session, if present."""
    return request.session.get("user") if hasattr(request, "session") else None


def require_authenticated_user(request: Request) -> dict[str, Any]:
    """Return the authenticated user or raise HTTP 401."""
    user = get_user(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return user


def require_auth(
    func: Callable[..., Coroutine[object, object, object]],
) -> Callable[..., Coroutine[object, object, object]]:
    """Ensure the request has an authenticated session."""

    @wraps(func)
    async def wrapper(request: Request, *args: object, **kwargs: object) -> object:
        require_authenticated_user(request)
        return await func(request, *args, **kwargs)

    return wrapper
