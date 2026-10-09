"""Database URL helpers with no import-time side effects.

core/database.py runs init_db() (create_all + migrations) when imported, and
importing anything under core/ imports it (core/__init__.py), so
helper processes such as the email MCP server use this module instead.
"""
from sqlalchemy.engine import make_url


def with_installed_postgres_driver(url: str) -> str:
    """Pin a bare ``postgresql://`` URL to psycopg2, the driver we ship.

    SQLAlchemy 2.1 made psycopg (v3) the default for ``postgresql://``, which
    is not installed, so every Postgres install failed at create_engine with
    "No module named 'psycopg'". An explicit driver (``postgresql+psycopg://``)
    is left alone.
    """
    try:
        parsed = make_url(url)
    except Exception:
        return url
    if parsed.drivername in ("postgresql", "postgres"):
        return parsed.set(drivername="postgresql+psycopg2").render_as_string(hide_password=False)
    return url


def is_sqlite_url(url: str) -> bool:
    try:
        return make_url(url).get_backend_name() == "sqlite"
    except Exception:
        return True
