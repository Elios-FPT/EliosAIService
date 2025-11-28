from pathlib import Path
from uuid import UUID

import pytest

from tests.bot import sql_loader


def test_build_data_seed_config_valid():
    bot_root = Path(__file__).resolve().parents[2] / "bot"
    raw = {
        "sql_file": "fixtures/sql/java-backend-beginner.sql",
        "interview_id": "b323c6a1-4749-4922-876f-72b6c426b2a6",
        "question_ids": [
            "453523fb-8ac5-43d9-8aa8-856803fa950d",
            "f405aaad-3e97-401f-bd5c-d68c62bb1445",
        ],
    }

    config = sql_loader.build_data_seed_config(raw, bot_root)

    assert config is not None
    assert config.sql_path.name == "java-backend-beginner.sql"
    assert config.interview_id == UUID("b323c6a1-4749-4922-876f-72b6c426b2a6")
    assert list(config.question_ids)[0] == UUID("453523fb-8ac5-43d9-8aa8-856803fa950d")


def test_build_data_seed_config_rejects_outside_fixture_dir(tmp_path: Path):
    bot_root = tmp_path
    (bot_root / "fixtures" / "sql").mkdir(parents=True)
    rogue_sql = bot_root / "rogue.sql"
    rogue_sql.write_text("SELECT 1;")

    raw = {
        "sql_file": "rogue.sql",
        "interview_id": "b323c6a1-4749-4922-876f-72b6c426b2a6",
    }

    with pytest.raises(ValueError):
        sql_loader.build_data_seed_config(raw, bot_root)


def test_split_sql_statements_handles_semicolons_in_strings():
    script = "DELETE FROM t; INSERT INTO t VALUES ('foo;bar');"
    statements = sql_loader._split_sql_statements(script)

    assert len(statements) == 2
    assert statements[1].endswith("('foo;bar')")

