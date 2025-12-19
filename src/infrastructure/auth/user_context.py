"""User context model for authenticated users.

This module defines the UserContext dataclass which represents an authenticated user
in the system. User context is extracted from Keycloak reverse proxy headers by the
AuthMiddleware and stored in request.state for access in endpoint handlers.
"""

from dataclasses import dataclass
from typing import Optional
from uuid import UUID


@dataclass(frozen=True)
class UserContext:
    """Authenticated user context from Keycloak reverse proxy.

    This immutable dataclass represents a user authenticated via Keycloak.
    It is populated by AuthMiddleware from X-Auth-Request-* headers and
    stored in request.state.user for access in endpoint handlers.

    Attributes:
        user_id: Unique user identifier (UUID format)
        role: User's application role ("Admin" or "User")
        email: Optional user email address (future extension)
        username: Optional username (future extension)

    Example:
        >>> user = UserContext(
        ...     user_id=UUID("102ea1b3-f664-4617-8f43-fdde557f12b6"),
        ...     role="User"
        ... )
        >>> user.is_admin()
        False
        >>> user.has_role("User", "Admin")
        True
    """

    user_id: UUID
    role: str
    email: Optional[str] = None
    username: Optional[str] = None

    def has_role(self, *roles: str) -> bool:
        """Check if user has any of the specified roles.

        Args:
            *roles: One or more role names to check

        Returns:
            True if user's role matches any of the specified roles

        Example:
            >>> user.has_role("Admin", "User")
            True
        """
        return self.role in roles

    def is_admin(self) -> bool:
        """Check if user has Admin role.

        Returns:
            True if user's role is "Admin"

        Example:
            >>> user.is_admin()
            False
        """
        return self.role == "Admin"
