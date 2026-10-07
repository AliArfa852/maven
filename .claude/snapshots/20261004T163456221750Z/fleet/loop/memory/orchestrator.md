# orchestrator memory

## Known facts
- Plan: `.claude/loop/MAVEN_PLAN.md`. Phase 0 is active until the baseline has ≤ 40 entries, each with a reason.
- Decisions: `DECISIONS-PENDING.md`. D-0-1..D-0-4 answered; D-0-5 (promote baseline) pending as of 2026-10-05.
- Baseline (proposed) 186 ids by owner: workspace-apps 93, agent-core 51, security-core 24, inference-core 9, chat-core 9.
- Test files are owned per-file (OWNERSHIP.txt), not by security-core, despite MAVEN_PLAN's Phase 0 line.
- `.github/scripts/*` is human-owned; test_pr_description_check / test_issue_description_check run those via node.
- scripts/migrate_searxng_settings.py runs only inside the Linux searxng container (mounted by docker-compose*.yml).

## Tick 1 (dry run) queued T-1-1..T-1-8, all blocked-on D-0-5. See reports/_tick-1-plan.md.
- Projected: 186 -> 71 after these land + human prune; F2 (32) and F4 (12) are decision items.

## Useful checks (Windows)
- Baseline id -> file: `tests.<mod>::<test>` -> `tests/<mod>.py`; class ids appear as `tests.test_shell_routes.TestX::...`.
- Owner per baseline file: loop `fleet_ownership.py who` over the files (~1 s per call).
- Is a cp1252 failure test-side? Rerun with `PYTHONUTF8=1`; if it passes and the frame is in tests/, yes.
- JS ESM failures need `Path(p).as_uri()`; UTF-8 mode alone does not fix them (ws JS: 49 -> 41 failing).
- Harness-only hypothesis can be checked by copying a test + tests/conftest.py to scratchpad, editing, and running with `PYTHONPATH=<repo> pytest <copy> --rootdir=<repo>`.
- `_tool_path_roots` (src/tool_execution.py:308) has no Windows temp root; setting TMPDIR to tempfile.gettempdir() makes most write_file tests pass.

## Notes
- No ticket has failed yet (DONE.md empty), so nothing is stuck.
