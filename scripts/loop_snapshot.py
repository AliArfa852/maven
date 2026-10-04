#!/usr/bin/env python3
"""Step 0 of every agent-fleet tick: a verified, restorable snapshot.

No snapshot, no tick. `create` exits non-zero on ANY failure and the tick must
abort.

  create              snapshot git state, the (gitignored) fleet config, and
                      the data dir (SQLite via the online backup API)
  verify <id>         re-check file hashes and SQLite integrity
  list                list snapshots
  restore <id> --to <empty dir>
                      restore the data-dir copy into an EMPTY directory that is
                      not the live data dir. Prints the git command to recover
                      code state; it never runs it. Swapping the restored data in
                      is a human step, with the app stopped.

What is captured:
  git   `git stash create` (tracked changes, or HEAD when clean) pinned under
        refs/loop-snapshots/<id> so it survives gc. The working tree is never
        touched. Untracked, non-ignored files are copied, since a stash commit
        does not include them.
  fleet .claude/ (minus snapshots/ and _to_delete/), because it is gitignored
        here and self-review edits agent files.
  data  ODYSSEUS_DATA_DIR, else <repo>/data, the same resolution as
        src/constants.py. SQLite files go through sqlite3's backup API: a plain
        copy of a live WAL database is a torn file. Every backup gets
        `PRAGMA integrity_check`. Other files under LOOP_SNAPSHOT_MAX_FILE_MB are
        copied and hashed.

Snapshots live in .claude/snapshots/ (override: LOOP_SNAPSHOT_DIR). Nothing is
ever pruned automatically. They hold copies of data/, which may include
encrypted secrets and keys, so they stay on this machine.

Stdlib only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SNAP_ROOT = Path(os.environ.get("LOOP_SNAPSHOT_DIR", REPO / ".claude" / "snapshots"))
MAX_FILE = int(os.environ.get("LOOP_SNAPSHOT_MAX_FILE_MB", "200")) * 1024 * 1024
MAX_TOTAL = int(os.environ.get("LOOP_SNAPSHOT_MAX_TOTAL_MB", "4096")) * 1024 * 1024
SQLITE_MAGIC = b"SQLite format 3\x00"
SQLITE_SIDECARS = ("-wal", "-shm", "-journal")
FLEET_SKIP = {"snapshots", "_to_delete"}


class SnapshotError(Exception):
    pass


def data_dir() -> Path:
    env = os.environ.get("ODYSSEUS_DATA_DIR")
    return Path(env).resolve() if env else (REPO / "data").resolve()


def git(*args: str) -> str:
    r = subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True)
    if r.returncode != 0:
        raise SnapshotError(f"git {' '.join(args)} failed: {r.stderr.strip()}")
    return r.stdout.strip()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def is_sqlite(path: Path) -> bool:
    try:
        with open(path, "rb") as f:
            return f.read(16) == SQLITE_MAGIC
    except OSError:
        return False


def integrity(path: Path) -> str:
    conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        return conn.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        conn.close()


def backup_sqlite(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    # Open the source read/write: a read-only open of a WAL database cannot
    # always build its -shm index. backup() reads a consistent snapshot of
    # main db + WAL and changes no rows (closing the last connection may
    # checkpoint the WAL, which moves pages but not data).
    s = sqlite3.connect(str(src), timeout=30)
    d = sqlite3.connect(str(dst))
    try:
        s.backup(d)
    finally:
        d.close()
        s.close()
    result = integrity(dst)
    if result != "ok":
        raise SnapshotError(f"integrity_check failed for backup of {src}: {result}")


def snap_git(out: Path, manifest: dict) -> None:
    head = git("rev-parse", "HEAD")
    stash = git("stash", "create")  # empty when the tree is clean
    sha = stash or head
    ref = f"refs/loop-snapshots/{out.name}"
    git("update-ref", ref, sha)
    untracked = [f for f in git("ls-files", "--others", "--exclude-standard").splitlines() if f]
    for rel in untracked:
        src = REPO / rel
        if src.is_file():
            dst = out / "untracked" / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    manifest["git"] = {
        "head": head,
        "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
        "snapshot_commit": sha,
        "dirty": bool(stash),
        "ref": ref,
        "untracked": untracked,
    }


def snap_fleet(out: Path, manifest: dict) -> None:
    src = REPO / ".claude"
    if not src.is_dir():
        manifest["fleet"] = None
        return
    dst = out / "fleet"
    shutil.copytree(
        src, dst,
        ignore=lambda d, names: [n for n in names if Path(d) == src and n in FLEET_SKIP],
    )
    manifest["fleet"] = sorted(str(p.relative_to(dst).as_posix()) for p in dst.rglob("*") if p.is_file())


def snap_data(out: Path, manifest: dict) -> None:
    ddir = data_dir()
    info = {"path": str(ddir), "exists": ddir.is_dir(), "sqlite": {}, "files": {}, "skipped": []}
    manifest["data"] = info
    if not ddir.is_dir():
        return
    # Never let the snapshot recurse into itself.
    if SNAP_ROOT.resolve().is_relative_to(ddir):
        raise SnapshotError(f"snapshot dir {SNAP_ROOT} is inside the data dir {ddir}")
    total = 0
    for p in sorted(ddir.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(ddir).as_posix()
        if p.name.endswith(SQLITE_SIDECARS):
            continue  # folded into the backup of the main database
        dst = out / "data" / rel
        if is_sqlite(p):
            backup_sqlite(p, dst)
            info["sqlite"][rel] = {"sha256": sha256(dst), "integrity": "ok"}
            total += dst.stat().st_size
        else:
            size = p.stat().st_size
            if size > MAX_FILE:
                info["skipped"].append({"file": rel, "bytes": size})
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dst)
            info["files"][rel] = sha256(dst)
            total += size
        if total > MAX_TOTAL:
            raise SnapshotError(
                f"data snapshot exceeds LOOP_SNAPSHOT_MAX_TOTAL_MB ({MAX_TOTAL >> 20} MB); "
                "raise the cap deliberately rather than snapshotting partially"
            )
    info["bytes"] = total


def cmd_create(_args) -> int:
    snap_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    out = SNAP_ROOT / snap_id
    out.mkdir(parents=True, exist_ok=False)
    manifest: dict = {"id": snap_id, "created": snap_id, "complete": False}
    try:
        snap_git(out, manifest)
        snap_fleet(out, manifest)
        snap_data(out, manifest)
        manifest["complete"] = True
    except Exception as e:  # any failure: no snapshot, no tick
        manifest["error"] = f"{type(e).__name__}: {e}"
        (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print(f"SNAPSHOT FAILED {snap_id}: {manifest['error']}", file=sys.stderr)
        return 1
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    d = manifest["data"]
    print(
        f"SNAPSHOT OK {snap_id} git={manifest['git']['snapshot_commit'][:10]}"
        f"{' (dirty)' if manifest['git']['dirty'] else ''} "
        f"untracked={len(manifest['git']['untracked'])} "
        f"sqlite={len(d['sqlite'])} files={len(d['files'])} "
        f"data={'present' if d['exists'] else 'absent'} skipped={len(d['skipped'])}"
    )
    return 0


def load(snap_id: str) -> tuple[Path, dict]:
    out = SNAP_ROOT / snap_id
    mf = out / "manifest.json"
    if not mf.is_file():
        raise SnapshotError(f"no snapshot {snap_id} in {SNAP_ROOT}")
    manifest = json.loads(mf.read_text(encoding="utf-8"))
    if not manifest.get("complete"):
        raise SnapshotError(f"snapshot {snap_id} is incomplete: {manifest.get('error')}")
    return out, manifest


def verify_dir(root: Path, data: dict) -> list[str]:
    problems = []
    for rel, meta in data.get("sqlite", {}).items():
        p = root / rel
        if not p.is_file():
            problems.append(f"missing {rel}")
            continue
        if sha256(p) != meta["sha256"]:
            problems.append(f"hash mismatch {rel}")
        res = integrity(p)
        if res != "ok":
            problems.append(f"integrity {rel}: {res}")
    for rel, digest in data.get("files", {}).items():
        p = root / rel
        if not p.is_file():
            problems.append(f"missing {rel}")
        elif sha256(p) != digest:
            problems.append(f"hash mismatch {rel}")
    return problems


def cmd_verify(args) -> int:
    out, manifest = load(args.id)
    problems = verify_dir(out / "data", manifest["data"])
    try:
        git("cat-file", "-e", manifest["git"]["snapshot_commit"])
    except SnapshotError:
        problems.append("git snapshot commit missing")
    for p in problems:
        print(f"FAIL {p}")
    print(f"verify {args.id}: {'OK' if not problems else f'{len(problems)} problem(s)'}")
    return 1 if problems else 0


def cmd_list(_args) -> int:
    if not SNAP_ROOT.is_dir():
        print("no snapshots")
        return 0
    for d in sorted(SNAP_ROOT.iterdir()):
        mf = d / "manifest.json"
        if mf.is_file():
            m = json.loads(mf.read_text(encoding="utf-8"))
            state = "ok" if m.get("complete") else f"INCOMPLETE ({m.get('error')})"
            print(f"{d.name}  {state}  git={m.get('git', {}).get('snapshot_commit', '?')[:10]}")
    return 0


def cmd_restore(args) -> int:
    out, manifest = load(args.id)
    target = Path(args.to).resolve()
    live = data_dir()
    if target == live or target.is_relative_to(live) or live.is_relative_to(target):
        print(f"REFUSED: {target} is or overlaps the live data dir {live}", file=sys.stderr)
        return 2
    if target.exists() and any(target.iterdir()):
        print(f"REFUSED: {target} is not empty", file=sys.stderr)
        return 2
    problems = verify_dir(out / "data", manifest["data"])
    if problems:
        print("REFUSED: snapshot failed verification: " + "; ".join(problems), file=sys.stderr)
        return 1
    src = out / "data"
    if src.is_dir():
        shutil.copytree(src, target, dirs_exist_ok=True)
    else:
        target.mkdir(parents=True, exist_ok=True)
    problems = verify_dir(target, manifest["data"])
    if problems:
        print("RESTORE FAILED verification: " + "; ".join(problems), file=sys.stderr)
        return 1
    g = manifest["git"]
    print(f"restored data snapshot {args.id} -> {target} (verified)")
    print("To recover code state (human step; review first):")
    print(f"  git switch -c restore/{args.id} {g['head']}")
    if g["dirty"]:
        print(f"  git stash apply {g['snapshot_commit']}")
    if g["untracked"]:
        print(f"  untracked files are in {out / 'untracked'}")
    print(f"To use the data: stop the app, then point ODYSSEUS_DATA_DIR at {target}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("create")
    sub.add_parser("list")
    v = sub.add_parser("verify")
    v.add_argument("id")
    r = sub.add_parser("restore")
    r.add_argument("id")
    r.add_argument("--to", required=True)
    args = ap.parse_args()
    try:
        return {"create": cmd_create, "list": cmd_list, "verify": cmd_verify, "restore": cmd_restore}[args.cmd](args)
    except SnapshotError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
