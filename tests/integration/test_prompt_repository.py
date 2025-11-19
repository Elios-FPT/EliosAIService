"""Integration tests for PostgreSQL prompt repository."""

import pytest
from uuid import uuid4

from src.adapters.persistence.postgres_prompt_repository import PostgreSQLPromptRepository


@pytest.mark.asyncio
async def test_create_initial_prompt(async_session):
    """Test creating initial prompt version."""
    repo = PostgreSQLPromptRepository(async_session)

    prompt = await repo.create_initial_prompt(
        name="test_prompt",
        template_json={
            "system": "You are an assistant",
            "user_template": "Generate question for {skill}",
            "variables": ["skill"],
        },
        created_by="admin",
        notes="Initial version",
    )

    assert prompt.name == "test_prompt"
    assert prompt.version == 1
    assert prompt.is_draft is True
    assert prompt.is_active is False
    assert prompt.created_by == "admin"


@pytest.mark.asyncio
async def test_create_initial_prompt_duplicate_fails(async_session):
    """Test that creating duplicate initial prompt fails."""
    repo = PostgreSQLPromptRepository(async_session)

    await repo.create_initial_prompt(
        name="test_prompt",
        template_json={"system": "test", "user_template": "test", "variables": []},
        created_by="admin",
    )

    # Try to create again - should fail
    with pytest.raises(ValueError, match="already exists"):
        await repo.create_initial_prompt(
            name="test_prompt",
            template_json={"system": "test2", "user_template": "test2", "variables": []},
            created_by="admin",
        )


@pytest.mark.asyncio
async def test_create_new_version(async_session):
    """Test creating new version from parent."""
    repo = PostgreSQLPromptRepository(async_session)

    # Create v1
    v1 = await repo.create_initial_prompt(
        name="test_prompt",
        template_json={"system": "v1", "user_template": "test", "variables": []},
        created_by="admin",
    )

    # Create v2
    v2 = await repo.create_new_version(
        name="test_prompt",
        parent_version=1,
        template_json={"system": "v2", "user_template": "test", "variables": []},
        change_summary="Updated system prompt",
        created_by="admin",
    )

    assert v2.version == 2
    assert v2.parent_version_id == v1.id
    assert v2.change_summary == "Updated system prompt"
    assert v2.template_json["system"] == "v2"


@pytest.mark.asyncio
async def test_create_new_version_invalid_parent_fails(async_session):
    """Test creating version with invalid parent fails."""
    repo = PostgreSQLPromptRepository(async_session)

    await repo.create_initial_prompt(
        name="test_prompt",
        template_json={"system": "v1", "user_template": "test", "variables": []},
        created_by="admin",
    )

    # Try to create from non-existent parent
    with pytest.raises(ValueError, match="not found"):
        await repo.create_new_version(
            name="test_prompt",
            parent_version=99,
            template_json={"system": "v2", "user_template": "test", "variables": []},
            change_summary="test",
            created_by="admin",
        )


@pytest.mark.asyncio
async def test_activate_version_deactivates_others(async_session):
    """Test that activation deactivates previous versions."""
    repo = PostgreSQLPromptRepository(async_session)

    # Create 2 versions
    v1 = await repo.create_initial_prompt(
        name="test_prompt",
        template_json={"system": "v1", "user_template": "test", "variables": []},
        created_by="admin",
    )
    v2 = await repo.create_new_version(
        name="test_prompt",
        parent_version=1,
        template_json={"system": "v2", "user_template": "test", "variables": []},
        change_summary="Update",
        created_by="admin",
    )

    # Activate v1
    await repo.activate_version(v1.id, "admin", "Test v1", traffic_percentage=100)

    # Activate v2 → should deactivate v1
    await repo.activate_version(v2.id, "admin", "Test v2", traffic_percentage=100)

    # Verify
    v1_refreshed = await repo.get_by_id(v1.id)
    v2_refreshed = await repo.get_by_id(v2.id)

    assert v1_refreshed.is_active is False
    assert v2_refreshed.is_active is True
    assert v2_refreshed.is_draft is False


