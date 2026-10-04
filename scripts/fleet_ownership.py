#!/usr/bin/env python3
"""Ownership gate for the .claude agent fleet.

Reads .claude/agents/OWNERSHIP.txt (ordered globs, first match wins) and checks
it against the tracked files in this repo.

  check                 every tracked file has an owner, every rule matches
                        something, every owner is a real agent (or `human`)
  who <path>...         print the owner of each path
  diff <owner> [base]   fail if the working tree / branch changes files that
                        <owner> does not own (base defaults to `dev`)
  summary               files per owner

Stdlib only, so it runs before the project venv exists. Exit 0 = pass.
"""
from __future__ import annotations

import fnmatch
import subprocess
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MAP_FILE = REPO / ".claude" / "agents" / "OWNERSHIP.txt"
AGENTS_DIR = REPO / ".claude" / "agents"
HUMAN = "human"


def load_rules() -> list[tuple[str, str, int]]:
    rules = []
    for lineno, raw in enumerate(MAP_FILE.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) != 2:
            sys.exit(f"OWNERSHIP.txt:{lineno}: expected '<glob> <owner>', got {raw!r}")
        rules.append((parts[0], parts[1], lineno))
    return rules


def known_owners() -> set[str]:
    names = {p.stem for p in AGENTS_DIR.glob("*.md") if p.stem.upper() != "README"}
    return names | {HUMAN}


def tracked_files() -> list[str]:
    """Tracked files plus untracked, non-ignored ones: a worker's new file
    needs an owner before it is ever committed."""
    out = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=REPO, capture_output=True, text=True, check=True,
    ).stdout
    return sorted({f for f in out.splitlines() if f})


SOURCE = "@source"  # owner = owner of the module the test is named after
SOURCE_DIRS = ("src/", "routes/", "services/", "core/", "mcp_servers/")
_source_stems: dict[str, str] | None = None


def _stems() -> dict[str, str]:
    """Map module stem -> path for tracked Python source, for @source rules."""
    global _source_stems
    if _source_stems is None:
        _source_stems = {}
        for f in tracked_files():
            if f.startswith(SOURCE_DIRS) and f.endswith(".py") and not f.endswith("__init__.py"):
                _source_stems.setdefault(Path(f).stem, f)
    return _source_stems


def _source_owner(path: str, rules) -> str | None:
    """tests/.../test_action_intents_x.py -> owner of src/action_intents.py.

    Longest underscore-token prefix of the test name that is a module stem wins.
    Returns None (fall through to later rules) when nothing matches.
    """
    name = Path(path).stem
    if not name.startswith("test_"):
        return None
    tokens = name[len("test_"):].split("_")
    stems = _stems()
    for n in range(len(tokens), 0, -1):
        target = stems.get("_".join(tokens[:n]))
        if target:
            return owner_of(target, rules)
    return None


def _match(path: str, rules):
    for pattern, owner, lineno in rules:
        if fnmatch.fnmatchcase(path, pattern):
            if owner == SOURCE:
                resolved = _source_owner(path, rules)
                if resolved is None:
                    continue
                return resolved, lineno
            return owner, lineno
    return None, None


def owner_of(path: str, rules) -> str | None:
    return _match(path.replace("\\", "/"), rules)[0]


def cmd_check(rules) -> int:
    files = tracked_files()
    owners = known_owners()
    failures = 0

    unknown = sorted({o for _, o, _ in rules if o not in owners and o != SOURCE})
    for o in unknown:
        print(f"FAIL unknown owner {o!r} (no .claude/agents/{o}.md)")
        failures += 1

    hits: Counter[int] = Counter()
    unowned = []
    for f in files:
        owner, lineno = _match(f, rules)
        if owner is None:
            unowned.append(f)
        else:
            hits[lineno] += 1
            if owner not in owners:
                print(f"FAIL {f} resolves to unknown owner {owner!r}")
                failures += 1

    for f in unowned:
        print(f"FAIL unowned file {f}")
    failures += len(unowned)

    for pattern, owner, lineno in rules:
        if hits[lineno] == 0:
            print(f"FAIL dead rule line {lineno}: {pattern} -> {owner} (matches no file, or is shadowed)")
            failures += 1

    print(f"{len(files)} tracked files, {len(rules)} rules, {failures} failure(s)")
    return 1 if failures else 0


def cmd_who(rules, paths) -> int:
    rc = 0
    for p in paths:
        o = owner_of(p, rules)
        print(f"{o or 'UNOWNED'}\t{p}")
        rc |= o is None
    return rc


def changed_files(base: str) -> list[str]:
    def git(*args):
        return subprocess.run(
            ["git", *args], cwd=REPO, capture_output=True, text=True, check=True
        ).stdout.splitlines()

    files = set(git("diff", "--name-only", f"{base}...HEAD"))
    files |= set(git("diff", "--name-only", "HEAD"))
    files |= set(git("ls-files", "--others", "--exclude-standard"))
    return sorted(f for f in files if f)


def cmd_diff(rules, owner: str, base: str) -> int:
    if owner not in known_owners():
        print(f"FAIL unknown owner {owner!r}")
        return 1
    bad = 0
    for f in changed_files(base):
        o = owner_of(f, rules)
        if o != owner:
            print(f"FAIL {f} is owned by {o or 'nobody'}, not {owner}")
            bad += 1
    print(f"ownership diff vs {base}: {bad} violation(s)")
    return 1 if bad else 0


def cmd_summary(rules) -> int:
    c = Counter(owner_of(f, rules) or "UNOWNED" for f in tracked_files())
    for owner, n in c.most_common():
        print(f"{n:6d}  {owner}")
    return 0


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    rules = load_rules()
    cmd, args = argv[0], argv[1:]
    if cmd == "check":
        return cmd_check(rules)
    if cmd == "who" and args:
        return cmd_who(rules, args)
    if cmd == "diff" and args:
        return cmd_diff(rules, args[0], args[1] if len(args) > 1 else "dev")
    if cmd == "summary":
        return cmd_summary(rules)
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
