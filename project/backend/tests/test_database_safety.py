import sqlite3

import pytest

from app.db import session
from app.db.backup import create_sqlite_backup, restore_sqlite_backup


class FakeSession:
    def __init__(self):
        self.rollback_calls = 0
        self.close_calls = 0

    def rollback(self):
        self.rollback_calls += 1

    def close(self):
        self.close_calls += 1


def test_get_db_rolls_back_when_request_raises(monkeypatch):
    fake_session = FakeSession()
    monkeypatch.setattr(session, "SessionLocal", lambda: fake_session)
    dependency = session.get_db()

    assert next(dependency) is fake_session
    with pytest.raises(RuntimeError, match="request failed"):
        dependency.throw(RuntimeError("request failed"))

    assert fake_session.rollback_calls == 1
    assert fake_session.close_calls == 1


def test_test_engine_uses_an_isolated_temporary_database(test_engine):
    assert "data/test.db" not in str(test_engine.url)


def test_create_sqlite_backup_copies_consistent_database(tmp_path):
    source = tmp_path / "source.db"
    with sqlite3.connect(source) as connection:
        connection.execute("CREATE TABLE records (value TEXT)")
        connection.execute("INSERT INTO records (value) VALUES ('preserved')")

    backup_path = create_sqlite_backup(
        f"sqlite:///{source.as_posix()}",
        tmp_path / "backups",
    )

    assert backup_path.exists()
    with sqlite3.connect(backup_path) as connection:
        assert connection.execute("SELECT value FROM records").fetchone() == ("preserved",)


def test_create_sqlite_backup_rejects_non_sqlite_url(tmp_path):
    with pytest.raises(ValueError, match="SQLite"):
        create_sqlite_backup("postgresql://user:secret@localhost/platform", tmp_path)

    assert list(tmp_path.iterdir()) == []


def test_restore_sqlite_backup_atomically_replaces_live_database(tmp_path):
    live_database = tmp_path / "live.db"
    connection = sqlite3.connect(live_database)
    try:
        connection.execute("CREATE TABLE records (value TEXT)")
        connection.execute("INSERT INTO records (value) VALUES ('snapshot')")
        connection.commit()
    finally:
        connection.close()

    backup_path = create_sqlite_backup(f"sqlite:///{live_database.as_posix()}", tmp_path / "backups")
    connection = sqlite3.connect(live_database)
    try:
        connection.execute("DELETE FROM records")
        connection.execute("INSERT INTO records (value) VALUES ('newer')")
        connection.commit()
    finally:
        connection.close()

    restore_sqlite_backup(backup_path, f"sqlite:///{live_database.as_posix()}")

    connection = sqlite3.connect(live_database)
    try:
        assert connection.execute("SELECT value FROM records").fetchone() == ("snapshot",)
    finally:
        connection.close()