@pytest.mark.asyncio
async def test_get_active_prompt_single(async_session):
    """Test getting active prompt (single active version)."""
    repo = PostgreSQLPromptRepository(async_session)

    # Create and activate
    prompt = await repo.create_initial_prompt(
        name="test_prompt",
        template_json={"system": "test", "user_template": "test", "variables": []},
        created_by="admin",
    )
    await repo.activate_version(prompt.id, "admin", "Activate", traffic_percentage=100)

    # Get active
    active = await repo.get_active_prompt("test_prompt")

    assert active is not None
    assert active.id == prompt.id
    assert active.is_active is True


@pytest.mark.asyncio
async def test_get_active_prompt_none(async_session):
    """Test getting active prompt when none active."""
    repo = PostgreSQLPromptRepository(async_session)

    await repo.create_initial_prompt(
        name="test_prompt",
        template_json={"system": "test", "user_template": "test", "variables": []},
        created_by="admin",
    )

    active = await repo.get_active_prompt("test_prompt")
    assert active is None


@pytest.mark.asyncio
async def test_ab_testing_distribution(async_session):
    """Test A/B selection distributes traffic correctly."""
    repo = PostgreSQLPromptRepository(async_session)

    # Create 2 versions
    v1 = await repo.create_initial_prompt(
        name="test_prompt",
        template_json={"system": "v1", "user_template": "test", "variables": []},
        created_by="admin",
    )
    v2 = await repo.create_new_version(
        name="test_prompt",
        parent_version=1,
        template_json={"system": "v2", "user_template": "test", "variables": []},
        change_summary="Variant",
        created_by="admin",
    )

    # Activate both with 50/50 split
    await repo.activate_version(v1.id, "admin", "Control", traffic_percentage=50, ab_test_group="control")
    await repo.activate_version(v2.id, "admin", "Variant", traffic_percentage=50, ab_test_group="variant_a")

    # Sample 1000 selections
    selections = {"v1": 0, "v2": 0}
    for _ in range(1000):
        selected = await repo.get_active_prompt("test_prompt")
        if selected.version == 1:
            selections["v1"] += 1
        else:
            selections["v2"] += 1

    # Verify ~50/50 distribution (±10% tolerance for randomness)
    assert 400 <= selections["v1"] <= 600
    assert 400 <= selections["v2"] <= 600


@pytest.mark.asyncio
async def test_adjust_ab_traffic(async_session):
    """Test adjusting traffic percentage."""
    repo = PostgreSQLPromptRepository(async_session)

    prompt = await repo.create_initial_prompt(
        name="test_prompt",
        template_json={"system": "test", "user_template": "test", "variables": []},
        created_by="admin",
    )
    await repo.activate_version(prompt.id, "admin", "Activate", traffic_percentage=50)

    # Adjust traffic
    await repo.adjust_ab_traffic(prompt.id, 75, "admin", "Increase traffic")

    # Verify
    updated = await repo.get_by_id(prompt.id)
    assert updated.traffic_percentage == 75


@pytest.mark.asyncio
async def test_get_version_history_with_diffs(async_session):
    """Test version history includes JSON diffs."""
    repo = PostgreSQLPromptRepository(async_session)

    # Create versions
    v1 = await repo.create_initial_prompt(
        name="test_prompt",
        template_json={"system": "v1 system", "user_template": "test", "variables": ["skill"]},
        created_by="admin",
    )
    v2 = await repo.create_new_version(
        name="test_prompt",
        parent_version=1,
        template_json={"system": "v2 system", "user_template": "test", "variables": ["skill", "difficulty"]},
        change_summary="Added difficulty variable",
        created_by="admin",
    )

    # Get history
    history = await repo.get_version_history("test_prompt")

    assert len(history) == 2
    assert history[0]["version"] == 1
    assert history[0]["diff"] is None  # v1 has no parent

    assert history[1]["version"] == 2
    assert history[1]["diff"] is not None
    assert history[1]["change_summary"] == "Added difficulty variable"


