"""Unit tests for AuthMiddleware.

Tests cover:
- User role extraction from Keycloak headers
- Route pattern matching
- Authentication validation (401 errors)
- Authorization enforcement (403 errors)
- Public route bypass
- UserContext population in request.state
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from uuid import UUID

from src.infrastructure.middleware.auth_middleware import AuthMiddleware


@pytest.fixture
def app_with_auth():
    """Create FastAPI app with AuthMiddleware for testing."""
    app = FastAPI()

    # Add auth middleware
    app.add_middleware(
        AuthMiddleware,
        role_header_name="X-Auth-Request-Groups",
        user_id_header_name="X-Auth-Request-User",
        role_prefix="role:",
        allowed_roles=["Admin", "User"],
    )

    # Test endpoints
    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/api/ai/interviews")
    async def list_interviews():
        return {"interviews": []}

    @app.delete("/api/ai/interviews/{interview_id}/delete")
    async def delete_interview(interview_id: str):
        return {"deleted": interview_id}

    @app.get("/api/ai/admin/users")
    async def list_users():
        return {"users": []}

    @app.get("/api/ai/feedback")
    async def list_feedback():
        return {"feedback": []}

    return app


@pytest.fixture
def client(app_with_auth):
    """Test client with auth middleware."""
    return TestClient(app_with_auth)


class TestUserRoleExtraction:
    """Test role extraction from Keycloak headers."""

    def test_user_role_extraction(self, client):
        """Should extract 'User' role from Keycloak header."""
        response = client.get(
            "/api/ai/interviews",
            headers={
                "X-Auth-Request-User": "102ea1b3-f664-4617-8f43-fdde557f12b6",
                "X-Auth-Request-Groups": "role:User,role:default-roles-elios,role:offline_access",
            },
        )
        assert response.status_code == 200

    def test_admin_role_extraction(self, client):
        """Should extract 'Admin' role from Keycloak header."""
        response = client.get(
            "/api/ai/admin/users",
            headers={
                "X-Auth-Request-User": "102ea1b3-f664-4617-8f43-fdde557f12b6",
                "X-Auth-Request-Groups": "role:Admin,role:default-roles-elios",
            },
        )
        assert response.status_code == 200

    def test_no_valid_role_returns_403(self, client):
        """Should return 403 when no valid app role in header."""
        response = client.get(
            "/api/ai/interviews",
            headers={
                "X-Auth-Request-User": "102ea1b3-f664-4617-8f43-fdde557f12b6",
                "X-Auth-Request-Groups": "role:default-roles-elios,role:offline_access",
            },
        )
        assert response.status_code == 403
        assert "Insufficient permissions" in response.json()["detail"]


class TestAuthenticationValidation:
    """Test authentication header validation (401 errors)."""

    def test_missing_user_id_returns_401(self, client):
        """Should return 401 when X-Auth-Request-User header is missing."""
        response = client.get(
            "/api/ai/interviews",
            headers={
                "X-Auth-Request-Groups": "role:User",
            },
        )
        assert response.status_code == 401
        assert "Authentication required" in response.json()["detail"]

    def test_missing_roles_header_returns_401(self, client):
        """Should return 401 when X-Auth-Request-Groups header is missing."""
        response = client.get(
            "/api/ai/interviews",
            headers={
                "X-Auth-Request-User": "102ea1b3-f664-4617-8f43-fdde557f12b6",
            },
        )
        assert response.status_code == 401
        assert "Authentication required" in response.json()["detail"]

    def test_invalid_uuid_returns_401(self, client):
        """Should return 401 when user_id is not valid UUID format."""
        response = client.get(
            "/api/ai/interviews",
            headers={
                "X-Auth-Request-User": "not-a-valid-uuid",
                "X-Auth-Request-Groups": "role:User",
            },
        )
        assert response.status_code == 401
        assert "Invalid authentication credentials" in response.json()["detail"]


class TestAuthorizationEnforcement:
    """Test route-based authorization (403 errors)."""

    def test_admin_route_user_forbidden(self, client):
        """User role should not be able to access admin routes."""
        response = client.get(
            "/api/ai/admin/users",
            headers={
                "X-Auth-Request-User": "102ea1b3-f664-4617-8f43-fdde557f12b6",
                "X-Auth-Request-Groups": "role:User",
            },
        )
        assert response.status_code == 403
        assert "Insufficient permissions" in response.json()["detail"]

    def test_admin_route_admin_allowed(self, client):
        """Admin role should be able to access admin routes."""
        response = client.get(
            "/api/ai/admin/users",
            headers={
                "X-Auth-Request-User": "102ea1b3-f664-4617-8f43-fdde557f12b6",
                "X-Auth-Request-Groups": "role:Admin",
            },
        )
        assert response.status_code == 200

    def test_delete_route_user_forbidden(self, client):
        """User role should not be able to delete interviews."""
        response = client.delete(
            "/api/ai/interviews/123e4567-e89b-12d3-a456-426614174000/delete",
            headers={
                "X-Auth-Request-User": "102ea1b3-f664-4617-8f43-fdde557f12b6",
                "X-Auth-Request-Groups": "role:User",
            },
        )
        assert response.status_code == 403

    def test_delete_route_admin_allowed(self, client):
        """Admin role should be able to delete interviews."""
        response = client.delete(
            "/api/ai/interviews/123e4567-e89b-12d3-a456-426614174000/delete",
            headers={
                "X-Auth-Request-User": "102ea1b3-f664-4617-8f43-fdde557f12b6",
                "X-Auth-Request-Groups": "role:Admin",
            },
        )
        assert response.status_code == 200

    def test_interview_route_both_roles_allowed(self, client):
        """Both Admin and User roles should access interview routes."""
        # Test with User role
        response_user = client.get(
            "/api/ai/interviews",
            headers={
                "X-Auth-Request-User": "102ea1b3-f664-4617-8f43-fdde557f12b6",
                "X-Auth-Request-Groups": "role:User",
            },
        )
        assert response_user.status_code == 200

        # Test with Admin role
        response_admin = client.get(
            "/api/ai/interviews",
            headers={
                "X-Auth-Request-User": "102ea1b3-f664-4617-8f43-fdde557f12b6",
                "X-Auth-Request-Groups": "role:Admin",
            },
        )
        assert response_admin.status_code == 200


class TestPublicRoutes:
    """Test public routes bypass authentication."""

    def test_health_no_auth(self, client):
        """Health endpoint should be accessible without auth headers."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_docs_no_auth(self, client):
        """Docs endpoints should be accessible without auth."""
        # Note: TestClient may not render full docs, but should not return 401
        response = client.get("/docs")
        # May return 404 if docs not configured, but should not return 401
        assert response.status_code != 401

    def test_openapi_no_auth(self, client):
        """OpenAPI spec should be accessible without auth."""
        response = client.get("/openapi.json")
        assert response.status_code == 200


