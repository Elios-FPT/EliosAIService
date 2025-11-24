"""Unit tests for PromptMetadataChange domain model."""

import pytest
from uuid import uuid4

from src.domain.models.prompt_metadata_change import PromptMetadataChange


def test_prompt_metadata_change_creation():
    """Test creating a valid metadata change."""
    prompt_id = uuid4()

    change = PromptMetadataChange(
        prompt_template_id=prompt_id,
        field_name="traffic_percentage",
        old_value="50",
        new_value="75",
        changed_by="admin",
        reason="Increase traffic to new version",
    )

    assert change.prompt_template_id == prompt_id
    assert change.field_name == "traffic_percentage"
    assert change.old_value == "50"
    assert change.new_value == "75"
    assert change.changed_by == "admin"
    assert change.reason == "Increase traffic to new version"


def test_create_change_factory_method():
    """Test factory method serializes values correctly."""
    prompt_id = uuid4()

    # Test with integer values
    change = PromptMetadataChange.create_change(
        prompt_template_id=prompt_id,
        field_name="traffic_percentage",
        old_value=50,
        new_value=75,
        changed_by="admin",
        reason="Increase traffic",
    )

    assert change.field_name == "traffic_percentage"
    assert change.old_value == "50"  # Serialized to string
    assert change.new_value == "75"  # Serialized to string
    assert change.changed_by == "admin"
    assert change.reason == "Increase traffic"


def test_create_change_with_none_values():
    """Test factory method handles None values."""
    prompt_id = uuid4()

    change = PromptMetadataChange.create_change(
        prompt_template_id=prompt_id,
        field_name="ab_test_group",
        old_value=None,
        new_value="control",
        changed_by="system",
    )

    assert change.old_value is None
    assert change.new_value == "control"
    assert change.reason is None


def test_create_change_with_boolean_values():
    """Test factory method serializes boolean values."""
    prompt_id = uuid4()

    change = PromptMetadataChange.create_change(
        prompt_template_id=prompt_id,
        field_name="is_active",
        old_value=False,
        new_value=True,
        changed_by="admin",
        reason="Activating new version",
    )

    assert change.old_value == "False"
    assert change.new_value == "True"


def test_create_change_with_complex_values():
    """Test factory method serializes complex values."""
    prompt_id = uuid4()

    change = PromptMetadataChange.create_change(
        prompt_template_id=prompt_id,
        field_name="metadata",
        old_value={"key": "old_value"},
        new_value={"key": "new_value"},
        changed_by="admin",
    )

    assert "old_value" in change.old_value
    assert "new_value" in change.new_value


def test_changed_at_auto_set():
    """Test that changed_at is automatically set."""
    prompt_id = uuid4()

    change = PromptMetadataChange(
        prompt_template_id=prompt_id,
        field_name="test_field",
        changed_by="admin",
    )

    assert change.changed_at is not None


def test_id_auto_generated():
    """Test that ID is automatically generated."""
    prompt_id = uuid4()

    change = PromptMetadataChange(
        prompt_template_id=prompt_id,
        field_name="test_field",
        changed_by="admin",
    )

    assert change.id is not None