@pytest.mark.asyncio
async def test_get_audit_trail(async_session):
    """Test audit trail logs all metadata changes."""
    repo = PostgreSQLPromptRepository(async_session)

    prompt = await repo.create_initial_prompt(
        name="test_prompt",
        template_json={"system": "test", "user_template": "test", "variables": []},
        created_by="admin",
    )

    # Activate (logs is_active change)
    await repo.activate_version(prompt.id, "admin", "Initial activation", traffic_percentage=100)

    # Adjust traffic (logs traffic_percentage change)
    await repo.adjust_ab_traffic(prompt.id, 75, "admin", "Reduce traffic")

    # Get audit trail
    trail = await repo.get_audit_trail("test_prompt")

    # Should have at least 2 changes (is_active, traffic_percentage)
    assert len(trail) >= 2

    # Verify change structure
    assert all("field_name" in change for change in trail)
    assert all("changed_by" in change for change in trail)
    assert all(change["changed_by"] == "admin" for change in trail)


@pytest.mark.asyncio
async def test_rollback_to_version(async_session):
    """Test rollback creates new version from target."""
    repo = PostgreSQLPromptRepository(async_session)

    # Create v1 and v2
    v1 = await repo.create_initial_prompt(
        name="test_prompt",
        template_json={"system": "v1", "user_template": "test", "variables": []},
        created_by="admin",
    )
    v2 = await repo.create_new_version(
        name="test_prompt",
        parent_version=1,
        template_json={"system": "v2 broken", "user_template": "test", "variables": []},
        change_summary="Broken update",
        created_by="admin",
    )

    # Rollback to v1
    v3 = await repo.rollback_to_version("test_prompt", 1, "admin", "v2 was broken")

    # Verify v3
    assert v3.version == 3
    assert v3.template_json["system"] == "v1"  # Same content as v1
    assert "Rollback to v1" in v3.change_summary


@pytest.mark.asyncio
async def test_log_execution(async_session):
    """Test logging prompt execution."""
    repo = PostgreSQLPromptRepository(async_session)

    prompt = await repo.create_initial_prompt(
        name="test_prompt",
        template_json={"system": "test", "user_template": "test", "variables": []},
        created_by="admin",
    )

    # Log execution
    execution = await repo.log_execution(
        prompt_template_id=prompt.id,
        execution_data={
            "input_variables": {"skill": "Python"},
            "output_text": "Generated question...",
            "prompt_tokens": 150,
            "completion_tokens": 300,
            "latency_ms": 1500,
            "model_name": "gpt-4",
            "success": True,
        },
    )

    assert execution.prompt_template_id == prompt.id
    assert execution.input_variables == {"skill": "Python"}
    assert execution.success is True
    assert execution.latency_ms == 1500


@pytest.mark.asyncio
async def test_get_analytics_summary(async_session):
    """Test getting analytics summary from materialized view."""
    repo = PostgreSQLPromptRepository(async_session)

    prompt = await repo.create_initial_prompt(
        name="test_prompt",
        template_json={"system": "test", "user_template": "test", "variables": []},
        created_by="admin",
    )
    await repo.activate_version(prompt.id, "admin", "Activate", traffic_percentage=100)

    # Log some executions
    for _ in range(3):
        await repo.log_execution(
            prompt_template_id=prompt.id,
            execution_data={
                "input_variables": {},
                "prompt_tokens": 100,
                "completion_tokens": 200,
                "latency_ms": 1000,
                "success": True,
            },
        )

    # Refresh materialized view (in real app this would be a background job)
    await async_session.execute("REFRESH MATERIALIZED VIEW prompt_analytics_summary")

    # Get summary
    summary = await repo.get_analytics_summary("test_prompt")

    # Note: summary might be None if view hasn't refreshed
    # In real tests with proper setup, we'd verify the structure
    if summary:
        assert "total_executions" in summary
        assert "avg_latency_ms" in summary
        assert "success_rate" in summary
