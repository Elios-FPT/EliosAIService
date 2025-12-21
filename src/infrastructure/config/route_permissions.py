"""Route-based permission configuration.

This module defines the mapping between API routes and required roles.
Routes are matched using wildcard patterns where * matches any path segment.

Pattern Matching Rules:
- Exact matches take precedence over wildcard matches
- Longer patterns are matched before shorter patterns
- * matches any single path segment (e.g., /api/ai/interviews/*/delete)
- Routes not in ROUTE_PERMISSIONS use DEFAULT_REQUIRED_ROLES
- Routes in PUBLIC_ROUTES bypass authentication entirely

Example:
    Route: "/api/ai/interviews/123e4567-e89b-12d3-a456-426614174000/delete"
    Pattern: "/api/ai/interviews/*/delete"
    Match: Yes
    Required Roles: ["Admin"]
"""

from typing import Dict, List

# Route pattern to required roles mapping
# More specific patterns should be listed first for clarity
ROUTE_PERMISSIONS: Dict[str, List[str]] = {

    # Interview operations
    "/api/ai/interviews/*": ["Admin", "User"],
    "/api/ai/interviews": ["Admin", "User"],

    # Feedback operations
    "/api/ai/feedback/*": ["Admin", "User"],
    "/api/ai/feedback": ["Admin", "User"],

    # Question operations
    "/api/ai/questions/*": ["Admin"],
    "/api/ai/questions": ["Admin"],

    # Prompt operations
    "/api/ai/prompts/*": ["Admin"],
    "/api/ai/prompts": ["Admin"],
}

# Default required roles for routes not explicitly listed above
# This acts as a secure default - all routes require authentication
DEFAULT_REQUIRED_ROLES: List[str] = ["Admin", "User"]

# Public routes that bypass authentication entirely
# These routes are accessible without any authentication headers
PUBLIC_ROUTES: List[str] = [
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/favicon.ico",
]
