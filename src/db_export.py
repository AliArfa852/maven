"""Portable table export/import for backups of non-SQLite databases.

maven-backup copies SQLite files directly, but a PostgreSQL database lives
outside data/, so it used to be missing from backups entirely. This writes
every table as JSON Lines (one file per table plus a manifest) that
`maven-db load-export` can load into an empty database of any kind.

Plain Python + SQLAlchemy: no pg_dump, so no client/server version matching.
Reading uses reflection, so importing this module has no side effects.
"""
from __future__ import annotations

import base64
import json
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path

MANIFEST = "manifest.json"
FORMAT_VERSION = 1


def _encode(value):
    if isinstance(value, datetime):
        return {"$dt": value.isoformat()}
    if isinstance(value, date):
        return {"$d": value.isoformat()}
    if isinstance(value, time):
        return {"$t": value.isoformat()}
    if isinstance(value, (bytes, bytearray, memoryview)):
        return {"$b64": base64.b64encode(bytes(value)).decode("ascii")}
    if isinstance(value, Decimal):
        return {"$dec": str(value)}
    raise TypeError(f"cannot export {type(value).__name__}")


def _decode(value):
    if isinstance(value, dict) and len(value) == 1:
        (key, raw), = value.items()
        if key == "$dt":
            return datetime.fromisoformat(raw)
        if key == "$d":
            return date.fromisoformat(raw)
        if key == "$t":
            return time.fromisoformat(raw)
        if key == "$b64":
            return base64.b64decode(raw)
        if key == "$dec":
            return Decimal(raw)
    return value


def export_tables(engine, out_dir: Path) -> dict:
    """Write every table of ``engine`` to ``out_dir``. Returns the manifest."""
    from sqlalchemy import MetaData, select

    out_dir.mkdir(parents=True, exist_ok=True)
    meta = MetaData()
    meta.reflect(bind=engine)
    counts = {}
    with engine.connect() as conn:
        for table in meta.sorted_tables:
            path = out_dir / f"{table.name}.jsonl"
            n = 0
            with open(path, "w", encoding="utf-8") as fh:
                result = conn.execution_options(stream_results=True).execute(select(table))
                cols = list(result.keys())
                for row in result:
                    fh.write(json.dumps(dict(zip(cols, row)), default=_encode, ensure_ascii=False))
                    fh.write("\n")
                    n += 1
            counts[table.name] = n
    manifest = {
        "format_version": FORMAT_VERSION,
        "dialect": engine.dialect.name,
        "exported_at": datetime.utcnow().isoformat() + "Z",
        "tables": counts,
    }
    (out_dir / MANIFEST).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def read_manifest(in_dir: Path) -> dict:
    path = in_dir / MANIFEST
    if not path.exists():
        raise FileNotFoundError(f"no {MANIFEST} in {in_dir}")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("format_version") != FORMAT_VERSION:
        raise ValueError(f"unsupported export format {manifest.get('format_version')!r}")
    return manifest


def iter_rows(in_dir: Path, table: str, batch: int = 500):
    """Yield lists of decoded row dicts for ``table`` (empty if not exported)."""
    path = in_dir / f"{table}.jsonl"
    if not path.exists():
        return
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                rows.append({k: _decode(v) for k, v in json.loads(line).items()})
                if len(rows) >= batch:
                    yield rows
                    rows = []
    if rows:
        yield rows


def reset_sequences(conn, tables) -> None:
    """Move PostgreSQL id sequences past copied rows (no-op elsewhere)."""
    from sqlalchemy import text

    if conn.dialect.name != "postgresql":
        return
    for table in tables:
        pk = list(table.primary_key.columns)
        if len(pk) != 1:
            continue
        col = pk[0]
        try:
            is_int = col.type.python_type is int
        except NotImplementedError:
            is_int = False
        if not is_int:
            continue
        seq = conn.execute(text("SELECT pg_get_serial_sequence(:t, :c)"),
                           {"t": table.name, "c": col.name}).scalar()
        if seq:
            conn.execute(text(
                f'SELECT setval(:s, COALESCE((SELECT MAX("{col.name}") FROM "{table.name}"), 0) + 1, false)'),
                {"s": seq})
