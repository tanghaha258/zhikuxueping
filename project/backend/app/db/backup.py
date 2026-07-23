import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def create_sqlite_backup(database_url: str, destination_dir: str | Path) -> Path:
    source_path = _sqlite_database_path(database_url)
    if not source_path.is_file():
        raise ValueError("SQLite database file does not exist")

    destination = Path(destination_dir)
    destination.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = destination / f"{source_path.stem}-{timestamp}.db"
    temporary_path = backup_path.with_suffix(".tmp")

    try:
        source = sqlite3.connect(source_path)
        target = sqlite3.connect(temporary_path)
        try:
            source.backup(target)
        finally:
            target.close()
            source.close()
        os.replace(temporary_path, backup_path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise

    return backup_path


def restore_sqlite_backup(backup_path: str | Path, database_url: str) -> None:
    """Restore a SQLite snapshot through an adjacent temporary file and atomic replace.

    Callers must stop application processes that hold the target database open
    before invoking this explicit operational action.
    """
    source_path = Path(backup_path)
    target_path = _sqlite_database_path(database_url)
    if not source_path.is_file():
        raise ValueError("SQLite backup file does not exist")
    if not target_path.is_file():
        raise ValueError("SQLite target database file does not exist")
    if source_path.resolve() == target_path.resolve():
        raise ValueError("SQLite backup and target must be different files")

    temporary_path = target_path.with_suffix(f"{target_path.suffix}.restore.tmp")
    try:
        source = sqlite3.connect(source_path)
        target = sqlite3.connect(temporary_path)
        try:
            source.backup(target)
        finally:
            target.close()
            source.close()

        restored = sqlite3.connect(temporary_path)
        try:
            restored.execute("PRAGMA integrity_check").fetchone()
        finally:
            restored.close()
        os.replace(temporary_path, target_path)
    except Exception:
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def _sqlite_database_path(database_url: str) -> Path:
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        raise ValueError("SQLite database URL is required")

    database_path = database_url.removeprefix(prefix)
    if database_path == ":memory:":
        raise ValueError("SQLite in-memory databases cannot be backed up")
    return Path(database_path)
