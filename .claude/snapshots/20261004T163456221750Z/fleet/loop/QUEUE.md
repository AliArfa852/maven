# Queue

Orchestrator is the only writer. Format: see .claude/agents/orchestrator.md.

Tick 1 (DRY RUN, 2026-10-05). Every ticket below is `blocked-on D-0-5`: until the human promotes
`.claude/loop/gate-baseline.proposed.txt` to `gate-baseline.txt`, every full gate run is RED and nothing can land.
Dispatch starts on the first tick after promotion. Plan and dispatch order: `.claude/loop/reports/_tick-1-plan.md`.

Shared rules for every harness ticket (T-1-2 to T-1-8):
- Fix the test harness only. For node ESM imports, pass `pathlib.Path(p).as_uri()` (a file:// URL), not a bare path. Use explicit `encoding="utf-8"` on `open` / `read_text` / `subprocess.run(text=True)`. Build JSON tool payloads with `json.dumps`.
- No skip, xfail, deleted assertion, or global `PYTHONUTF8` / env hack. The tests must still pass on POSIX CI.
- If a test's real assertion fails once the harness error is gone (the test was never actually running on Windows), STOP. Do not touch product code. File a BACKLOG item (P0 if it is a security test) and leave the ticket failed.

### T-1-1  _is_sensitive_path: also split on os.altsep so forward-slash paths hit the deny-list on Windows
owner: agent-core   tier: sonnet   priority: P1
band: core
files: src/tool_execution.py
done-when: ./venv/Scripts/python -m pytest tests/test_tool_path_confinement.py -k sensitive -q -p no:cacheprovider
why: triage F3. The baseline holds tests.test_tool_path_confinement::test_sensitive_{ssh_dir,gnupg_dir,shell_rc,key_filenames} (4 ids). `_is_sensitive_path` (src/tool_execution.py:109) splits on `os.sep` only, so `C:/Users/x/.ssh/authorized_keys` and `expanduser('~')+'/.ssh/config'` return False on Windows. Fix: split on `os.sep` AND `os.altsep` when it is not None. `os.altsep` is None on POSIX, so POSIX behaviour is byte-identical; on Windows this is a pure deny-list tightening. Do NOT use a blanket `[\\/]` regex. `-k sensitive` collects 7 tests (4 fail today; non_sensitive, case_insensitive and extra_root_still_blocks_sensitive are the guards and must stay green). Current callers (lines 249/290/298/380/421/479, filesystem_tools.py:833) pass realpath'd input, so the fix also makes a full caller audit unnecessary for this function. Do not edit the test file (security-core owns it).
status: blocked-on D-0-5

### T-1-2  test_agent_state_dir_confinement: build tool-call JSON with json.dumps (Windows backslashes break the f-string JSON)
owner: security-core   tier: sonnet   priority: P1
band: core
files: tests/test_agent_state_dir_confinement.py
done-when: ./venv/Scripts/python -m pytest tests/test_agent_state_dir_confinement.py -q -p no:cacheprovider
why: triage F2 "cause UNCONFIRMED", now confirmed as test-side. The 3 baseline ids (hardlink_alias line ~126-134, recursive_glob_and_grep line ~474-478, ls_hides_protected_entries[False] line ~606) build payloads like f'{{"path": "{workspace}"}}'. There are 7 such f-string JSON payloads in the file (grep `f'{{`); fix all of them. On Windows `C:\Users\...` is invalid JSON, and the tool returns `{'error': 'glob: pattern is required'}` (KeyError 'output'). Orchestrator check: a scratchpad copy with all 7 payloads switched to json.dumps gives 64 passed, 1 skipped (case-sensitive-only test). The product does hide the hardlink alias on Windows, so this fix is expected to pass. Today the file has 3 failed. Shared rules at the top of QUEUE.md apply: no skip/xfail/env hacks, and STOP and file to BACKLOG if a real assertion fails.
status: blocked-on D-0-5

### T-1-3  chat-core tests: file:// ESM import URLs and utf-8 reads on Windows
owner: chat-core   tier: sonnet   priority: P2
band: core
files: tests/test_preset_local_storage_js.py, tests/test_startup_session_bootstrap_js.py, tests/test_markdown_table_row_js.py, tests/test_deleted_session_sidebar_regression.py
done-when: ./venv/Scripts/python -m pytest tests/test_preset_local_storage_js.py tests/test_startup_session_bootstrap_js.py tests/test_markdown_table_row_js.py tests/test_deleted_session_sidebar_regression.py -q -p no:cacheprovider
why: triage F1 + F6. These are all 9 chat-core baseline ids (ERR_UNSUPPORTED_ESM_URL_SCHEME "Received protocol 'c:'", plus a cp1252 UnicodeDecodeError in deleted_session_sidebar). Today: 9 failed, 2 passed. The deleted_session ids pass under PYTHONUTF8=1, which confirms the cause is test-side. Shared rules at the top of QUEUE.md apply: no skip/xfail/env hacks, and STOP and file to BACKLOG if a real assertion fails.
status: blocked-on D-0-5

### T-1-4  agent-core tests: file:// ESM import URLs and utf-8 encoding on Windows
owner: agent-core   tier: sonnet   priority: P2
band: core
files: tests/test_local_endpoint_js.py, tests/test_provider_device_flow_js.py, tests/test_calendar_css_url_escape_js.py, tests/test_local_endpoint_api_key_js.py, tests/test_match_model_key_js.py, tests/test_startup_shell_js.py, tests/test_external_context_tool_gate.py
done-when: ./venv/Scripts/python -m pytest tests/test_local_endpoint_js.py tests/test_provider_device_flow_js.py tests/test_calendar_css_url_escape_js.py tests/test_local_endpoint_api_key_js.py tests/test_match_model_key_js.py tests/test_startup_shell_js.py tests/test_external_context_tool_gate.py -q -p no:cacheprovider
why: triage F1 + F6/F8. 28 baseline ids, and today there are 28 failed, 159 passed. test_local_endpoint_js (12) is cp1252 '\u2192'. test_external_context_tool_gate (2) is `Path.read_text()` without utf-8 at test lines 1348/1404 (frame is in tests/, not src/), and it passes under PYTHONUTF8=1. Those two are the post-external-context authorization gate checks, and calendar_css_url_escape (3) is an escaping test. If their real assertions fail after the harness fix, follow the STOP rule. Shared rules at the top of QUEUE.md apply: no skip/xfail/env hacks, and STOP and file to BACKLOG if a real assertion fails.
status: blocked-on D-0-5

### T-1-5  security-core tests: file:// ESM import URL and utf-8 reads (security assertions never ran on Windows)
owner: security-core   tier: sonnet   priority: P2
band: core
files: tests/test_security_regressions.py, tests/test_email_linkify_security_js.py
done-when: ./venv/Scripts/python -m pytest tests/test_security_regressions.py tests/test_email_linkify_security_js.py -q -p no:cacheprovider
why: triage F1/F6 caveat. Covers test_security_regressions::{email_thread_rendering_sanitizes_body_html, gmail_mcp_preset_uses_contained_oauth_paths} (cp1252 decode; they pass under PYTHONUTF8=1) and test_email_linkify_security_js::test_plain_text_linkify_escapes_href_attribute_without_double_escaping (ESM 'c:'). Today: 3 failed, 99 passed. The linkify assertion has never executed on Windows. If it fails after the harness fix, that is a P0 XSS finding for BACKLOG, not something to work around. Shared rules at the top of QUEUE.md apply: no skip/xfail/env hacks, and STOP and file to BACKLOG if a real assertion fails.
status: blocked-on D-0-5

### T-1-6  inference-core tests: file:// ESM import URL in cookbook port parsing test
owner: inference-core   tier: sonnet   priority: P2
band: core
files: tests/test_cookbook_port_parsing_js.py
done-when: ./venv/Scripts/python -m pytest tests/test_cookbook_port_parsing_js.py -q -p no:cacheprovider
why: triage F1. The 3 baseline ids in test_cookbook_port_parsing_js fail with ERR_UNSUPPORTED_ESM_URL_SCHEME. Today: 3 failed. This is the only harness-fixable inference-core work; its other 6 ids are platform-specific (see the BACKLOG decision item). Shared rules at the top of QUEUE.md apply: no skip/xfail/env hacks, and STOP and file to BACKLOG if a real assertion fails.
status: blocked-on D-0-5

### T-1-7  workspace-apps JS tests: file:// ESM import URLs and utf-8 on Windows
owner: workspace-apps   tier: sonnet   priority: P2
band: supporting
files: tests/test_email_summary_error_ui_js.py, tests/test_harmonize_masks_invalid_layers_js.py, tests/test_ordinal_suffix_js.py, tests/test_signature_fold_js.py, tests/test_lang_icon_null_opts_js.py, tests/test_matchescombo_nonstring_js.py, tests/test_providers_mixtral_logo_js.py, tests/test_reply_all_cc_nonstring_js.py, tests/test_tile_manager_snap_zones_js.py, tests/test_canvas_coords_empty_touches_js.py, tests/test_gmail_quote_attribution_js.py, tests/test_hex_to_rgb_js.py, tests/test_portal_dropdown_z_js.py, tests/test_reply_recipients_js.py, tests/test_signature_fold_self_closing_br_js.py, tests/test_snap_other_layers_nonarray_js.py, tests/test_email_open_dedup_js.py, tests/test_emoji_shortcodes_js.py, tests/test_panel_loader_js.py
done-when: ./venv/Scripts/python -m pytest tests/test_email_summary_error_ui_js.py tests/test_harmonize_masks_invalid_layers_js.py tests/test_ordinal_suffix_js.py tests/test_signature_fold_js.py tests/test_lang_icon_null_opts_js.py tests/test_matchescombo_nonstring_js.py tests/test_providers_mixtral_logo_js.py tests/test_reply_all_cc_nonstring_js.py tests/test_tile_manager_snap_zones_js.py tests/test_canvas_coords_empty_touches_js.py tests/test_gmail_quote_attribution_js.py tests/test_hex_to_rgb_js.py tests/test_portal_dropdown_z_js.py tests/test_reply_recipients_js.py tests/test_signature_fold_self_closing_br_js.py tests/test_snap_other_layers_nonarray_js.py tests/test_email_open_dedup_js.py tests/test_emoji_shortcodes_js.py tests/test_panel_loader_js.py -q -p no:cacheprovider
why: triage F1. 49 baseline ids, and today there are 49 failed, 10 passed (PYTHONUTF8=1 alone still leaves 41 failing, so the file:// URL fix is required). Supporting band, queued because every characterised core Phase 0 item is already queued (T-1-1 to T-1-6). Dispatch it after core. Shared rules at the top of QUEUE.md apply: no skip/xfail/env hacks, and STOP and file to BACKLOG if a real assertion fails.
status: blocked-on D-0-5

### T-1-8  workspace-apps tests: utf-8 decoding in memory-add and PR/issue description checks
owner: workspace-apps   tier: sonnet   priority: P2
band: supporting
files: tests/test_memory_add_submit_regression.py, tests/test_pr_description_check.py, tests/test_issue_description_check.py
done-when: ./venv/Scripts/python -m pytest tests/test_memory_add_submit_regression.py tests/test_pr_description_check.py tests/test_issue_description_check.py -q -p no:cacheprovider
why: triage F6/F7. 16 baseline ids, and today there are 16 failed, 13 passed. All of them pass under PYTHONUTF8=1, so the fix is test-side encoding (the read_text / subprocess decode in tests/). It must not edit `.github/scripts/*` (human-owned). If a fix seems to need `.github/`, STOP and file a BACKLOG item for decision-broker. test_pr_blocker_audit::test_color_auto_requires_terminal_and_support is deliberately excluded: it still fails under UTF-8 mode and is uncharacterised. Shared rules at the top of QUEUE.md apply: no skip/xfail/env hacks, and STOP and file to BACKLOG if a real assertion fails.
status: blocked-on D-0-5
