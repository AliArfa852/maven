"""maven-backup covers the data folder the app really uses and, for a
non-SQLite database, exports every table (src/db_export.py)."""

import importlib.machinery
import importlib.util
import os
import subprocess
import sys
import tarfile
import uuid
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import Column, DateTime, Integer, LargeBinary, MetaData, Numeric, String, Table, create_engine

from src import db_export

ROOT = Path(__file__).resolve().parent.parent


def test_export_round_trips_types(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'src.db'}")
    meta = MetaData()
    t = Table("things", meta, Column("id", Integer, primary_key=True), Column("name", String),
              Column("at", DateTime), Column("blob", LargeBinary), Column("price", Numeric(10, 2)))
    meta.create_all(engine)
    row = {"id": 1, "name": "Zoë", "at": datetime(2026, 1, 2, 3, 4, 5), "blob": b"\x00\xff",
           "price": Decimal("12.50")}
    with engine.begin() as conn:
        conn.execute(t.insert(), [row])
    manifest = db_export.export_tables(engine, tmp_path / "out")
    assert manifest["tables"] == {"things": 1}
    assert db_export.read_manifest(tmp_path / "out")["dialect"] == "sqlite"
    (batch,) = list(db_export.iter_rows(tmp_path / "out", "things"))
    got = batch[0]
    assert got["name"] == "Zoë" and got["at"] == row["at"] and got["blob"] == row["blob"]
    assert Decimal(str(got["price"])) == Decimal("12.50")
    assert list(db_export.iter_rows(tmp_path / "out", "missing")) == []


def test_unknown_export_format_is_refused(tmp_path):
    (tmp_path / "manifest.json").write_text('{"format_version": 99, "tables": {}}', encoding="utf-8")
    with pytest.raises(ValueError):
        db_export.read_manifest(tmp_path)


def _load_backup_module(monkeypatch, data_dir: Path):
    path = ROOT / "scripts" / "maven-backup"
    loader = importlib.machinery.SourceFileLoader(f"maven_backup_{uuid.uuid4().hex}", str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    monkeypatch.setattr(module, "_DATA_DIR", data_dir)
    monkeypatch.setattr(module, "_REPO_ROOT", data_dir.parent)
    monkeypatch.setattr(module, "_BACKUP_DIR", data_dir.parent / "backups")
    return module


def test_custom_data_folder_is_backed_up_as_data_and_restored_in_place(tmp_path, monkeypatch, capsys):
    data_dir = tmp_path / "company-data"   # not named "data" (MAVEN_AI_DATA_DIR)
    (data_dir / "sub").mkdir(parents=True)
    (data_dir / "sub" / "a.txt").write_text("hello", encoding="utf-8")
    (data_dir / "_db_export").mkdir()
    (data_dir / "_db_export" / "stale.jsonl").write_text("{}", encoding="utf-8")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    mod = _load_backup_module(monkeypatch, data_dir)
    out = tmp_path / "b.tar.gz"
    mod.cmd_snapshot(type("A", (), {"out": str(out), "include_research": False,
                                    "include_attachments": False, "pretty": False})())
    names = tarfile.open(out).getnames()
    assert "data/sub/a.txt" in names
    assert not any("_db_export" in n for n in names)   # a restored export is never re-archived

    (data_dir / "sub" / "a.txt").write_text("changed", encoding="utf-8")
    mod.cmd_restore(type("A", (), {"path": str(out), "yes": True, "pretty": False})())
    assert (data_dir / "sub" / "a.txt").read_text(encoding="utf-8") == "hello"
    assert any(p.name.startswith("company-data.before-restore-") for p in tmp_path.iterdir())


_PG = os.environ.get("MAVEN_AI_TEST_POSTGRES_URL", "")


@pytest.mark.skipif(not _PG, reason="set MAVEN_AI_TEST_POSTGRES_URL to run against PostgreSQL")
def test_postgres_backup_restore_and_load(tmp_path):
    from sqlalchemy import text
    from sqlalchemy.engine import make_url
    from src.db_url import with_installed_postgres_driver

    admin = create_engine(with_installed_postgres_driver(_PG), isolation_level="AUTOCOMMIT")
    names = [f"maven_bk_{uuid.uuid4().hex[:8]}" for _ in range(2)]
    with admin.connect() as c:
        for n in names:
            c.execute(text(f'CREATE DATABASE "{n}"'))
    base = make_url(with_installed_postgres_driver(_PG))
    src_url, dst_url = (base.set(database=n).render_as_string(hide_password=False) for n in names)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    env = {**os.environ, "MAVEN_AI_DATA_DIR": str(data_dir), "DATABASE_URL": src_url}
    run = lambda *a, **kw: subprocess.run([sys.executable, *a], cwd=ROOT, env={**env, **kw},
                                          capture_output=True, text=True, encoding="utf-8", timeout=300)
    try:
        seed = run("-c", "from core.database import SessionLocal, Note\n"
                         "db = SessionLocal(); db.add_all([Note(id=f'n{i}', owner='a', title='t', content='c')"
                         " for i in range(4)]); db.commit()")
        assert seed.returncode == 0, seed.stderr
        backup = tmp_path / "b.tar.gz"
        snap = run("scripts/maven-backup", "snapshot", "--out", str(backup))
        assert snap.returncode == 0, snap.stderr
        assert '"exported": true' in snap.stdout
        restore = run("scripts/maven-backup", "restore", str(backup), "--yes")
        assert restore.returncode == 0 and "load-export" in restore.stdout, restore.stderr
        load = run("scripts/maven-db", "load-export", str(data_dir / "_db_export"), "--to", dst_url)
        assert load.returncode == 0, load.stderr
        with create_engine(dst_url).connect() as c:
            assert c.execute(text("SELECT COUNT(*) FROM notes")).scalar() == 4
        again = run("scripts/maven-db", "load-export", str(data_dir / "_db_export"), "--to", dst_url)
        assert again.returncode != 0 and "already holds data" in again.stderr
    finally:
        with admin.connect() as c:
            for n in names:
                c.execute(text(f'DROP DATABASE IF EXISTS "{n}" WITH (FORCE)'))
        admin.dispose()
