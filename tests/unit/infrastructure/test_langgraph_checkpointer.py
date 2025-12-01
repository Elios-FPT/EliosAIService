import pytest

from src.infrastructure.database.langgraph_checkpointer import (
    _convert_to_standard_postgres_url,
    _detect_endpoint_type,
)


def test_detect_endpoint_type_identifies_pooler():
    url = "postgresql+asyncpg://user:pass@ep-demo-pooler.us-east-1.aws.neon.tech/db"
    assert _detect_endpoint_type(url) == "pooler"


def test_detect_endpoint_type_marks_direct_neon():
    url = "postgresql://user:pass@ep-demo.us-east-1.aws.neon.tech/db"
    assert _detect_endpoint_type(url) == "direct"


def test_detect_endpoint_type_unknown_for_custom_host():
    url = "postgresql://localhost:5432/db"
    assert _detect_endpoint_type(url) == "unknown"


@pytest.mark.parametrize(
    "sqlalchemy_url,expected",
    [
        (
            "postgresql+asyncpg://user:pass@ep-demo-pooler.us-east-1.aws.neon.tech/db",
            "postgresql://user:pass@ep-demo.us-east-1.aws.neon.tech/db?sslmode=require&keepalives_idle=240&keepalives_interval=30&keepalives_count=3",
        ),
        (
            "postgresql+asyncpg://user:pass@localhost:5432/db",
            "postgresql://user:pass@localhost:5432/db?keepalives_idle=240&keepalives_interval=30&keepalives_count=3",
        ),
    ],
)
def test_convert_to_standard_postgres_url_removes_pooler_and_adds_keepalive(sqlalchemy_url, expected):
    assert _convert_to_standard_postgres_url(sqlalchemy_url) == expected

