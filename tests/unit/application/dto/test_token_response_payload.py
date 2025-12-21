"""Unit tests for token response DTOs."""

import pytest
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from src.application.dto.event import TokenResponseEnvelope, TokenResponsePayload


class TestTokenResponsePayload:
    """Tests for TokenResponsePayload model."""

    def test_parse_success_payload(self):
        """Parse successful token response payload."""
        raw = {
            "processedAt": "2025-12-21T17:18:03.110580300Z",
            "success": True,
            "newBalance": "6220.00",
            "userId": "102ea1b3-f664-4617-8f43-fdde557f12b6",
        }

        payload = TokenResponsePayload.model_validate(raw)

        assert payload.success is True
        assert payload.new_balance == Decimal("6220.00")
        assert payload.user_id == UUID("102ea1b3-f664-4617-8f43-fdde557f12b6")
        assert payload.processed_at is not None


class TestTokenResponseEnvelope:
    """Tests for TokenResponseEnvelope model."""

    def test_parse_success_response(self):
        """Parse complete success response envelope."""
        raw = {
            "EventId": "2ff86c0d-ad2c-49d3-997d-371dc9fca629",
            "CorrelationId": "a2d4668b-5f70-45ec-83df-be656fefd714",
            "EventType": "UPDATE",
            "Payload": {
                "processedAt": "2025-12-21T17:18:03.110580300Z",
                "success": True,
                "newBalance": "6220.00",
                "userId": "102ea1b3-f664-4617-8f43-fdde557f12b6",
            },
            "Success": True,
            "ErrorMessage": None,
        }

        envelope = TokenResponseEnvelope.model_validate(raw)

        assert envelope.is_success() is True
        assert envelope.correlation_id == UUID("a2d4668b-5f70-45ec-83df-be656fefd714")
        assert envelope.payload.new_balance == Decimal("6220.00")

    def test_parse_failure_response(self):
        """Parse failure response envelope."""
        raw = {
            "EventId": "987abfc4-f65c-4e8a-927c-3536dd8b2626",
            "CorrelationId": "3d30601e-d06b-455c-b0cd-15dd0ac72dc7",
            "EventType": "UPDATE",
            "Payload": None,
            "Success": False,
            "ErrorMessage": "Insufficient balance: cannot deduct 100000 from 10220.00",
        }

        envelope = TokenResponseEnvelope.model_validate(raw)

        assert envelope.is_success() is False
        assert (
            envelope.get_error_detail()
            == "Insufficient balance: cannot deduct 100000 from 10220.00"
        )
        assert envelope.payload is None

    def test_is_success_requires_payload(self):
        """Success flag True but missing payload should be treated as failure."""
        raw = {
            "EventId": "123e4567-e89b-12d3-a456-426614174000",
            "CorrelationId": "123e4567-e89b-12d3-a456-426614174001",
            "EventType": "UPDATE",
            "Payload": None,
            "Success": True,  # Inconsistent state
            "ErrorMessage": None,
        }

        envelope = TokenResponseEnvelope.model_validate(raw)

        # is_success checks both success flag AND payload presence
        assert envelope.is_success() is False
