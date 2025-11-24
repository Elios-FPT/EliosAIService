"""Unit tests for PromptDiffService."""

from src.domain.services.prompt_diff_service import PromptDiffService


def test_calculate_diff_values_changed():
    """Test diff calculation for changed values."""
    old = {
        "system": "You are an assistant",
        "user_template": "Generate question for {skill}",
        "variables": ["skill"],
    }
    new = {
        "system": "You are a helpful AI assistant",
        "user_template": "Generate question for {skill}",
        "variables": ["skill"],
    }

    diff = PromptDiffService.calculate_diff(old, new)

    assert "values_changed" in diff
    assert "root['system']" in diff["values_changed"]


def test_calculate_diff_items_added():
    """Test diff calculation for added items."""
    old = {"variables": ["skill"]}
    new = {"variables": ["skill", "difficulty"]}

    diff = PromptDiffService.calculate_diff(old, new)

    assert "iterable_item_added" in diff


def test_calculate_diff_items_removed():
    """Test diff calculation for removed items."""
    old = {"variables": ["skill", "difficulty"]}
    new = {"variables": ["skill"]}

    diff = PromptDiffService.calculate_diff(old, new)

    assert "iterable_item_removed" in diff


def test_calculate_diff_dictionary_added():
    """Test diff calculation for added dictionary fields."""
    old = {"system": "test"}
    new = {"system": "test", "constraints": ["No more than 3 sentences"]}

    diff = PromptDiffService.calculate_diff(old, new)

    assert "dictionary_item_added" in diff


def test_calculate_diff_dictionary_removed():
    """Test diff calculation for removed dictionary fields."""
    old = {"system": "test", "constraints": ["test"]}
    new = {"system": "test"}

    diff = PromptDiffService.calculate_diff(old, new)

    assert "dictionary_item_removed" in diff


def test_calculate_diff_no_changes():
    """Test diff calculation when no changes."""
    old = {"system": "test", "variables": ["skill"]}
    new = {"system": "test", "variables": ["skill"]}

    diff = PromptDiffService.calculate_diff(old, new)

    assert diff == {}


def test_calculate_diff_ignore_order():
    """Test diff ignores list order."""
    old = {"variables": ["skill", "difficulty", "level"]}
    new = {"variables": ["level", "skill", "difficulty"]}

    diff = PromptDiffService.calculate_diff(old, new)

    # Should be empty since order is ignored
    assert diff == {}


def test_get_human_readable_summary_values_changed():
    """Test human-readable summary for value changes."""
    diff = {
        "values_changed": {
            "root['system']": {"old_value": "Old", "new_value": "New"},
            "root['user_template']": {"old_value": "Old", "new_value": "New"},
        }
    }

    summary = PromptDiffService.get_human_readable_summary(diff)

    assert "Changed 'system' field" in summary
    assert "Changed 'user_template' field" in summary


def test_get_human_readable_summary_items_added():
    """Test summary for added items."""
    diff = {
        "iterable_item_added": {
            "root['variables'][1]": "difficulty",
            "root['variables'][2]": "level",
        }
    }

    summary = PromptDiffService.get_human_readable_summary(diff)

    assert "Added 2 items" in summary


def test_get_human_readable_summary_items_removed():
    """Test summary for removed items."""
    diff = {"iterable_item_removed": {"root['variables'][1]": "difficulty"}}

    summary = PromptDiffService.get_human_readable_summary(diff)

    assert "Removed 1 item" in summary


def test_get_human_readable_summary_fields_added():
    """Test summary for added fields."""
    diff = {
        "dictionary_item_added": {
            "root['constraints']",
            "root['examples']",
        }
    }

    summary = PromptDiffService.get_human_readable_summary(diff)

    assert "Added 2 fields" in summary


def test_get_human_readable_summary_fields_removed():
    """Test summary for removed fields."""
    diff = {"dictionary_item_removed": {"root['constraints']"}}

    summary = PromptDiffService.get_human_readable_summary(diff)

    assert "Removed 1 field" in summary


def test_get_human_readable_summary_type_changes():
    """Test summary for type changes."""
    diff = {
        "type_changes": {
            "root['variables']": {
                "old_type": "list",
                "new_type": "dict",
            }
        }
    }

    summary = PromptDiffService.get_human_readable_summary(diff)

    assert "Changed 1 type" in summary


def test_get_human_readable_summary_no_changes():
    """Test summary when no changes."""
    diff = {}

    summary = PromptDiffService.get_human_readable_summary(diff)

    assert summary == "No changes detected"


def test_get_human_readable_summary_multiple_changes():
    """Test summary with multiple change types."""
    diff = {
        "values_changed": {"root['system']": {"old_value": "Old", "new_value": "New"}},
        "iterable_item_added": {"root['variables'][1]": "difficulty"},
        "dictionary_item_removed": {"root['constraints']"},
    }

    summary = PromptDiffService.get_human_readable_summary(diff)

    assert "Changed 'system' field" in summary
    assert "Added 1 item" in summary
    assert "Removed 1 field" in summary


def test_has_significant_changes_true():
    """Test has_significant_changes returns True for changes."""
    diff = {
        "values_changed": {"root['system']": {"old_value": "Old", "new_value": "New"}}
    }

    result = PromptDiffService.has_significant_changes(diff)

    assert result is True


def test_has_significant_changes_false():
    """Test has_significant_changes returns False for no changes."""
    diff = {}

    result = PromptDiffService.has_significant_changes(diff)

    assert result is False


def test_has_significant_changes_with_ignore_fields():
    """Test has_significant_changes with ignored fields."""
    diff = {
        "values_changed": {
            "root['updated_at']": {"old_value": "2024-01-01", "new_value": "2024-01-02"}
        }
    }

    # Without ignore - should be significant
    result = PromptDiffService.has_significant_changes(diff)
    assert result is True

    # With ignore - should not be significant
    result = PromptDiffService.has_significant_changes(diff, ignore_fields=["updated_at"])
    assert result is False


def test_has_significant_changes_mixed_ignored():
    """Test has_significant_changes with some ignored, some not."""
    diff = {
        "values_changed": {
            "root['system']": {"old_value": "Old", "new_value": "New"},
            "root['updated_at']": {"old_value": "2024-01-01", "new_value": "2024-01-02"},
        }
    }

    # System field is not ignored, so should be significant
    result = PromptDiffService.has_significant_changes(diff, ignore_fields=["updated_at"])
    assert result is True


def test_has_significant_changes_all_types():
    """Test has_significant_changes detects all change types."""
    diffs = [
        {"values_changed": {"root['a']": {}}},
        {"iterable_item_added": {"root[0]": "x"}},
        {"iterable_item_removed": {"root[0]": "x"}},
        {"dictionary_item_added": {"root['x']"}},
        {"dictionary_item_removed": {"root['x']"}},
        {"type_changes": {"root['a']": {}}},
    ]

    for diff in diffs:
        result = PromptDiffService.has_significant_changes(diff)
        assert result is True, f"Failed for diff: {diff}"
