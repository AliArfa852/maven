# triage-reporter memory

## Known facts (2026-10-04)
- The latest full junit is `.claude/loop/reports/_gate_junit.xml`; it exists after the first gate run.
- The full suite takes ~640s. Do not re-run it for triage; read the gate's output.

## Notes
- Tick 1 (dry run): baseline families are JS tests (ESM `c:` URL + cp1252, ~85), `/tmp`-only root in tool_execution._tool_path_roots (~37), os.fchmod in scripts/migrate_searxng_settings.py (12), _is_sensitive_path os.sep-only split (4), PR/issue check scripts (~14). Detail in reports/_tick-1-triage.md.
- Tests that die on encoding/harness errors never ran their assertions (email sanitize, external_context gate, security_regressions). Do not call them passing.
- Unconfirmed at tick 1: agent_state_dir KeyError 'output' (3), rag_remove scope (1), upload/rename owner (2).
- In bash heredocs with many quotes the tool broke; use the Write tool for report files.
