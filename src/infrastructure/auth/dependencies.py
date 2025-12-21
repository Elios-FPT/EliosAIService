"""FastAPI dependencies for authentication.

This module provides dependency injection functions for accessing authenticated
user context in FastAPI endpoint handlers.
"""

from fastapi import Request

from .user_context import UserContext


def get_current_user(request: Request) -> UserContext:
    """Get authenticated user context from request state.

    This dependency extracts the UserContext that was stored by AuthMiddleware
    in request.state.user. It provides type-safe access to user information
    in endpoint handlers.

    Args:
        request: FastAPI/Starlette request object

    Returns:
        UserContext for the authenticated user

    Raises:
        RuntimeError: If AuthMiddleware is not registered or user context not found

    Example:
        >>> from fastapi import Depends
        >>>
        >>> @router.get("/profile")
        >>> async def get_profile(user: UserContext = Depends(get_current_user)):
        ...     return {"user_id": str(user.user_id), "role": user.role}
    """
    user = getattr(request.state, "user", None)
    if user is None:
        raise RuntimeError(
            "User context not found in request.state. "
            "Ensure AuthMiddleware is registered in the application."
        )
    return user
