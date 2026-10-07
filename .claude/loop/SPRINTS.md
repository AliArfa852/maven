# Sprints

At most one active. See PROTOCOL.md section Sprint.

## S-1  Phase 1c: rename to Maven (ACTIVE, opened 2026-10-05 by the human's direct instruction)
**STATUS (2026-10-05):** stages 1-4 done, and leftovers fixed. `fleet/S-1-verify` @134f44ca = dev + batch 2 (T-1-7, T-1-8) + the full rename. Brand tests 15/15. Ownership 0 failures (1,611 files). Tree clean. **Stage 5 (full gate) waits on system memory** (1.0 GB free; the last gate was killed at about that level). Then land on GREEN after the human's visual review and confirmation of the D-1-3 skip (R1).
**Decisions:** D-0-3, D-1c-0 … D-1c-4.
**Base:** `fleet/batch-2-verify` (dev plus T-1-7 and T-1-8, still ungated), so one full gate covers batch 2 and the rename (D-1c-0).
**Branches:** each stage-2 owner works in its own isolated worktree on `fleet/S-1-<owner>`, branched from `fleet/S-1-security`. git-manager merges everything into `fleet/S-1-verify`.
**Reviewer:** chat-core reviews the combined diff against the done-when (no nested dispatch, because nested worktrees are unreliable here).
**Order:**
1. Stage 1, security-core: brand module, env alias shim and tests. git-manager commits it on `fleet/S-1-security`, and stage 2 branches from that (no separate base branch). `.env.example` is blocked by settings (D-1c-5).
2. Stage 2, in parallel worktrees: chat-core, agent-core, inference-core, workspace-apps, docs-keeper.
3. Stage 3: git-manager merges all into `fleet/S-1-verify`; chat-core reviews.
4. Stage 4, security-core: the rename-completeness test.
5. Stage 5: full gate (memory permitting); land on GREEN.

### Shared contract (every worker codes against this)
- **`src/brand.py`** (security-core) defines:
  - `BRAND_NAME = "Maven"`, `BRAND_SLUG = "maven"`
  - `ENV_PREFIX = "MAVEN_AI_"`, `LEGACY_ENV_PREFIX = "ODYSSEUS_"`
  - `UPSTREAM_NAME = "Odysseus"`, `UPSTREAM_URL = "https://github.com/odysseus-dev/odysseus"`
  - `SOURCE_URL`: env `MAVEN_AI_SOURCE_URL`, default `https://github.com/AliArfa852/maven`. This is the AGPL §13 "source" link.
  - `apply_env_aliases(environ=os.environ)`: for every name present under either prefix, the new name wins when both are set, and both names end up holding the winning value. Idempotent; never logs values.
- **Where the shim runs:** `apply_env_aliases()` is called at the TOP of `src/constants.py` (before `DATA_DIR` is read), in `app.py` and `launcher.py`, and in every Python CLI entry point. Existing `os.getenv("ODYSSEUS_X")` read sites therefore keep working unchanged. Do NOT mass-rewrite read sites.
- **`static/js/brand.js`** (chat-core): `window.MAVEN_BRAND = Object.freeze({ name: "Maven", sourceUrl: "<same default>" })`, loaded early by `index.html`. A test asserts the JS and Python names match.
- **Brand files:** chosen concept B, source in `.claude/brand/b-secure-m/`. Ship SVGs to `static/brand/` (chat-core) and PNGs over `static/icons/icon-192.png`, `icon-512.png` and `icon-maskable-512.png` (workspace-apps), plus `static/brand/favicon-16.png` and `favicon-32.png` (chat-core).
- **Rename only what users or admins SEE or CONFIGURE** (D-1c-3): UI text, page titles, the PWA manifest, docs, `.env.example` names, CLI command names, model-facing identity ("you are Odysseus" → BRAND_NAME), and the FastAPI title.
- **LEAVE these:** localStorage and sessionStorage keys, cookies, `X-Odysseus-*` headers, internal function, module and variable names, env vars the app sets only for its own children, MCP server ids, code comments, and docker-compose interpolation variables (no docker here to verify nested `${A:-${B}}`; follow-up F-1).
- **CLIs:** `scripts/maven` and `scripts/maven-<x>` become the real scripts, holding the content of the old ones with visible text rebranded. The old `scripts/odysseus*` become thin Python shims that re-exec the new name with the same args, **guarded by `if __name__ == "__main__":`** (an unguarded `os.execv` at import time silently kills pytest when a test loads the script; found by inference-core). Tests load `maven-*` and check shims only as subprocesses, so existing cron and systemd entries keep working. Shell completions get `maven` names, and the old ones are kept.
- **Tests:** a test asserting an old visible string is updated in the same change (that is not weakening). Never delete an assertion.
- **Credit and legal:** keep every "Odysseus Contributors" copyright, LICENSE and licenses/. ACKNOWLEDGMENTS keeps the credit, adds "Maven is based on Odysseus", and fixes the stale "MIT core" text. `NOTICE.md` (docs-keeper) carries the AGPL §5a modified-version notice. The UI gets a "Source code" link to SOURCE_URL (§13).
- **Human-owned, not touched:** `specs/`, `.github/`, `website/`, `assets/branding/`, SECURITY.md, THREAT_MODEL.md, ROADMAP.md, `swift/`, `integrations/`, `Odysseus.spec`, `odysseus-ui.service` and the build/launch scripts. docs-keeper drafts their wording into BACKLOG for the human.

### done-when (shared)
`./venv/Scripts/python -m pytest tests/test_brand.py tests/test_brand_rename.py -q -p no:cacheprovider` passes. Then the full gate is GREEN on `fleet/S-1-verify`.
`test_brand_rename.py` asserts that `git grep -i odysseus` outside human-owned paths appears only in allowlisted contexts: credit/legal lines, the legacy alias constants, the left-alone internals listed above, and shims.

### Stage-3 rulings (main loop, 2026-10-05)
- **R1. Skip approved under D-1-3.** workspace-apps' new test `test_resolve_prefers_maven_and_falls_back_to_legacy` skips on Windows ("exec bit is not meaningful on Windows"). It is a new test, Windows-only, explicit reason, no existing assertion weakened. The gate will still return NEEDS-HUMAN for it, and the human confirms at landing.
- **R2. Cross-owner test edits accepted for this sprint.** 11 test files owned by agent-core (9) and security-core (2) were edited by workspace-apps ONLY to load `maven-*` instead of `odysseus-*`, a direct consequence of the CLI rename. Recorded here as part of the sprint's assignment.
- **R3. Favicon PNGs force-added.** `.gitignore:66` ignores `*.png` repo-wide; the existing static/icons PNGs are tracked by force-add. `static/brand/favicon-16.png` and `favicon-32.png` follow the same convention, because index.html links them.

### Follow-ups (not in S-1)
- F-1: docker-compose `MAVEN_AI_*` interpolation, after `docker compose config` can be verified. Needs a human with docker.
- F-2: an image registry name for the fork (CI is human-owned).
- F-3: migrate the left-alone internals (D-1c-3), if ever wanted.
