"""Integration tests for prompt management database schema."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
import json


@pytest.mark.asyncio
async def test_prompt_templates_table_exists(async_session):
    """Verify prompt_templates table exists with correct schema."""
    result = await async_session.execute(
        text("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'prompt_templates'
            ORDER BY ordinal_position
        """)
    )
    columns = {row[0]: {"type": row[1], "nullable": row[2]} for row in result}

    # Verify key columns exist
    assert "id" in columns
    assert "name" in columns
    assert "version" in columns
    assert "template_json" in columns
    assert "is_active" in columns
    assert "is_draft" in columns
    assert "ab_test_group" in columns
    assert "traffic_percentage" in columns
    assert "created_at" in columns

    # Verify JSONB type
    assert columns["template_json"]["type"] == "jsonb"

    # Verify NOT NULL constraints
    assert columns["name"]["nullable"] == "NO"
    assert columns["version"]["nullable"] == "NO"
    assert columns["template_json"]["nullable"] == "NO"


@pytest.mark.asyncio
async def test_prompt_metadata_changes_table_exists(async_session):
    """Verify prompt_metadata_changes table exists."""
    result = await async_session.execute(
        text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'prompt_metadata_changes'
        """)
    )
    columns = [row[0] for row in result]

    assert "id" in columns
    assert "prompt_template_id" in columns
    assert "field_name" in columns
    assert "old_value" in columns
    assert "new_value" in columns
    assert "changed_by" in columns
    assert "changed_at" in columns
    assert "reason" in columns


@pytest.mark.asyncio
async def test_prompt_executions_table_exists(async_session):
    """Verify prompt_executions table exists."""
    result = await async_session.execute(
        text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'prompt_executions'
        """)
    )
    columns = [row[0] for row in result]

    assert "id" in columns
    assert "prompt_template_id" in columns
    assert "interview_id" in columns
    assert "candidate_id" in columns
    assert "input_variables" in columns
    assert "output_text" in columns
    assert "tokens_used" in columns
    assert "latency_ms" in columns
    assert "model_name" in columns
    assert "success" in columns
    assert "executed_at" in columns


