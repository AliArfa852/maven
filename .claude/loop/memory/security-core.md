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
- On Windows, node ESM `import()` needs `Path.resolve().as_uri()`. `as_posix()` gives `c:/...`, which node rejects (ERR_UNSUPPORTED_ESM_URL_SCHEME).
- Under pytest on Windows, `read_text()` and `subprocess.run(text=True)` default to cp1252. Pass `encoding="utf-8"` explicitly. `tests/test_security_regressions.py` had 8 such reads (T-1-5).
- `tests/test_email_linkify_security_js.py` runs `static/js/emailLibrary/utils.js` through node with a stub `document`, and skips if node is not on PATH.
- T-1-2: Windows paths in f-string JSON break tool payloads; use json.dumps. Ticket count of '7' was really 6.
- `src/brand.py` holds the brand constants and `apply_env_aliases`. `src/constants.py` and `app.py` call it first; `launcher.py` right after its imports (S-1).
- `tests/test_brand.py` runs its DATA_DIR checks in subprocesses with MAVEN_AI_*/ODYSSEUS_* stripped from the env.
- `-m area_security` takes ~2 min (830 tests); its Windows baseline failures are rag_remove_directory_scope, rename_user_owner_sync and tool_path_confinement::allows_tmp.
- `.env.example` is unreadable to agents: the settings deny `./.env.*` (D-1c-5).
- `tests/test_brand_rename.py` (S-1) blanks SPAN_ALLOW spans first, then checks LINE_ALLOW, FILE_ALLOW, tests-only fixtures and comment contexts (`_comment_only` state machine; extensionless scripts are treated as shell). Call `find_unallowed()` to list everything without the 50-line cap.
- Pitfall: non-raw '' in a patch script wrote backspace bytes into the regexes. Use raw strings.
- Changing the TOTP issuer (`core/auth.py`) only relabels NEW enrollments; existing codes stay valid.
