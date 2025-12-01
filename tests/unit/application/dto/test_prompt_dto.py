"""Tests for prompt template DTOs."""

from datetime import datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.application.dto.prompt_dto import (
    ActivatePromptRequest,
    AdjustTrafficRequest,
    AnalyticsSummaryResponse,
    AuditTrailResponse,
    CreatePromptRequest,
    CreateVersionRequest,
    PaginatedPromptsResponse,
    PromptTemplateResponse,
    RollbackRequest,
    UpdateDraftPromptRequest,
    VersionHistoryResponse,
)
from src.domain.models.prompt_template import PromptTemplate


class TestCreatePromptRequest:
    """Test CreatePromptRequest DTO."""

    def test_valid_request(self):
        """Test valid request creation."""
        request = CreatePromptRequest(
            prompt_name="test_prompt",
            system_prompt="You are a helpful assistant",
            user_template="Answer: {question}",
            input_variables=["question"],
            temperature=0.7,
            max_tokens=1000,
            top_p=0.9,
            frequency_penalty=0.0,
            presence_penalty=0.0,
            created_by="admin",
        )
        assert request.prompt_name == "test_prompt"
        assert request.temperature == 0.7

    def test_temperature_validation_min(self):
        """Test temperature must be >= 0.0."""
        with pytest.raises(ValidationError) as exc_info:
            CreatePromptRequest(
                prompt_name="test",
                system_prompt="test",
                user_template="test",
                temperature=-0.1,
                max_tokens=1000,
                top_p=0.9,
                frequency_penalty=0.0,
                presence_penalty=0.0,
                created_by="admin",
            )
        assert "greater than or equal to 0" in str(exc_info.value)

    def test_temperature_validation_max(self):
        """Test temperature must be <= 2.0."""
        with pytest.raises(ValidationError) as exc_info:
            CreatePromptRequest(
                prompt_name="test",
                system_prompt="test",
                user_template="test",
                temperature=2.1,
                max_tokens=1000,
                top_p=0.9,
                frequency_penalty=0.0,
                presence_penalty=0.0,
                created_by="admin",
            )
        assert "less than or equal to 2" in str(exc_info.value)

    def test_max_tokens_validation_min(self):
        """Test max_tokens must be >= 1."""
        with pytest.raises(ValidationError) as exc_info:
            CreatePromptRequest(
                prompt_name="test",
                system_prompt="test",
                user_template="test",
                temperature=0.7,
                max_tokens=0,
                top_p=0.9,
                frequency_penalty=0.0,
                presence_penalty=0.0,
                created_by="admin",
            )
        assert "greater than or equal to 1" in str(exc_info.value)

    def test_max_tokens_validation_max(self):
        """Test max_tokens must be <= 100000."""
        with pytest.raises(ValidationError) as exc_info:
            CreatePromptRequest(
                prompt_name="test",
                system_prompt="test",
                user_template="test",
                temperature=0.7,
                max_tokens=100001,
                top_p=0.9,
                frequency_penalty=0.0,
                presence_penalty=0.0,
                created_by="admin",
            )
        assert "less than or equal to 100000" in str(exc_info.value)


class TestCreateVersionRequest:
    """Test CreateVersionRequest DTO."""

    def test_valid_request(self):
        """Test valid version request."""
        request = CreateVersionRequest(
            parent_version=1,
            system_prompt="Updated system prompt",
            user_template="Updated template",
            change_summary="Improved clarity",
            temperature=0.8,
            max_tokens=2000,
            top_p=0.95,
            frequency_penalty=0.0,
            presence_penalty=0.0,
            created_by="admin",
        )
        assert request.parent_version == 1
        assert request.change_summary == "Improved clarity"

    def test_parent_version_optional_defaults(self):
        """Parent version can be omitted (handled server-side)."""
        request = CreateVersionRequest(
            system_prompt="Updated system prompt",
            user_template="Updated template",
            change_summary="Improved clarity",
            temperature=0.8,
            max_tokens=2000,
            top_p=0.95,
            frequency_penalty=0.0,
            presence_penalty=0.0,
            created_by="admin",
        )
        assert request.parent_version is None


