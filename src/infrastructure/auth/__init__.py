"""Authentication and authorization infrastructure.

This module provides authentication and authorization components for the application,
including user context management and dependencies for FastAPI endpoints.
"""

from .dependencies import get_current_user
from .user_context import UserContext

__all__ = ["UserContext", "get_current_user"]
