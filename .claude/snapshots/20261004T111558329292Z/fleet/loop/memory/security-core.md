# security-core memory

## File map
- `core/middleware.py`: SecurityHeadersMiddleware (CSP), `require_admin`, and the internal-tool loopback token.
- `core/auth.py`: `DEFAULT_PRIVILEGES` and `RESERVED_USERNAMES`.
- `src/tool_security.py`: `NON_ADMIN_BLOCKED_TOOLS`, `owner_is_admin_or_single_user`. Any `mcp__*` tool is also blocked for non-admins.
- `src/prompt_security.py`: `untrusted_context_message`, `UNTRUSTED_CONTEXT_POLICY`.
- `src/outbound_fetch.py`: the SSRF guard. Webhooks pin to the validated IP.
- `src/constants.py`: the only reader of `ODYSSEUS_DATA_DIR` (via `DATA_DIR`). Paths include `APP_DB`, `SESSIONS_FILE`, `SKILLS_FILE`, `CHROMA_DIR`, `UPLOAD_DIR`.
- `core/database.py`: SQLite at `data/app.db`, with startup migrations.
- THREAT_MODEL known gaps: no sandbox for admin tools (D-0-2 keeps it so), SSRF via the `/api/v1/chat` `base_url` (open), coarse token scopes.
- Test infrastructure you own: `tests/conftest.py`, `tests/helpers/`, `tests/_taxonomy.py`, `tests/run_focus.py`. The Windows harness fixes for Phase 0 land here.

## Environment (verified 2026-10-04)
- Windows 11, Git Bash plus PowerShell. Python 3.11.9 venv at `./venv/Scripts/python`, Node v26.7.0.
- The full suite takes **~640s**: 5,956 tests, 186 baseline failures. Collection alone takes ~67s. Prefer a `--focus` run while working.
- The `data/` dir exists, but is empty apart from what tests write. Point `ODYSSEUS_DATA_DIR` at a scratch dir for manual runs.
- Windows-only failure families in the baseline are a Node ESM loader error on `C:\` paths (~60), cp1252 Unicode errors (~20) and `socket.AF_UNIX` (4). They are harness or environment problems, not product bugs.

## Baseline failures you own (2026-10-04, dev@2992bf6)
Each is a candidate Phase 0 ticket. Fixing one means removing it from the baseline, which the human does.
- `tests/test_searxng_settings_migration.py` ×12: AssertionError: Traceback (most recent call last):
- `tests/test_tool_path_confinement.py` ×5: AssertionError: assert False
- `tests/test_agent_state_dir_confinement.py` ×3: KeyError: 'output'
- `tests/test_security_regressions.py` ×2: UnicodeDecodeError: 'charmap' codec can't decode byte 0x8f in position 385949: character maps to <undefined>
- `tests/test_email_linkify_security_js.py` ×1: AssertionError: node:internal/modules/esm/load:193
- `tests/test_rename_user_owner_sync.py` ×1: AssertionError: assert 'c:\\users\\a...aaaaaaaaa.txt' == 'C:\\Users\\a...aaaaaaaaa.txt'

## Notes
_(add here as you work)_
