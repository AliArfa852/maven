"""PostgreSQL support (decision D-2-1): URL driver pinning, dialect-neutral
column introspection for the startup migrations, and the email MCP server
reading accounts from a non-SQLite DATABASE_URL."""

from sqlalchemy import create_engine, text

from src.db_url import is_sqlite_url, with_installed_postgres_driver


def test_bare_postgres_url_uses_the_shipped_psycopg2_driver():
    assert with_installed_postgres_driver("postgresql://u:p@db:5432/maven") == \
        "postgresql+psycopg2://u:p@db:5432/maven"
    assert with_installed_postgres_driver("postgres://u@db/maven").startswith("postgresql+psycopg2://")


def test_explicit_drivers_and_other_databases_are_left_alone():
    for url in ("postgresql+psycopg://u@db/maven", "sqlite:///./data/app.db", "not a url"):
        assert with_installed_postgres_driver(url) == url


def test_is_sqlite_url():
    assert is_sqlite_url("sqlite:///./data/app.db") is True
    assert is_sqlite_url("postgresql://u@db/maven") is False


def test_inspected_table_info_matches_sqlite_pragma(tmp_path):
    from core.database import _inspected_table_info, _table_info

    engine = create_engine(f"sqlite:///{tmp_path / 't.db'}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE t (id TEXT PRIMARY KEY, name TEXT NOT NULL, note TEXT)"))
    with engine.connect() as conn:
        pragma = _table_info(conn, "t")
        inspected = _inspected_table_info(conn, "t")
        missing = _inspected_table_info(conn, "nope")
    # name, NOT NULL flag and primary-key flag agree with SQLite's own answer
    assert [(r[1], r[3], r[5]) for r in inspected] == [(r[1], r[3], r[5]) for r in pragma]
    assert missing == []


def test_email_server_uses_database_url_when_not_sqlite(monkeypatch, tmp_path):
    import mcp_servers.email_server as email_server

    # A non-SQLite URL is required to take this path; point it at a SQLite
    # engine through the cache so no PostgreSQL server is needed here.
    engine = create_engine(f"sqlite:///{tmp_path / 'accounts.db'}")
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE email_accounts (id TEXT, owner TEXT, name TEXT, is_default BOOLEAN,"
            " enabled BOOLEAN, imap_host TEXT, imap_port INT, imap_user TEXT, imap_password TEXT,"
            " imap_starttls BOOLEAN, smtp_host TEXT, smtp_port INT, smtp_security TEXT,"
            " smtp_user TEXT, smtp_password TEXT, from_address TEXT, created_at TEXT)"))
        conn.execute(text(
            "INSERT INTO email_accounts VALUES ('a1','alice','Work',1,1,'imap',993,'u','p',0,"
            "'smtp',587,'ssl','u','p','u@x','2026-01-01'),"
            "('a2','alice','Off',0,0,'imap',993,'u','p',0,'smtp',587,'ssl','u','p','u@x','2026-01-01')"))
    monkeypatch.setenv("DATABASE_URL", "postgresql://u@db/maven")
    monkeypatch.setattr(email_server, "_EXTERNAL_ENGINE", engine)
    rows = email_server._read_accounts_from_db()
    assert [r["id"] for r in rows] == ["a1"]  # disabled account filtered out


def test_email_server_keeps_sqlite_file_path_by_default(monkeypatch):
    import mcp_servers.email_server as email_server

    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert email_server._external_db_engine() is None
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./data/app.db")
    assert email_server._external_db_engine() is None


# ---------------------------------------------------------------------------
# Live PostgreSQL: runs only when MAVEN_AI_TEST_POSTGRES_URL points at a server
# whose user may create databases, e.g. postgresql://postgres@127.0.0.1:5432/postgres
# ---------------------------------------------------------------------------

import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

_PG = os.environ.get("MAVEN_AI_TEST_POSTGRES_URL", "")
_live = pytest.mark.skipif(not _PG, reason="set MAVEN_AI_TEST_POSTGRES_URL to run against PostgreSQL")
_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def empty_pg_database():
    from sqlalchemy.engine import make_url

    admin = create_engine(with_installed_postgres_driver(_PG), isolation_level="AUTOCOMMIT")
    name = f"maven_test_{uuid.uuid4().hex[:10]}"
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{name}"'))
    try:
        yield make_url(with_installed_postgres_driver(_PG)).set(database=name).render_as_string(hide_password=False)
    finally:
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()


def _run(args, data_dir, **env):
    return subprocess.run(
        [sys.executable, *args], cwd=_ROOT, capture_output=True, text=True, encoding="utf-8",
        env={**os.environ, "MAVEN_AI_DATA_DIR": str(data_dir), **env}, timeout=300,
    )


@_live
def test_copy_to_postgres_moves_rows_and_refuses_a_second_copy(tmp_path, empty_pg_database):
    # Build a SQLite app database with the app's own schema, plus a few rows.
    seed = (
        "from core.database import SessionLocal, Note\n"
        "db = SessionLocal()\n"
        "db.add_all([Note(id=f'n{i}', owner='alice', title=f't{i}', content='c') for i in range(3)])\n"
        "db.commit()\n"
    )
    sqlite_file = tmp_path / "app.db"
    # conftest sets DATABASE_URL to in-memory SQLite; children need a real file.
    proc = _run(["-c", seed], tmp_path, DATABASE_URL=f"sqlite:///{sqlite_file}")
    assert proc.returncode == 0, proc.stderr

    copy = _run(["scripts/maven-db", "copy-to-postgres", "--from", str(sqlite_file),
                 "--to", empty_pg_database], tmp_path)
    assert copy.returncode == 0, copy.stderr
    assert '"notes": 3' in copy.stdout

    with create_engine(empty_pg_database).connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM notes WHERE owner = 'alice'")).scalar() == 3

    again = _run(["scripts/maven-db", "copy-to-postgres", "--from", str(sqlite_file),
                  "--to", empty_pg_database], tmp_path)
    assert again.returncode != 0
    assert "already holds data" in again.stderr


@_live
def test_app_schema_and_migrations_start_cleanly_on_postgres(tmp_path, empty_pg_database):
    proc = _run(["-c", "import core.database"], tmp_path, DATABASE_URL=empty_pg_database)
    assert proc.returncode == 0, proc.stderr
    # The startup migrations used to log a PRAGMA syntax error each on PostgreSQL.
    assert "PRAGMA" not in proc.stderr
