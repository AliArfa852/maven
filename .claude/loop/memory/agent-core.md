# agent-core memory

## File map
- `src/agent_loop.py`: the loop; 48 fixes in the last 600 commits. `src/llm_core.py`: provider calls; 33 fixes.
- `src/tool_schemas.py`, `tool_parsing.py`, `tool_execution.py`, `tool_implementations.py`, `tool_index.py`: the tool pipeline. Registry consistency across these is manual (spec gap).
- `src/agent_tools/*_tools.py`: tool groups (filesystem, subprocess, web, document, session, admin, bg_job, coding, interaction, model_interaction).
- `src/model_capability_readers/`: per-provider readers. llamacpp/lmstudio/ollama belong to inference-core.
- Specs: `specs/agent-tools.md`, `llm-models.md`, `context-building.md`, `model-quirks.md`, `shell-mcp.md`.

## Environment (verified 2026-10-04)
- Windows 11, Git Bash plus PowerShell. Python 3.11.9 venv at `./venv/Scripts/python`, Node v26.7.0.
- The full suite takes **~640s**: 5,956 tests, 186 baseline failures. Collection alone takes ~67s. Prefer a `--focus` run while working.
- The `data/` dir exists, but is empty apart from what tests write. Point `ODYSSEUS_DATA_DIR` at a scratch dir for manual runs.
- Windows-only failure families in the baseline are a Node ESM loader error on `C:\` paths (~60), cp1252 Unicode errors (~20) and `socket.AF_UNIX` (4). They are harness or environment problems, not product bugs.

## Baseline failures you own (2026-10-04, dev@2992bf6)
Each is a candidate Phase 0 ticket. Fixing one means removing it from the baseline, which the human does.
- `tests/test_code_nav_tools.py` ×16: assert 1 == 0
- `tests/test_local_endpoint_js.py` ×12: UnicodeEncodeError: 'charmap' codec can't encode character '\u2192' in position 623: character maps to <undefi
- `tests/test_provider_device_flow_js.py` ×5: AssertionError: node:internal/modules/esm/load:193
- `tests/test_shell_routes.py` ×5: AssertionError: assert False is True
- `tests/test_calendar_css_url_escape_js.py` ×3: AssertionError: node:internal/modules/esm/load:193
- `tests/test_external_context_tool_gate.py` ×2: UnicodeDecodeError: 'charmap' codec can't decode byte 0x81 in position 24199: character maps to <undefined>
- `tests/test_local_endpoint_api_key_js.py` ×2: UnicodeEncodeError: 'charmap' codec can't encode character '\u2192' in position 2912: character maps to <undef
- `tests/test_match_model_key_js.py` ×2: AssertionError: node:internal/modules/esm/load:193
- `tests/test_startup_shell_js.py` ×2: AssertionError: failure written before the render frame
- `tests/test_builtin_mcp_npx_cache.py` ×1: AssertionError: cache hit should not shell out to npx
- `tests/test_slash_setup_provider_aliases.py` ×1: UnicodeDecodeError: 'charmap' codec can't decode byte 0x90 in position 90657: character maps to <undefined>

## Notes
- `_is_sensitive_path` (src/tool_execution.py ~109) normalises `os.altsep` to `os.sep` before splitting (T-1-1, tick 2).
- `tests/test_tool_execution*.py` matches no files. Confinement tests live in `tests/test_tool_path_confinement.py`.
- In an isolated worktree: run git as its own command (compound bash containing git is refused). Writes to the main `.claude/loop/` are refused, so return report and memory text to the main loop.
- `tests/test_tool_index_schema_parity.py` literal_evals `src/tool_index.py` and `src/tool_schemas.py`: descriptions there must be pure string literals (no `+` or f-strings).
- The LoRA minimal prompts (`_minimal_odysseus_*`, agent_loop ~1770-1915) are a contract with the `odysseus-qwen3` weights; they keep "Odysseus" (S-1).
- The `-k agent/tool/llm/...` selection takes ~250s; run it in the foreground with a timeout. Baseline ids are dotted `tests.module::name`.
