# workspace-apps memory

## File map
- Fallback owner for `routes/`, `src/`, `services/`, `static/js`, `scripts/` and `tests/`. Always run `who` first.
- Email: `routes/email_routes.py` (15 fixes), `email_helpers.py` (12), `email_pollers.py`.
- Research: `services/research/`, `src/deep_research.py`, `src/research_handler.py`, `src/visual_report.py` (HTML report for deep research; no charts).
- RAG and docs: `src/rag_manager.py`, `rag_vector.py`, `document_processor.py`, `markitdown_runtime.py`, `pdf_runtime.py`. These become `knowledge-core`'s in Phase 2.
- `src/` and `services/` duplicate search and memory (transitional). Change both.
- `tests/cli/` tests the `scripts/odysseus-*` CLIs, which get renamed with aliases in Phase 1c.

## Environment (verified 2026-10-04)
- Windows 11, Git Bash plus PowerShell. Python 3.11.9 venv at `./venv/Scripts/python`, Node v26.7.0.
- The full suite takes **~640s**: 5,956 tests, 186 baseline failures. Collection alone takes ~67s. Prefer a `--focus` run while working.
- The `data/` dir exists, but is empty apart from what tests write. Point `ODYSSEUS_DATA_DIR` at a scratch dir for manual runs.
- Windows-only failure families in the baseline are a Node ESM loader error on `C:\` paths (~60), cp1252 Unicode errors (~20) and `socket.AF_UNIX` (4). They are harness or environment problems, not product bugs.

## Baseline failures you own (2026-10-04, dev@2992bf6)
Each is a candidate Phase 0 ticket. Fixing one means removing it from the baseline, which the human does.
- `tests/test_write_file_empty_body.py` ×15: AssertionError: write_file: path 'C:\Users\aliar\AppData\Local\Temp\odysseus-6414-y7lusuuc\classic-banana-cake
- `tests/test_pr_description_check.py` ×8: TypeError: the JSON object must be str, bytes or bytearray, not NoneType
- `tests/test_emoji_shortcodes_js.py` ×5: AssertionError: node:internal/modules/esm/load:193
- `tests/test_issue_description_check.py` ×5: TypeError: the JSON object must be str, bytes or bytearray, not NoneType
- `tests/test_panel_loader_js.py` ×5: AssertionError: node:internal/modules/esm/load:193
- `tests/test_email_open_dedup_js.py` ×4: UnicodeEncodeError: 'charmap' codec can't encode character '\u21d2' in position 7194: character maps to <undef
- `tests/test_canvas_coords_empty_touches_js.py` ×3: AssertionError: node:internal/modules/esm/load:193
- `tests/test_gmail_quote_attribution_js.py` ×3: AssertionError: node:internal/modules/esm/load:193
- `tests/test_hex_to_rgb_js.py` ×3: AssertionError: node:internal/modules/esm/load:193
- `tests/test_memory_add_submit_regression.py` ×3: UnicodeDecodeError: 'charmap' codec can't decode byte 0x81 in position 17176: character maps to <undefined>
- `tests/test_portal_dropdown_z_js.py` ×3: UnicodeDecodeError: 'charmap' codec can't decode byte 0x90 in position 86549: character maps to <undefined>
- `tests/test_reply_recipients_js.py` ×3: AssertionError: node:internal/modules/esm/load:193
- `tests/test_run_focus.py` ×3: assert "'C:\\Users\\...b_cookbook'\n" == "C:\\Users\\a...b_cookbook'\n"
- `tests/test_signature_fold_self_closing_br_js.py` ×3: AssertionError: node:internal/modules/esm/load:193
- `tests/test_snap_other_layers_nonarray_js.py` ×3: AssertionError: node:internal/modules/esm/load:193
- `tests/test_lang_icon_null_opts_js.py` ×2: AssertionError: node:internal/modules/esm/load:193
- `tests/test_matchescombo_nonstring_js.py` ×2: AssertionError: node:internal/modules/esm/load:193
- `tests/test_providers_mixtral_logo_js.py` ×2: AssertionError: node:internal/modules/esm/load:193
- `tests/test_reply_all_cc_nonstring_js.py` ×2: AssertionError: node:internal/modules/esm/load:193
- `tests/test_tile_manager_snap_zones_js.py` ×2: AssertionError: node:internal/modules/esm/load:193
- `tests/test_app_db_permissions.py` ×1: AssertionError: assert None == 'C:\\Users\\aliar\\AppData\\Local\\Temp\\pytest-of-aliar\\pytest-128\\test_sqli
- `tests/test_email_summary_error_ui_js.py` ×1: AssertionError: node:internal/modules/esm/load:193
- `tests/test_harmonize_masks_invalid_layers_js.py` ×1: AssertionError: node:internal/modules/esm/load:193
- `tests/test_imap_mailbox_quoting.py` ×1: UnicodeDecodeError: 'charmap' codec can't decode byte 0x8d in position 54607: character maps to <undefined>
- `tests/test_live_fallback_round_attribution.py` ×1: AssertionError: assert {'labels': [{...lderCount': 0} == {'labels': [{...lderCount': 0}
- … 9 more files; see `gate-baseline.txt`

## Notes
- The `*_js.py` node-harness tests share one Windows breakage: bare `c:/` ESM import paths and cp1252 on `text=True`/`read_text()`. The fix is `resolve().as_uri()` plus `encoding="utf-8"` (T-1-7, 19 files).
- The venv python can't read bash `/tmp` paths. Pass file lists inline.

## S-1 rename notes (worktree fleet/S-1-workspace)
- Worktree bash blocks compound git, `$VAR` as sed/git operand and `cd x && git`; use literal paths, `sed -i -- ... $(cat list)`. Python `write_text` on Windows writes CRLF into list files (strip with `tr -d '\r'`).
- `.claude/` is not in worktrees; run MAIN's `scripts/fleet_ownership.py who <paths>` for ownership.
- CLI rename: `scripts/maven*` are real; `scripts/odysseus*` are shims with `__main__` guard (execv at import kills pytest). Dispatcher `_resolve_subcommand` prefers `maven-`, falls back to `odysseus-`.
- A `\bOdysseus\b` regex also hits `X-Odysseus-*` headers; revert those. Left alone: storage keys, events, `window.__odysseus*`, odysseus_kind DB column, `odysseus-ui` origin header value, `odysseus.local` msgids, `odysseus://attachment/`, settings.js plugin-setup snippets (human-owned integrations), reminder persona, research example prompt.
- `tests/test_odysseus_dispatcher.py::test_is_runnable...` is a baseline failure on Windows (exec bit).