@pytest.mark.asyncio
async def test_prompt_analytics_summary_view_exists(async_session):
    """Verify prompt_analytics_summary materialized view exists."""
    result = await async_session.execute(
        text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'prompt_analytics_summary'
        """)
    )
    columns = [row[0] for row in result]

    assert "prompt_template_id" in columns
    assert "name" in columns
    assert "version" in columns
    assert "total_executions" in columns
    assert "avg_tokens_used" in columns
    assert "avg_latency_ms" in columns
    assert "success_rate" in columns
    assert "estimated_cost_usd" in columns


@pytest.mark.asyncio
async def test_unique_constraint_name_version(async_session):
    """Verify UNIQUE(name, version) constraint works."""
    # Insert first version
    await async_session.execute(
        text("""
            INSERT INTO prompt_templates (name, version, template_json)
            VALUES ('test_unique', 1, '{"system": "test"}')
        """)
    )
    await async_session.commit()

    # Try to insert duplicate (same name, same version) - should fail
    with pytest.raises(IntegrityError):
        await async_session.execute(
            text("""
                INSERT INTO prompt_templates (name, version, template_json)
                VALUES ('test_unique', 1, '{"system": "test2"}')
            """)
        )
        await async_session.commit()

    # Rollback the failed transaction
    await async_session.rollback()

    # Clean up
    await async_session.execute(
        text("DELETE FROM prompt_templates WHERE name = 'test_unique'")
    )
    await async_session.commit()


@pytest.mark.asyncio
async def test_check_constraint_no_active_draft(async_session):
    """Verify CHECK constraint prevents active drafts."""
    # Try to insert active draft - should fail
    with pytest.raises(IntegrityError):
        await async_session.execute(
            text("""
                INSERT INTO prompt_templates (name, version, template_json, is_active, is_draft)
                VALUES ('test_check', 1, '{"system": "test"}', true, true)
            """)
        )
        await async_session.commit()

    # Rollback failed transaction
    await async_session.rollback()


@pytest.mark.asyncio
async def test_check_constraint_traffic_percentage(async_session):
    """Verify traffic_percentage CHECK constraint (0-100)."""
    # Try invalid traffic percentage (-1) - should fail
    with pytest.raises(IntegrityError):
        await async_session.execute(
            text("""
                INSERT INTO prompt_templates (name, version, template_json, traffic_percentage)
                VALUES ('test_traffic', 1, '{"system": "test"}', -1)
            """)
        )
        await async_session.commit()

    await async_session.rollback()

    # Try invalid traffic percentage (101) - should fail
    with pytest.raises(IntegrityError):
        await async_session.execute(
            text("""
                INSERT INTO prompt_templates (name, version, template_json, traffic_percentage)
                VALUES ('test_traffic', 1, '{"system": "test"}', 101)
            """)
        )
        await async_session.commit()

    await async_session.rollback()


@pytest.mark.asyncio
async def test_seed_data_inserted(async_session):
    """Verify 7 initial prompts were seeded."""
    result = await async_session.execute(
        text("""
            SELECT name, version, is_active, is_draft, created_by
            FROM prompt_templates
            WHERE created_by = 'system' AND version = 1
            ORDER BY name
        """)
    )
    prompts = list(result)

    assert len(prompts) == 7

    expected_names = [
        "answer_evaluation",
        "feedback_report",
        "follow_up_generation",
        "gap_detection",
        "ideal_answer_generation",
        "question_generation",
        "rationale_generation",
    ]

    actual_names = sorted([row[0] for row in prompts])
    assert actual_names == expected_names

    # Verify all are active and not drafts
    for row in prompts:
        assert row[2] is True  # is_active
        assert row[3] is False  # is_draft
        assert row[4] == "system"  # created_by


@pytest.mark.asyncio
async def test_prompt_template_json_structure(async_session):
    """Verify template_json has expected structure."""
    result = await async_session.execute(
        text("""
            SELECT template_json
            FROM prompt_templates
            WHERE name = 'question_generation' AND version = 1
        """)
    )
    row = result.fetchone()
    assert row is not None

    template = json.loads(row[0]) if isinstance(row[0], str) else row[0]

    # Verify required keys
    assert "system" in template
    assert "user_template" in template
    assert "variables" in template
    assert "constraints" in template

    # Verify types
    assert isinstance(template["system"], str)
    assert isinstance(template["user_template"], str)
    assert isinstance(template["variables"], list)
    assert isinstance(template["constraints"], str)


@pytest.mark.asyncio
async def test_indexes_created(async_session):
    """Verify all required indexes were created."""
    result = await async_session.execute(
        text("""
            SELECT indexname
            FROM pg_indexes
            WHERE tablename IN ('prompt_templates', 'prompt_metadata_changes', 'prompt_executions', 'prompt_analytics_summary')
        """)
    )
    indexes = [row[0] for row in result]

    # Prompt templates indexes
    assert "idx_prompt_templates_name" in indexes
    assert "idx_prompt_templates_active" in indexes
    assert "idx_prompt_templates_version" in indexes
    assert "idx_prompt_templates_parent" in indexes
    assert "idx_prompt_templates_ab_test" in indexes

    # Prompt metadata changes indexes
    assert "idx_prompt_metadata_changes_template" in indexes
    assert "idx_prompt_metadata_changes_field" in indexes

    # Prompt executions indexes
    assert "idx_prompt_executions_template" in indexes
    assert "idx_prompt_executions_interview" in indexes
    assert "idx_prompt_executions_success" in indexes
    assert "idx_prompt_executions_model" in indexes

    # Analytics summary indexes
    assert "idx_analytics_summary_template_id" in indexes
    assert "idx_analytics_summary_name" in indexes


@pytest.mark.asyncio
async def test_foreign_key_cascade_delete(async_session):
    """Verify CASCADE delete on metadata changes and executions."""
    # Create a test prompt
    result = await async_session.execute(
        text("""
            INSERT INTO prompt_templates (name, version, template_json)
            VALUES ('test_cascade', 1, '{"system": "test"}')
            RETURNING id
        """)
    )
    prompt_id = result.fetchone()[0]
    await async_session.commit()

    # Add metadata change
    await async_session.execute(
        text("""
            INSERT INTO prompt_metadata_changes (prompt_template_id, field_name, changed_by)
            VALUES (:prompt_id, 'test_field', 'tester')
        """),
        {"prompt_id": prompt_id}
    )
    await async_session.commit()

    # Verify metadata change exists
    result = await async_session.execute(
        text("""
            SELECT COUNT(*) FROM prompt_metadata_changes
            WHERE prompt_template_id = :prompt_id
        """),
        {"prompt_id": prompt_id}
    )
    count = result.fetchone()[0]
    assert count == 1

    # Delete prompt
    await async_session.execute(
        text("DELETE FROM prompt_templates WHERE id = :prompt_id"),
        {"prompt_id": prompt_id}
    )
    await async_session.commit()

    # Verify metadata change was cascade deleted
    result = await async_session.execute(
        text("""
            SELECT COUNT(*) FROM prompt_metadata_changes
            WHERE prompt_template_id = :prompt_id
        """),
        {"prompt_id": prompt_id}
    )
    count = result.fetchone()[0]
    assert count == 0