class TestUpdateDraftPromptRequest:
    """Test UpdateDraftPromptRequest DTO."""

    def test_valid_request(self):
        """Test full draft update payload."""
        request = UpdateDraftPromptRequest(
            system_prompt="Updated system",
            user_template="Answer {question}",
            input_variables=["question"],
            partial_variables={"topic": "ai"},
            output_parser_type="json_output_parser",
            output_schema={"type": "object"},
            temperature=0.6,
            max_tokens=1500,
            top_p=0.9,
            frequency_penalty=0.0,
            presence_penalty=0.0,
        )

        assert request.system_prompt == "Updated system"
        assert request.max_tokens == 1500

    def test_temperature_validation(self):
        """Temperature must be within allowed range."""
        with pytest.raises(ValidationError):
            UpdateDraftPromptRequest(
                system_prompt="Updated",
                user_template="Updated",
                input_variables=[],
                temperature=2.5,
                max_tokens=1000,
                top_p=0.9,
                frequency_penalty=0.0,
                presence_penalty=0.0,
            )


class TestRollbackRequest:
    """Test RollbackRequest DTO."""

    def test_valid_request(self):
        """Test valid rollback request."""
        request = RollbackRequest(
            target_version=2,
            changed_by="admin",
            reason="Performance issues",
        )
        assert request.target_version == 2
        assert request.reason == "Performance issues"


class TestActivatePromptRequest:
    """Test ActivatePromptRequest DTO."""

    def test_valid_request_default_traffic(self):
        """Test valid request with default traffic_percentage."""
        request = ActivatePromptRequest(
            changed_by="admin",
            reason="Deploy to production",
        )
        assert request.traffic_percentage == 100

    def test_valid_request_custom_traffic(self):
        """Test valid request with custom traffic_percentage."""
        request = ActivatePromptRequest(
            changed_by="admin",
            reason="A/B test",
            traffic_percentage=50,
        )
        assert request.traffic_percentage == 50

    def test_traffic_validation_min(self):
        """Test traffic_percentage must be >= 0."""
        with pytest.raises(ValidationError) as exc_info:
            ActivatePromptRequest(
                changed_by="admin",
                reason="test",
                traffic_percentage=-1,
            )
        assert "greater than or equal to 0" in str(exc_info.value)

    def test_traffic_validation_max(self):
        """Test traffic_percentage must be <= 100."""
        with pytest.raises(ValidationError) as exc_info:
            ActivatePromptRequest(
                changed_by="admin",
                reason="test",
                traffic_percentage=101,
            )
        assert "less than or equal to 100" in str(exc_info.value)


class TestAdjustTrafficRequest:
    """Test AdjustTrafficRequest DTO."""

    def test_valid_request(self):
        """Test valid traffic adjustment request."""
        request = AdjustTrafficRequest(
            new_traffic_percentage=75,
            changed_by="admin",
            reason="Increase traffic",
        )
        assert request.new_traffic_percentage == 75

    def test_traffic_validation(self):
        """Test traffic_percentage validation."""
        with pytest.raises(ValidationError) as exc_info:
            AdjustTrafficRequest(
                new_traffic_percentage=150,
                changed_by="admin",
                reason="test",
            )
        assert "less than or equal to 100" in str(exc_info.value)


