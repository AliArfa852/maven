# Done ledger

Append-only. git-manager writes one line per ticket outcome. Everyone reads the tail first.
Format: `<date> | <ticket-id> | <owner> | <landed <sha> / reverted <sha> / stuck / failed> | <files, comma-separated> | <one-line what changed>`

2026-10-05 | T-1-1 | agent-core | landed a6263589 | src/tool_execution.py | _is_sensitive_path now treats forward-slash Windows paths as sensitive
2026-10-05 | T-1-2 | security-core | landed 33b9e75c | tests/test_agent_state_dir_confinement.py | confinement payloads built with json.dumps
2026-10-05 | T-1-3 | chat-core | landed cc0b2d2c | tests/test_deleted_session_sidebar_regression.py, tests/test_markdown_table_row_js.py, tests/test_preset_local_storage_js.py, tests/test_startup_session_bootstrap_js.py | file:// ESM URLs and utf-8 decoding on Windows
2026-10-05 | T-1-4 | agent-core | landed 2a40cfe1 | tests/test_calendar_css_url_escape_js.py, tests/test_external_context_tool_gate.py, tests/test_local_endpoint_api_key_js.py, tests/test_local_endpoint_js.py, tests/test_match_model_key_js.py, tests/test_provider_device_flow_js.py, tests/test_startup_shell_js.py | file:// ESM URLs and utf-8 decoding on Windows
2026-10-05 | T-1-5 | security-core | landed d2a47daa | tests/test_email_linkify_security_js.py, tests/test_security_regressions.py | read sources as utf-8, import ESM via file:// on Windows
2026-10-05 | T-1-6 | inference-core | landed a624a650 | tests/test_cookbook_port_parsing_js.py | import port parser via file:// URL on Windows
