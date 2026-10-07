# chat-core memory

## File map
- `routes/chat_routes.py` (22 fixes) and `chat_helpers.py` (15); `src/chat_handler.py`, `chat_processor.py`, `chat_helpers.py`.
- Frontend: `static/js/chat.js` (20), `chatRenderer.js` (16), `streamingRenderer.js`, `streamingSegmenter.js`, `chatStream.js`, `chatStreamErrors.js`. The SSE contract is shared across these.
- `static/style.css` is 41,401 lines. `static/index.html` is 2,591 lines and `static/app.js` is 4,583.
- Mermaid v11 is vendored at `static/lib/mermaid.min.js`, lazy-loaded by `static/js/markdown.js`. KaTeX is lazy-loaded the same way.
- The CSP is in `core/middleware.py` (security-core): `script-src 'self' 'nonce-…' https://cdn.jsdelivr.net`.
- Specs: `specs/chat.md`, `frontend.md`, `compare.md`.

## Environment (verified 2026-10-04)
- Windows 11, Git Bash plus PowerShell. Python 3.11.9 venv at `./venv/Scripts/python`, Node v26.7.0.
- The full suite takes **~640s**: 5,956 tests, 186 baseline failures. Collection alone takes ~67s. Prefer a `--focus` run while working.
- The `data/` dir exists, but is empty apart from what tests write. Point `ODYSSEUS_DATA_DIR` at a scratch dir for manual runs.
- Windows-only failure families in the baseline are a Node ESM loader error on `C:\` paths (~60), cp1252 Unicode errors (~20) and `socket.AF_UNIX` (4). They are harness or environment problems, not product bugs.

## Baseline failures you own (2026-10-04, dev@2992bf6)
Each is a candidate Phase 0 ticket. Fixing one means removing it from the baseline, which the human does.
- `tests/test_markdown_table_row_js.py` ×4: AssertionError: node:internal/modules/esm/load:193
- `tests/test_deleted_session_sidebar_regression.py` ×3: UnicodeDecodeError: 'charmap' codec can't decode byte 0x81 in position 122247: character maps to <undefined>
- `tests/test_preset_local_storage_js.py` ×1: AssertionError: node:internal/modules/esm/load:193
- `tests/test_startup_session_bootstrap_js.py` ×1: AssertionError: assert 'Loading chatsâ€¦' == 'Loading chats…'

## Notes
_(add here as you work)_
