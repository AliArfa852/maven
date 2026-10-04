#!/usr/bin/env python3
"""Verification gate for the agent fleet. Exit 0 = green, anything else = red.

  python scripts/fleet_gate.py [--owner <agent>] [--base dev] [--focus <pytest args>]

Checks, in order (all run, and the verdict is the worst):
  1. syntax       python -m compileall (the same dirs CI compiles) and
                  node --check on changed static JS (vendored static/lib skipped)
  2. ownership    fleet_ownership.py check, plus `diff <owner>` when --owner is
                  given: a branch may only touch files its ticket owner owns
  3. weakening    in changed tests/ files: added skip/xfail, removed asserts
                  outnumbering added ones, or trivial asserts. These are P0
                  suspects for a human, never auto-landed
  4. suite        full pytest run. Failures not listed in
                  .claude/loop/gate-baseline.txt are NEW and fail the gate.
                  Collected test count below the baseline's floor fails the
                  gate (tests were deleted or stopped collecting)

--focus runs only the given pytest selection: fast feedback for a worker, and
NEVER sufficient to land. Landing requires a full run (no --focus).

--propose-baseline writes .claude/loop/gate-baseline.proposed.txt. Only the
human may promote it to gate-baseline.txt; agents are denied edits to that file.

Uses the project venv when present. Exit codes: 0 green, 1 red, 3 needs human
(weakening suspect), 2 usage/setup error.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LOOP = REPO / ".claude" / "loop"
BASELINE = LOOP / "gate-baseline.txt"
PROPOSED = LOOP / "gate-baseline.proposed.txt"
COMPILE_DIRS = ["app.py", "core", "routes", "src", "services", "scripts", "tests"]


def venv_python() -> str:
    for cand in (REPO / "venv" / "Scripts" / "python.exe", REPO / "venv" / "bin" / "python"):
        if cand.is_file():
            return str(cand)
    return sys.executable


PY = venv_python()


def run(cmd, **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, **kw)


def changed(base: str) -> list[str]:
    files = set(run(["git", "diff", "--name-only", f"{base}...HEAD"]).stdout.split())
    files |= set(run(["git", "diff", "--name-only", "HEAD"]).stdout.split())
    files |= set(run(["git", "ls-files", "--others", "--exclude-standard"]).stdout.split())
    return sorted(f for f in files if (REPO / f).exists())


def check_syntax(base: str) -> list[str]:
    errs = []
    r = run([PY, "-m", "compileall", "-q", *COMPILE_DIRS])
    if r.returncode:
        errs.append("compileall failed:\n" + (r.stdout + r.stderr)[-3000:])
    for f in changed(base):
        if f.endswith((".js", ".mjs")) and f.startswith("static/") and not f.startswith("static/lib/"):
            r = run(["node", "--check", f])
            if r.returncode:
                errs.append(f"node --check {f}:\n{r.stderr[-1500:]}")
    return errs


def check_ownership(owner: str | None, base: str) -> list[str]:
    errs = []
    script = REPO / "scripts" / "fleet_ownership.py"
    r = run([sys.executable, str(script), "check"])
    if r.returncode:
        errs.append("ownership map broken:\n" + r.stdout[-3000:])
    if owner:
        r = run([sys.executable, str(script), "diff", owner, base])
        if r.returncode:
            errs.append(f"files outside {owner}'s ownership changed:\n" + r.stdout[-3000:])
    return errs


SKIP_RE = re.compile(r"(pytest\.mark\.(skip|skipif|xfail)|pytest\.(skip|xfail)\(|@unittest\.skip)")
ASSERT_RE = re.compile(r"^\s*(assert\b|self\.assert\w*\(|expect\()")
TRIVIAL_RE = re.compile(r"^\s*assert\s+(True|1|.+\s+is\s+not\s+None|not\s+None)\s*(#.*)?$")


def check_weakening(base: str) -> list[str]:
    suspects = []
    tests = [f for f in changed(base) if f.startswith("tests/")]
    if not tests:
        return suspects
    # `git diff <base>` compares base to the working tree, so it already covers
    # committed and uncommitted changes on this branch.
    diff = run(["git", "diff", "-U0", base, "--", *tests]).stdout
    added_assert = removed_assert = 0
    cur = None
    for line in diff.splitlines():
        if line.startswith("+++ "):
            cur = line[6:]
            continue
        if line.startswith(("---", "@@")):
            continue
        if line.startswith("+"):
            body = line[1:]
            if SKIP_RE.search(body):
                suspects.append(f"{cur}: added skip/xfail: {body.strip()}")
            if TRIVIAL_RE.match(body):
                suspects.append(f"{cur}: trivial assert: {body.strip()}")
            added_assert += bool(ASSERT_RE.match(body))
        elif line.startswith("-"):
            removed_assert += bool(ASSERT_RE.match(line[1:]))
    if removed_assert > added_assert:
        suspects.append(f"tests lost assertions: -{removed_assert} +{added_assert}")
    return suspects


def load_baseline() -> tuple[set[str], int]:
    if not BASELINE.is_file():
        return set(), 0
    ids, floor = set(), 0
    for line in BASELINE.read_text(encoding="utf-8").splitlines():
        m = re.match(r"#\s*collected-floor:\s*(\d+)", line)
        if m:
            floor = int(m.group(1))
        elif line.strip() and not line.startswith("#"):
            ids.add(line.strip())
    return ids, floor


def run_suite(focus: list[str]) -> tuple[set[str], int, str]:
    xml = LOOP / "reports" / "_gate_junit.xml"
    xml.parent.mkdir(parents=True, exist_ok=True)
    r = run([PY, "-m", "pytest", "-q", "-p", "no:cacheprovider", f"--junitxml={xml}", *focus])
    if not xml.is_file():
        return set(), 0, r.stdout[-3000:] + r.stderr[-2000:]
    root = ET.parse(xml).getroot()
    failed, total = set(), 0
    for case in root.iter("testcase"):
        total += 1
        if case.find("failure") is not None or case.find("error") is not None:
            failed.add(f"{case.get('classname')}::{case.get('name')}")
    tail = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""
    return failed, total, tail


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--owner")
    ap.add_argument("--base", default="dev")
    ap.add_argument("--focus", nargs=argparse.REMAINDER, default=[])
    ap.add_argument("--propose-baseline", action="store_true")
    a = ap.parse_args()

    if a.propose_baseline:
        failed, total, tail = run_suite([])
        PROPOSED.write_text(
            "# Proposed gate baseline. A HUMAN reviews this and renames it to\n"
            "# gate-baseline.txt. Agents never edit the real file.\n"
            f"# collected-floor: {total}\n# pytest: {tail}\n" + "\n".join(sorted(failed)) + "\n",
            encoding="utf-8",
        )
        print(f"wrote {PROPOSED.relative_to(REPO)}: {len(failed)} failing of {total}")
        return 0

    red, human = [], []
    red += check_syntax(a.base)
    red += check_ownership(a.owner, a.base)
    human += check_weakening(a.base)

    baseline, floor = load_baseline()
    if not BASELINE.is_file():
        red.append("no .claude/loop/gate-baseline.txt: human must create it (see --propose-baseline)")
    failed, total, tail = run_suite(a.focus)
    if total == 0:
        red.append(f"pytest produced no results: {tail}")
    new = sorted(failed - baseline)
    fixed = sorted(baseline - failed) if not a.focus else []
    if new:
        red.append(f"{len(new)} NEW failing test(s):\n  " + "\n  ".join(new[:50]))
    if not a.focus and floor and total < floor:
        red.append(f"collected {total} tests, below floor {floor}: tests deleted or not collecting")

    print(f"suite: {tail}  (collected {total}, failing {len(failed)}, baseline {len(baseline)}, new {len(new)})")
    if fixed:
        print(f"note: {len(fixed)} baseline failure(s) now pass; human may shrink the baseline")
    if a.focus:
        print("NOTE: focused run; NOT sufficient to land")
    for e in red:
        print("RED  " + e)
    for s in human:
        print("HUMAN " + s)
    if red:
        print("GATE: RED")
        return 1
    if human:
        print("GATE: NEEDS HUMAN (test-weakening suspect)")
        return 3
    print("GATE: GREEN" + (" (focused only)" if a.focus else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