class TestPromptTemplateResponse:
    """Test PromptTemplateResponse DTO."""

    def test_from_domain(self):
        """Test from_domain() factory method."""
        prompt = PromptTemplate(
            id=uuid4(),
            prompt_name="test_prompt",
            version=1,
            is_active=True,
            traffic_percentage=100,
            system_prompt="System",
            user_template="User {var}",
            input_variables=["var"],
            partial_variables={"key": "value"},
            output_parser_type="json_output_parser",
            output_schema={"type": "object"},
            temperature=Decimal("0.7"),
            max_tokens=1000,
            top_p=Decimal("0.9"),
            frequency_penalty=Decimal("0.0"),
            presence_penalty=Decimal("0.0"),
            created_at=datetime.utcnow(),
        )

        response = PromptTemplateResponse.from_domain(prompt)

        assert response.id == prompt.id
        assert response.prompt_name == "test_prompt"
        assert response.version == 1
        assert response.is_active is True
        assert response.traffic_percentage == 100
        assert response.temperature == 0.7
        assert isinstance(response.temperature, float)
        assert response.top_p == 0.9
        assert isinstance(response.top_p, float)
        assert response.partial_variables == {"key": "value"}
        assert response.output_schema == {"type": "object"}

    def test_from_domain_with_empty_dicts(self):
        """Test from_domain() with empty partial_variables and output_schema."""
        prompt = PromptTemplate(
            id=uuid4(),
            prompt_name="test",
            version=1,
            system_prompt="System",
            user_template="User",
            temperature=Decimal("0.5"),
            max_tokens=500,
            top_p=Decimal("0.95"),
            frequency_penalty=Decimal("0.0"),
            presence_penalty=Decimal("0.0"),
            partial_variables={},
            output_schema={},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        response = PromptTemplateResponse.from_domain(prompt)

        assert response.partial_variables == {}
        assert response.output_schema == {}

    def test_json_serialization(self):
        """Test JSON serialization of response."""
        prompt = PromptTemplate(
            id=uuid4(),
            prompt_name="test",
            version=1,
            system_prompt="System",
            user_template="User",
            temperature=Decimal("0.5"),
            max_tokens=500,
            top_p=Decimal("0.95"),
            frequency_penalty=Decimal("0.0"),
            presence_penalty=Decimal("0.0"),
            created_at=datetime.utcnow(),
        )

        response = PromptTemplateResponse.from_domain(prompt)
        json_data = response.model_dump(mode="json")

        assert isinstance(json_data["id"], str)  # UUID serialized as string
        assert isinstance(json_data["temperature"], float)
        assert isinstance(json_data["created_at"], str)  # datetime serialized as string


class TestVersionHistoryResponse:
    """Test VersionHistoryResponse DTO."""

    def test_valid_response(self):
        """Test valid version history response."""
        response = VersionHistoryResponse(
            version=2,
            created_at=datetime.utcnow(),
            is_active=True,
            traffic_percentage=50,
            diff={"changed": ["system_prompt"]},
        )
        assert response.version == 2
        assert response.is_active is True
        assert response.diff == {"changed": ["system_prompt"]}

    def test_response_with_none_diff(self):
        """Test response with None diff (first version)."""
        response = VersionHistoryResponse(
            version=1,
            created_at=datetime.utcnow(),
            is_active=False,
            traffic_percentage=0,
            diff=None,
        )
        assert response.diff is None


class TestAnalyticsSummaryResponse:
    """Test AnalyticsSummaryResponse DTO."""

    def test_valid_response(self):
        """Test valid analytics summary response."""
        response = AnalyticsSummaryResponse(
            prompt_name="test_prompt",
            total_executions=100,
            avg_tokens_used=1500.5,
            avg_latency_ms=250.3,
            success_rate=0.95,
            estimated_cost_usd=0.05,
            last_executed_at=datetime.utcnow(),
        )
        assert response.total_executions == 100
        assert response.success_rate == 0.95

    def test_response_with_none_last_executed(self):
        """Test response with None last_executed_at."""
        response = AnalyticsSummaryResponse(
            prompt_name="test",
            total_executions=0,
            avg_tokens_used=0.0,
            avg_latency_ms=0.0,
            success_rate=0.0,
            estimated_cost_usd=0.0,
            last_executed_at=None,
        )
        assert response.last_executed_at is None


class TestAuditTrailResponse:
    """Test AuditTrailResponse DTO."""

    def test_valid_response(self):
        """Test valid audit trail response."""
        response = AuditTrailResponse(
            field_name="is_active",
            old_value="False",
            new_value="True",
            changed_by="admin",
            changed_at=datetime.utcnow(),
            reason="Activate for production",
        )
        assert response.field_name == "is_active"
        assert response.old_value == "False"
        assert response.new_value == "True"


class TestPaginatedPromptsResponse:
    """Test PaginatedPromptsResponse DTO."""

    def test_valid_response(self):
        """Test valid paginated response."""
        prompt = PromptTemplate(
            id=uuid4(),
            prompt_name="test",
            version=1,
            system_prompt="System",
            user_template="User",
            temperature=Decimal("0.5"),
            max_tokens=500,
            top_p=Decimal("0.95"),
            frequency_penalty=Decimal("0.0"),
            presence_penalty=Decimal("0.0"),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        prompt_response = PromptTemplateResponse.from_domain(prompt)

        response = PaginatedPromptsResponse(
            prompts=[prompt_response],
            total=1,
            page=1,
            page_size=20,
            has_next=False,
        )
        assert len(response.prompts) == 1
        assert response.total == 1
        assert response.has_next is False

    def test_has_next_calculation(self):
        """Test has_next calculation."""
        # Page 1, total 25, page_size 20 -> has_next=True
        response = PaginatedPromptsResponse(
            prompts=[],
            total=25,
            page=1,
            page_size=20,
            has_next=True,
        )
        assert response.has_next is True

