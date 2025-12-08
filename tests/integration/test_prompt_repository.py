"""Integration tests for PostgreSQLPromptRepository with decomposed fields."""

from decimal import Decimal
import pytest

from src.adapters.persistence.postgres_prompt_repository import PostgreSQLPromptRepository


def prompt_kwargs():
    return dict(
        system_prompt="sys",
        user_template="Hello {name}",
        input_variables=["name"],
        partial_variables={},
        output_schema={},
        temperature=Decimal("0.3"),
        max_tokens=128,
        top_p=Decimal("0.95"),
        frequency_penalty=Decimal("0"),
        presence_penalty=Decimal("0"),
        created_by="tester",
    )


@pytest.mark.asyncio
async def test_create_and_activate_prompt(async_session):
    repo = PostgreSQLPromptRepository(async_session)
    prompt = await repo.create_initial_prompt(name="greeting", **prompt_kwargs())
    await repo.activate_version(prompt.id, changed_by="tester", reason="activate v1")

    active = await repo.get_active_prompt("greeting")
    assert active is not None
    assert active.version == 1
    assert active.is_active is True


@pytest.mark.asyncio
async def test_create_new_version_and_rollback(async_session):
    repo = PostgreSQLPromptRepository(async_session)
    base = await repo.create_initial_prompt(name="greeting", **prompt_kwargs())
    await repo.activate_version(base.id, changed_by="tester", reason="activate v1")

    v2 = await repo.create_new_version(
        name="greeting",
        parent_version=1,
        system_prompt="sys2",
        user_template="Hi {name}",
        input_variables=["name"],
        partial_variables={},
        output_schema={},
        temperature=Decimal("0.2"),
        max_tokens=64,
        top_p=Decimal("0.9"),
        frequency_penalty=Decimal("0"),
        presence_penalty=Decimal("0"),
        change_summary="tweak",
        created_by="tester",
    )
    assert v2.version == 2
    assert v2.is_active is False

    v3 = await repo.rollback_to_version(
        name="greeting",
        target_version=1,
        changed_by="tester",
        reason="rollback to stable",
    )
    assert v3.version == 3
    assert v3.system_prompt == "sys"

