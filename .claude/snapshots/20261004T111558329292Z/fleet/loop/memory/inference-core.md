# inference-core memory

## File map
- `routes/cookbook_routes.py` (20 fixes), `cookbook_helpers.py` (17), `cookbook_output.py`; `src/cookbook_serve_lifecycle.py`.
- `services/hwfit/`: `fit.py`, `hardware.py`, `hf_discovery.py`, `profiles.py`, `models.py`, plus the `data/hf_models.json` catalog. Adapted from llmfit (MIT).
- Frontend: `static/js/cookbook*.js` (`cookbookRunning.js` has 11 fixes).
- Specs: `specs/cookbook-hwfit.md` and `specs/model-providers/{ollama,llama-cpp,vllm,sglang,lm-studio}.md`.
- Ollama becomes the only local-only provider in Phase 1a (MAVEN_PLAN), so the Ollama paths are Maven-critical.

## Environment (verified 2026-10-04)
- Windows 11, Git Bash plus PowerShell. Python 3.11.9 venv at `./venv/Scripts/python`, Node v26.7.0.
- The full suite takes **~640s**: 5,956 tests, 186 baseline failures. Collection alone takes ~67s. Prefer a `--focus` run while working.
- The `data/` dir exists, but is empty apart from what tests write. Point `ODYSSEUS_DATA_DIR` at a scratch dir for manual runs.
- Windows-only failure families in the baseline are a Node ESM loader error on `C:\` paths (~60), cp1252 Unicode errors (~20) and `socket.AF_UNIX` (4). They are harness or environment problems, not product bugs.

## Baseline failures you own (2026-10-04, dev@2992bf6)
Each is a candidate Phase 0 ticket. Fixing one means removing it from the baseline, which the human does.
- `tests/test_cookbook_port_parsing_js.py` ×3: AssertionError: node:internal/modules/esm/load:193
- `tests/test_cookbook_docker_access.py` ×2: AttributeError: module 'socket' has no attribute 'AF_UNIX'
- `tests/test_hwfit_cpu_arch_detection.py` ×2: AssertionError: assert 'x86_64' == 'arm64'
- `tests/test_cookbook_helpers.py` ×1: assert False
- `tests/test_hwfit_macos.py` ×1: AssertionError: assert 'cuda' == 'metal'

## Notes
_(add here as you work)_
