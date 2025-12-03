"""Unit tests for FeedbackRequest domain entity."""

import pytest
from uuid import uuid4

from src.domain.models.feedback_request import FeedbackRequest
from src.domain.models.feedback_result import FeedbackStatus, InputType


class TestFeedbackRequestCreation:
    """Test FeedbackRequest creation."""

    def test_create_feedback_request_minimal(self):
        """Test creating FeedbackRequest with minimal fields."""
        entity_id = uuid4()
        request = FeedbackRequest(
            entity_id=entity_id,
            input_type=InputType.INTERVIEW,
        )

        assert request.entity_id == entity_id
        assert request.input_type == InputType.INTERVIEW
        assert request.status == FeedbackStatus.PENDING
        assert request.user_id is None
        assert request.error_message is None
        assert request.id is not None
        assert request.created_at is not None
        assert request.updated_at is not None

    def test_create_feedback_request_with_user(self):
        """Test creating FeedbackRequest with user_id."""
        entity_id = uuid4()
        user_id = uuid4()
        request = FeedbackRequest(
            entity_id=entity_id,
            input_type=InputType.CV,
            user_id=user_id,
        )

        assert request.user_id == user_id
        assert request.input_type == InputType.CV

    def test_create_feedback_request_all_types(self):
        """Test creating FeedbackRequest for all input types."""
        entity_id = uuid4()

        for input_type in [InputType.INTERVIEW, InputType.CV, InputType.CODE]:
            request = FeedbackRequest(
                entity_id=entity_id,
                input_type=input_type,
            )
            assert request.input_type == input_type


class TestFeedbackRequestStateTransitions:
    """Test FeedbackRequest state management."""

    def test_is_terminal_state_success(self):
        """Test terminal state check for SUCCESS."""
        request = FeedbackRequest(
            entity_id=uuid4(),
            input_type=InputType.INTERVIEW,
            status=FeedbackStatus.SUCCESS,
        )

        assert request.is_terminal_state() is True

    def test_is_terminal_state_failed(self):
        """Test terminal state check for FAILED."""
        request = FeedbackRequest(
            entity_id=uuid4(),
            input_type=InputType.INTERVIEW,
            status=FeedbackStatus.FAILED,
        )

        assert request.is_terminal_state() is True

    def test_is_terminal_state_pending(self):
        """Test terminal state check for PENDING (not terminal)."""
        request = FeedbackRequest(
            entity_id=uuid4(),
            input_type=InputType.INTERVIEW,
            status=FeedbackStatus.PENDING,
        )

        assert request.is_terminal_state() is False

    def test_is_terminal_state_processing(self):
        """Test terminal state check for PROCESSING (not terminal)."""
        request = FeedbackRequest(
            entity_id=uuid4(),
            input_type=InputType.INTERVIEW,
            status=FeedbackStatus.PROCESSING,
        )

        assert request.is_terminal_state() is False

    def test_can_retry_retrying(self):
        """Test can_retry for RETRYING status."""
        request = FeedbackRequest(
            entity_id=uuid4(),
            input_type=InputType.INTERVIEW,
            status=FeedbackStatus.RETRYING,
        )

        assert request.can_retry() is True

    def test_can_retry_other_statuses(self):
        """Test can_retry for non-RETRYING statuses."""
        for status in [
            FeedbackStatus.PENDING,
            FeedbackStatus.PROCESSING,
            FeedbackStatus.SUCCESS,
            FeedbackStatus.FAILED,
        ]:
            request = FeedbackRequest(
                entity_id=uuid4(),
                input_type=InputType.INTERVIEW,
                status=status,
            )
            assert request.can_retry() is False

    def test_error_message_on_failed(self):
        """Test that error_message can be set for FAILED status."""
        request = FeedbackRequest(
            entity_id=uuid4(),
            input_type=InputType.INTERVIEW,
            status=FeedbackStatus.FAILED,
            error_message="Analysis failed: LLM timeout",
        )

        assert request.error_message == "Analysis failed: LLM timeout"
        assert request.status == FeedbackStatus.FAILED


class TestFeedbackRequestImmutability:
    """Test FeedbackRequest mutability (should be mutable)."""

    def test_feedback_request_is_mutable(self):
        """Test that FeedbackRequest is mutable (frozen=False)."""
        request = FeedbackRequest(
            entity_id=uuid4(),
            input_type=InputType.INTERVIEW,
        )

        # Should be able to modify fields
        original_status = request.status
        request.status = FeedbackStatus.PROCESSING
        assert request.status != original_status
        assert request.status == FeedbackStatus.PROCESSING

