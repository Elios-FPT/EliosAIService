"""Tests for TokenDeltaPayload."""

from uuid import uuid4

from src.application.dto.event.token_delta_payload import TokenDeltaPayload


def test_token_delta_payload_serialization():
    user_id = uuid4()
    payload = TokenDeltaPayload(user_id=user_id, tokens=-10)

    dumped = payload.model_dump(mode="json", by_alias=True)

    assert dumped["UserId"] == str(user_id)
    assert dumped["Tokens"] == -10

