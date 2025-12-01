"""JSON diff calculation service for prompt templates."""

import json
from typing import Any

from deepdiff import DeepDiff
from deepdiff.helper import SetOrdered


def _make_diff_serializable(diff_dict: dict) -> dict:
    """Convert DeepDiff result to fully JSON-serializable format.

    DeepDiff.to_dict() can contain non-serializable types like SetOrdered.
    This function recursively converts them to plain Python types.

    Args:
        diff_dict: Dictionary from DeepDiff.to_dict()

    Returns:
        Fully serializable dictionary
    """
    if not diff_dict:
        return {}

    # Use json.dumps/loads to convert all non-serializable types
    # This handles SetOrdered, custom types, etc.
    try:
        json_str = json.dumps(diff_dict, default=str)
        return json.loads(json_str)
    except (TypeError, ValueError):
        # Fallback: manually convert SetOrdered and other types
        def convert_value(value: Any) -> Any:
            # Explicitly handle SetOrdered first (before other iterable checks)
            if isinstance(value, SetOrdered):
                return [convert_value(item) for item in value]
            elif isinstance(value, dict):
                return {k: convert_value(v) for k, v in value.items()}
            elif isinstance(value, (list, tuple, set)):
                # Convert sets to lists
                return [convert_value(item) for item in value]
            else:
                # Try to convert to string if not serializable
                try:
                    json.dumps(value)
                    return value
                except (TypeError, ValueError):
                    return str(value)

        return convert_value(diff_dict)


class PromptDiffService:
    """Service for calculating JSON diffs between prompt versions."""

    @staticmethod
    def calculate_diff(
        old_template_json: dict,
        new_template_json: dict,
    ) -> dict:
        """Calculate diff between two prompt templates.

        Args:
            old_template_json: Previous version content
            new_template_json: New version content

        Returns:
            Diff dictionary from DeepDiff, empty dict if no changes
        """
        diff = DeepDiff(
            old_template_json,
            new_template_json,
            ignore_order=True,
            verbose_level=2,
        )

        diff_dict = diff.to_dict() if diff else {}
        return _make_diff_serializable(diff_dict)

    @staticmethod
    def get_human_readable_summary(diff: dict) -> str:
        """Convert diff to human-readable summary.

        Args:
            diff: Diff dictionary from calculate_diff()

        Returns:
            Human-readable summary string
        """
        if not diff:
            return "No changes detected"

        changes = []

        # Handle value changes
        if "values_changed" in diff:
            for path, change in diff["values_changed"].items():
                # Extract field name from path like "root['field']"
                field = path.split("'")[1] if "'" in path else path
                changes.append(f"Changed '{field}' field")

        # Handle added items (arrays/lists)
        if "iterable_item_added" in diff:
            count = len(diff["iterable_item_added"])
            changes.append(f"Added {count} item{'s' if count > 1 else ''}")

        # Handle removed items
        if "iterable_item_removed" in diff:
            count = len(diff["iterable_item_removed"])
            changes.append(f"Removed {count} item{'s' if count > 1 else ''}")

        # Handle dictionary item added
        if "dictionary_item_added" in diff:
            count = len(diff["dictionary_item_added"])
            changes.append(f"Added {count} field{'s' if count > 1 else ''}")

        # Handle dictionary item removed
        if "dictionary_item_removed" in diff:
            count = len(diff["dictionary_item_removed"])
            changes.append(f"Removed {count} field{'s' if count > 1 else ''}")

        # Handle type changes
        if "type_changes" in diff:
            count = len(diff["type_changes"])
            changes.append(f"Changed {count} type{'s' if count > 1 else ''}")

        return ", ".join(changes) if changes else "No changes detected"

    @staticmethod
    def has_significant_changes(diff: dict, ignore_fields: list[str] | None = None) -> bool:
        """Check if diff contains significant changes.

        Args:
            diff: Diff dictionary from calculate_diff()
            ignore_fields: Optional list of field names to ignore

        Returns:
            True if there are significant changes
        """
        if not diff:
            return False

        ignore_fields = ignore_fields or []

        # Check for any change types except ignored fields
        significant_keys = [
            "values_changed",
            "iterable_item_added",
            "iterable_item_removed",
            "dictionary_item_added",
            "dictionary_item_removed",
            "type_changes",
        ]

        for key in significant_keys:
            if key in diff:
                # If ignore_fields provided, filter out ignored changes
                if ignore_fields:
                    changes = diff[key]
                    if isinstance(changes, dict):
                        # Check if any change is NOT in ignore list
                        for path in changes.keys():
                            field = path.split("'")[1] if "'" in path else path
                            if field not in ignore_fields:
                                return True
                else:
                    return True

        return False
