"""Unit tests for PromptTemplate domain model."""

import pytest
from uuid import uuid4

from src.domain.models.prompt_template import PromptTemplate


def test_prompt_template_creation():
    """Test creating a valid prompt template."""
    prompt = PromptTemplate(
        name="test_prompt",
        version=1,
        template_json={
            "system": "You are an assistant.",
            "user_template": "Generate question for {skill}",
            "variables": ["skill"],
        },
    )

    assert prompt.name == "test_prompt"
    assert prompt.version == 1
    assert prompt.is_draft is True
    assert prompt.is_active is False
    assert prompt.traffic_percentage == 0


def test_template_json_validation():
    """Test template_json validation."""
    # Valid template
    prompt = PromptTemplate(
        name="test",
        version=1,
        template_json={
            "system": "You are an assistant.",
            "user_template": "Generate question for {skill}",
            "variables": ["skill"],
        },
    )
    assert prompt.template_json["system"] == "You are an assistant."

    # Missing 'system' key
    with pytest.raises(ValueError, match="must contain"):
        PromptTemplate(
            name="test",
            version=1,
            template_json={
                "user_template": "Missing system",
                "variables": [],
            },
        )

    # Missing 'user_template' key
    with pytest.raises(ValueError, match="must contain"):
        PromptTemplate(
            name="test",
            version=1,
            template_json={
                "system": "Missing user_template",
                "variables": [],
            },
        )

    # Missing 'variables' key
    with pytest.raises(ValueError, match="must contain"):
        PromptTemplate(
            name="test",
            version=1,
            template_json={
                "system": "Missing variables",
                "user_template": "test",
            },
        )

    # Invalid 'system' type (not string)
    with pytest.raises(ValueError, match="must be a string"):
        PromptTemplate(
            name="test",
            version=1,
            template_json={
                "system": 123,  # Should be string
                "user_template": "test",
                "variables": [],
            },
        )

    # Invalid 'variables' type (not list)
    with pytest.raises(ValueError, match="must be a list"):
        PromptTemplate(
            name="test",
            version=1,
            template_json={
                "system": "test",
                "user_template": "test",
                "variables": "not_a_list",
            },
        )


def test_active_draft_validation():
    """Test that active versions cannot be drafts."""
    # Draft non-active (valid)
    prompt = PromptTemplate(
        name="test",
        version=1,
        template_json={
            "system": "test",
            "user_template": "test",
            "variables": [],
        },
        is_active=False,
        is_draft=True,
    )
    assert prompt.is_draft is True

    # Active non-draft (valid)
    prompt = PromptTemplate(
        name="test",
        version=1,
        template_json={
            "system": "test",
            "user_template": "test",
            "variables": [],
        },
        is_active=True,
        is_draft=False,
    )
    assert prompt.is_active is True

    # Active draft (invalid)
    with pytest.raises(ValueError, match="cannot be drafts"):
        PromptTemplate(
            name="test",
            version=1,
            template_json={
                "system": "test",
                "user_template": "test",
                "variables": [],
            },
            is_active=True,
            is_draft=True,
        )


def test_get_prompt_text():
    """Test prompt rendering with variables."""
    prompt = PromptTemplate(
        name="test",
        version=1,
        template_json={
            "system": "You are an assistant.",
            "user_template": "Generate question for {skill} at {difficulty} level",
            "variables": ["skill", "difficulty"],
        },
    )

    # Render with all variables
    rendered = prompt.get_prompt_text(skill="Python", difficulty="medium")

    assert "You are an assistant" in rendered
    assert "Generate question for Python at medium level" in rendered

    # Missing variable (should fail)
    with pytest.raises(ValueError, match="Missing variables"):
        prompt.get_prompt_text(skill="Python")  # Missing 'difficulty'

    # Extra variables (should work - extra vars ignored)
    rendered = prompt.get_prompt_text(
        skill="Python",
        difficulty="medium",
        extra_var="ignored"
    )
    assert "Python" in rendered


def test_traffic_percentage_validation():
    """Test traffic_percentage field validation."""
    # Valid percentages
    for pct in [0, 50, 100]:
        prompt = PromptTemplate(
            name="test",
            version=1,
            template_json={
                "system": "test",
                "user_template": "test",
                "variables": [],
            },
            traffic_percentage=pct,
        )
        assert prompt.traffic_percentage == pct

    # Invalid percentage (< 0)
    with pytest.raises(ValueError):
        PromptTemplate(
            name="test",
            version=1,
            template_json={
                "system": "test",
                "user_template": "test",
                "variables": [],
            },
            traffic_percentage=-1,
        )

    # Invalid percentage (> 100)
    with pytest.raises(ValueError):
        PromptTemplate(
            name="test",
            version=1,
            template_json={
                "system": "test",
                "user_template": "test",
                "variables": [],
            },
            traffic_percentage=101,
        )


def test_version_validation():
    """Test version field validation."""
    # Valid version (>= 1)
    prompt = PromptTemplate(
        name="test",
        version=1,
        template_json={
            "system": "test",
            "user_template": "test",
            "variables": [],
        },
    )
    assert prompt.version == 1

    # Invalid version (< 1)
    with pytest.raises(ValueError):
        PromptTemplate(
            name="test",
            version=0,
            template_json={
                "system": "test",
                "user_template": "test",
                "variables": [],
            },
        )


def test_parent_version_id():
    """Test parent_version_id field."""
    parent_id = uuid4()

    prompt = PromptTemplate(
        name="test",
        version=2,
        parent_version_id=parent_id,
        template_json={
            "system": "test",
            "user_template": "test",
            "variables": [],
        },
    )

    assert prompt.parent_version_id == parent_id
    assert prompt.version == 2
