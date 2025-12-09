"""Unit tests for PromptTemplate domain model."""

import pytest
from uuid import uuid4
from decimal import Decimal

from src.domain.models.prompt_template import PromptTemplate


def make_prompt(**overrides):
    data = {
        "prompt_name": "test_prompt",
        "version": 1,
        "system_prompt": "You are an assistant.",
        "user_template": "Generate question for {skill}",
        "input_variables": ["skill"],
        "partial_variables": {"format": "json"},
        "output_schema": {"type": "object"},
        "temperature": Decimal("0.3"),
        "max_tokens": 100,
        "top_p": Decimal("0.9"),
        "frequency_penalty": Decimal("0"),
        "presence_penalty": Decimal("0"),
        "created_by": "tester",
    }
    data.update(overrides)
    return PromptTemplate(**data)


def test_prompt_template_creation_defaults():
    prompt = make_prompt()
    assert prompt.prompt_name == "test_prompt"
    assert prompt.version == 1
    assert prompt.is_draft is False
    assert prompt.is_active is False
    assert prompt.input_variables == ["skill"]
    assert prompt.output_schema == {"type": "object"}


def test_get_prompt_text_success_and_missing():
    prompt = make_prompt(user_template="Hello {name}", input_variables=["name"])
    assert prompt.get_prompt_text(name="Alice") == "Hello Alice"
    with pytest.raises(ValueError, match="Missing required variable 'name'"):
        prompt.get_prompt_text()


def test_soft_delete_sets_deleted_at_and_deactivates():
    prompt = make_prompt()
    prompt.soft_delete()
    assert prompt.is_deleted() is True
    assert prompt.deleted_at is not None
    assert prompt.is_active is False


def test_custom_ids_preserved():
    custom_id = uuid4()
    prompt = make_prompt(id=custom_id)
    assert prompt.id == custom_id

