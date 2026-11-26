from unittest.mock import Mock
import pytest
import config
import src.db as db

@pytest.mark.parametrize(("url", "expected"), [
    ("postgres://user:pass@localhost:5432/retiro", "postgresql+psycopg://user:pass@localhost:5432/retiro"),
    ("postgresql://user:pass@localhost:5432/retiro", "postgresql+psycopg://user:pass@localhost:5432/retiro"),
    ("postgresql+psycopg://user:pass@localhost/retiro", "postgresql+psycopg://user:pass@localhost/retiro"),
    ("sqlite://", "sqlite://"),
    ("sqlite:///:memory:", "sqlite:///:memory:"),
])
def test_normalize_database_url(url, expected):
    assert db.normalize_database_url(url) == expected

def test_make_engine_uses_config_url_when_argument_is_none(monkeypatch):
    create_engine = Mock(return_value=object())
    monkeypatch.setattr(db, "create_engine", create_engine)
    monkeypatch.setattr(config, "DATABASE_URL", "sqlite:///:memory:")
    assert db.make_engine() is create_engine.return_value
    create_engine.assert_called_once_with("sqlite:///:memory:")

def test_make_engine_normalizes_postgres_and_sets_connection_timeout(monkeypatch):
    create_engine = Mock(return_value=object())
    monkeypatch.setattr(db, "create_engine", create_engine)
    assert db.make_engine("postgres://user:pass@localhost/retiro") is create_engine.return_value
    create_engine.assert_called_once_with("postgresql+psycopg://user:pass@localhost/retiro", connect_args={"connect_timeout": config.DB_CONNECT_TIMEOUT_SECONDS})

def test_make_engine_does_not_set_postgres_timeout_for_sqlite(monkeypatch):
    create_engine = Mock(return_value=object())
    monkeypatch.setattr(db, "create_engine", create_engine)
    db.make_engine("sqlite:///:memory:")
    create_engine.assert_called_once_with("sqlite:///:memory:")
