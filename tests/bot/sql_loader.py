from __future__ import annotations

import hashlib
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DataSeedConfig:
    """Validated configuration for scenario-driven SQL seeding."""

    sql_path: Path
    interview_id: UUID
    question_ids: Sequence[UUID]


@dataclass(frozen=True)
class SQLFixtureResult:
    """Execution metadata for SQL fixtures."""

    sql_path: Path
    checksum: str
    statements_executed: int
    duration_ms: float


def build_data_seed_config(
    raw_config: dict | None,
    bot_root: Path,
) -> DataSeedConfig | None:
    """Validate and normalize raw data_seed configuration."""
    if not raw_config:
        return None

    sql_file = raw_config.get("sql_file")
    interview_id = raw_config.get("interview_id")

    if not sql_file or not interview_id:
        raise ValueError("data_seed requires sql_file and interview_id")

    sql_path = (bot_root / sql_file).resolve()
    fixtures_root = (bot_root / "fixtures" / "sql").resolve()

    if not sql_path.exists():
        raise FileNotFoundError(f"SQL fixture not found: {sql_path}")

    if not sql_path.is_relative_to(fixtures_root):
        raise ValueError(
            f"SQL fixture must live under {fixtures_root}, got {sql_path}",
        )

    question_ids_raw = raw_config.get("question_ids") or []
    if isinstance(question_ids_raw, str):
        question_ids_iterable = [_parse_uuid(question_ids_raw, "question_ids")]
    else:
        question_ids_iterable = [
            _parse_uuid(value, "question_ids") for value in question_ids_raw
        ]

    return DataSeedConfig(
        sql_path=sql_path,
        interview_id=_parse_uuid(interview_id, "interview_id"),
        question_ids=tuple(question_ids_iterable),
    )


async def execute_sql_fixture(engine: AsyncEngine, sql_path: Path) -> SQLFixtureResult:
    """Execute SQL statements contained in the given file."""
    _ensure_test_environment()

    sql_text = sql_path.read_text(encoding="utf-8")
    if not sql_text.strip():
        raise ValueError(f"SQL fixture is empty: {sql_path}")

    statements = _split_sql_statements(sql_text)
    if not statements:
        raise ValueError(f"No SQL statements found in {sql_path}")

    checksum = hashlib.sha256(sql_text.encode("utf-8")).hexdigest()
    start = time.perf_counter()

    async with engine.begin() as conn:
        for statement in statements:
            await conn.exec_driver_sql(statement)

    duration_ms = (time.perf_counter() - start) * 1000

    logger.info(
        "Executed SQL fixture %s (%d statements, %.1fms, sha=%s)",
        sql_path,
        len(statements),
        duration_ms,
        checksum,
    )

    return SQLFixtureResult(
        sql_path=sql_path,
        checksum=checksum,
        statements_executed=len(statements),
        duration_ms=duration_ms,
    )


def _ensure_test_environment() -> None:
    """Prevent SQL fixtures from running outside test environment."""
    environment = os.getenv("ENVIRONMENT", "").lower()
    if environment != "test":
        raise RuntimeError(
            "SQL fixtures can only run with ENVIRONMENT=test "
            "(current value: {!r})".format(environment or "undefined"),
        )


def _split_sql_statements(sql_text: str) -> list[str]:
    """Split SQL script into individual statements (semi-colon aware)."""
    statements: list[str] = []
    current: list[str] = []
    in_single = False
    in_double = False

    for char in sql_text:
        if char == "'" and not in_double:
            in_single = not in_single
        elif char == '"' and not in_single:
            in_double = not in_double

        if char == ";" and not in_single and not in_double:
            statement = "".join(current).strip()
            if statement:
                statements.append(statement)
            current = []
            continue

        current.append(char)

    tail = "".join(current).strip()
    if tail:
        statements.append(tail)

    return statements


def _parse_uuid(value: str, field_name: str) -> UUID:
    try:
        return UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid UUID for {field_name}: {value}") from exc


__all__ = [
    "DataSeedConfig",
    "SQLFixtureResult",
    "build_data_seed_config",
    "execute_sql_fixture",
]

