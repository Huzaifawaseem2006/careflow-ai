import pytest
from careflow.database import database_engine


def test_only_postgresql_psycopg_urls_are_accepted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite:///secret-value")
    with pytest.raises(ValueError, match="^Invalid database configuration$"):
        database_engine()
