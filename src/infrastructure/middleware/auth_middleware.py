"""Authentication middleware for Keycloak reverse proxy integration.

This middleware enforces route-based authentication and authorization using
user context extracted from Keycloak reverse proxy headers.

Flow:
1. Check if route is public (bypass auth)
2. Extract user_id from X-Auth-Request-User header
3. Extract role from X-Auth-Request-Groups header (parse Keycloak format)
4. Create UserContext and store in request.state.user
5. Match route against ROUTE_PERMISSIONS
6. Verify user has required role
7. Return 401/403 if unauthorized, otherwise continue
"""

import logging
import re
from typing import Callable, List, Optional, Pattern, Tuple
from uuid import UUID

from fastapi import HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from ..auth.user_context import UserContext
from ..config.route_permissions import (
    DEFAULT_REQUIRED_ROLES,
    PUBLIC_ROUTES,
    ROUTE_PERMISSIONS,
)

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware for Keycloak-based authentication and authorization.

    This middleware:
    - Extracts user context from Keycloak reverse proxy headers
    - Enforces route-based permissions
    - Stores UserContext in request.state.user for endpoint access

    Args:
        app: FastAPI/Starlette application
        role_header_name: Header name for roles (default: X-Auth-Request-Groups)
        user_id_header_name: Header name for user ID (default: X-Auth-Request-User)
        role_prefix: Keycloak role prefix (default: "role:")
        allowed_roles: List of valid application roles (default: ["Admin", "User"])
    """

    def __init__(
        self,
        app,
        role_header_name: str = "X-Auth-Request-Groups",
        user_id_header_name: str = "X-Auth-Request-User",
        role_prefix: str = "role:",
        allowed_roles: Optional[List[str]] = None,
    ):
        super().__init__(app)
        self.role_header_name = role_header_name.lower()
        self.user_id_header_name = user_id_header_name.lower()
        self.role_prefix = role_prefix
        self.allowed_roles = allowed_roles or ["Admin", "User"]

        # Compile route patterns to regex once at startup for efficiency
        self._route_patterns = self._compile_route_patterns()

        logger.info(
            f"AuthMiddleware initialized: "
            f"role_header={role_header_name}, "
            f"user_header={user_id_header_name}, "
            f"allowed_roles={self.allowed_roles}"
        )

    def _compile_route_patterns(self) -> List[Tuple[Pattern[str], List[str]]]:
        """Compile route patterns to regex for efficient matching.

        Returns:
            List of (compiled_regex, required_roles) tuples, sorted by pattern length
            (longest first for specificity matching)
        """
        patterns = []
        for pattern, roles in ROUTE_PERMISSIONS.items():
            # Convert wildcard pattern to regex
            # * matches any single path segment (not including /)
            regex_pattern = pattern.replace("*", "[^/]+")
            regex_pattern = f"^{regex_pattern}$"
            compiled = re.compile(regex_pattern)
            patterns.append((compiled, roles))

        # Sort by pattern length (longest first) for specificity matching
        patterns.sort(key=lambda x: len(x[0].pattern), reverse=True)

        logger.debug(f"Compiled {len(patterns)} route patterns")
        return patterns

    def _is_public_route(self, path: str) -> bool:
        """Check if route is public (no auth required).

        Args:
            path: Request path

        Returns:
            True if route is in PUBLIC_ROUTES
        """
        return path in PUBLIC_ROUTES

    def _extract_user_role(self, roles_header: str) -> Optional[str]:
        """Extract application role from Keycloak roles header.

        Keycloak format: "role:User,role:default-roles-elios,role:offline_access"
        We extract the first role that matches our allowed_roles list.

        Args:
            roles_header: Comma-separated roles from X-Auth-Request-Groups

        Returns:
            First matching role ("Admin" or "User"), or None if no valid role found
        """
        if not roles_header:
            return None

        # Parse Keycloak role format: "role:RoleName,role:AnotherRole,..."
        for role in roles_header.split(","):
            role = role.strip()
            if role.startswith(self.role_prefix):
                # Extract role name after prefix
                role_name = role[len(self.role_prefix) :]
                # Check if it's one of our application roles
                if role_name in self.allowed_roles:
                    return role_name

        return None

    def _get_required_roles(self, path: str) -> List[str]:
        """Get required roles for a route.

        Args:
            path: Request path

        Returns:
            List of roles that can access this route
        """
        # Match against compiled patterns (longest/most specific first)
        for pattern, roles in self._route_patterns:
            if pattern.match(path):
                return roles

        # No match found, use default
        return DEFAULT_REQUIRED_ROLES

    async def dispatch(self, request: Request, call_next) -> Response:
        """Process request through auth middleware.

        Args:
            request: Incoming request
            call_next: Next middleware/endpoint handler

        Returns:
            Response from handler or error response (JSONResponse for auth errors)
        """
        path = request.url.path

        # Skip auth for public routes
        if self._is_public_route(path):
            logger.debug(f"Public route, skipping auth: {path}")
            return await call_next(request)

        # Extract headers (case-insensitive)
        headers = {k.lower(): v for k, v in request.headers.items()}

        user_id_header = headers.get(self.user_id_header_name)
        roles_header = headers.get(self.role_header_name)

        # Validate user_id header
        if not user_id_header:
            logger.warning(f"Missing {self.user_id_header_name} header for {path}")
            return JSONResponse(
                status_code=401,
                content={"detail": "Authentication required"},
            )

        # Validate roles header
        if not roles_header:
            logger.warning(f"Missing {self.role_header_name} header for {path}")
            return JSONResponse(
                status_code=401,
                content={"detail": "Authentication required"},
            )

        # Parse user_id as UUID
        try:
            user_id = UUID(user_id_header)
        except (ValueError, AttributeError):
            logger.warning(f"Invalid UUID format in {self.user_id_header_name}: {user_id_header}")
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid authentication credentials"},
            )

        # Extract application role
        role = self._extract_user_role(roles_header)
        if not role:
            logger.warning(
                f"No valid application role found in {self.role_header_name} for user {user_id}. "
                f"Header value: {roles_header}"
            )
            return JSONResponse(
                status_code=403,
                content={"detail": "Insufficient permissions - no valid application role"},
            )

        # Create user context
        user_context = UserContext(user_id=user_id, role=role)

        # Get required roles for this route
        required_roles = self._get_required_roles(path)

        # Check if user has required role
        if not user_context.has_role(*required_roles):
            logger.warning(
                f"User {user_id} with role '{role}' attempted to access {path} "
                f"(requires: {required_roles})"
            )
            return JSONResponse(
                status_code=403,
                content={"detail": "Insufficient permissions"},
            )

        # Store user context in request state for endpoint access
        request.state.user = user_context

        logger.debug(
            f"Authenticated user {user_id} ({role}) for {path} "
            f"(required: {required_roles})"
        )

        # Proceed to next handler
        return await call_next(request)