class TestUserContextPopulation:
    """Test that UserContext is correctly populated in request.state."""

    def test_request_state_populated(self, app_with_auth):
        """User context should be stored in request.state.user."""
        from starlette.requests import Request

        user_context_captured = None

        @app_with_auth.get("/api/ai/test-user-context")
        async def test_endpoint(request: Request):
            nonlocal user_context_captured
            user_context_captured = request.state.user
            return {"user_id": str(request.state.user.user_id)}

        client = TestClient(app_with_auth)
        response = client.get(
            "/api/ai/test-user-context",
            headers={
                "X-Auth-Request-User": "102ea1b3-f664-4617-8f43-fdde557f12b6",
                "X-Auth-Request-Groups": "role:Admin",
            },
        )

        assert response.status_code == 200
        assert user_context_captured is not None
        assert user_context_captured.user_id == UUID("102ea1b3-f664-4617-8f43-fdde557f12b6")
        assert user_context_captured.role == "Admin"
        assert user_context_captured.is_admin() is True


class TestRoutePatternMatching:
    """Test wildcard route pattern matching."""

    def test_wildcard_pattern_matches_uuid(self, client):
        """Wildcard (*) should match UUID in route path."""
        response = client.delete(
            "/api/ai/interviews/550e8400-e29b-41d4-a716-446655440000/delete",
            headers={
                "X-Auth-Request-User": "102ea1b3-f664-4617-8f43-fdde557f12b6",
                "X-Auth-Request-Groups": "role:Admin",
            },
        )
        assert response.status_code == 200

    def test_more_specific_pattern_takes_precedence(self, client):
        """More specific patterns should match before general ones."""
        # /api/ai/interviews/*/delete (Admin only) should match before
        # /api/ai/interviews/* (Admin + User)
        response = client.delete(
            "/api/ai/interviews/123/delete",
            headers={
                "X-Auth-Request-User": "102ea1b3-f664-4617-8f43-fdde557f12b6",
                "X-Auth-Request-Groups": "role:User",
            },
        )
        # Should be 403 because delete requires Admin
        assert response.status_code == 403
