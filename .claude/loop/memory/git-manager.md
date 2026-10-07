# git-manager memory

## Known facts (2026-10-04)
- `.claude/` is gitignored. Fleet files never get committed.
- Commits follow Conventional Commits, `type(scope): summary`, and end with the Co-Authored-By trailer.

## Notes
- Harness worktrees branch from 2992bf6d (origin/dev), not local dev. Merging into a `fleet/<id>-verify` branch cut from dev fixes that; disjoint-file merges were clean in tick 2.
- In this shell `$TEMP` resolves to `/tmp`. `git commit -F /tmp/<file>` works for multi-line messages.
- Run each git command separately in worktrees; compound commands are refused.
- Batch landing: merge the T-x-verify branches into dev in the gated order, then prove `dev^{tree}` == `fleet/batch-N-verify^{tree}` instead of re-running the full gate (batch 1: equal, 349fa910).
- `git merge --no-ff <branch> -F /tmp/<file>` works: subject, blank line, body, blank line, trailer.
- `fleet_ownership.py who` resolves @source test rules through the MAIN folder's tracked files only. A test for a module not yet committed there falls to the fallback owner, so add an explicit rule (done for `tests/test_brand*.py`).
- Worktrees have no `.claude/`, so ownership and gate scripts run from the main folder only.
- S-1 stage 3: `git add -u` in a worktree skips untracked new files; `static/brand/favicon-16.png` and `favicon-32.png` are gitignored (need `-f` to track). Run `git ls-files --others` (no --untracked-files=all) to list untracked.
- Shim check: python script that finds `os.execv` and the preceding `if __name__ == "__main__":` within 2 lines; all odysseus* shims passed in S-1.
- workspace-apps S-1 added a Windows-conditional `pytest.skip` in tests/test_odysseus_dispatcher.py (new test), which trips the "added skip" stop rule; held uncommitted pending a decision.
