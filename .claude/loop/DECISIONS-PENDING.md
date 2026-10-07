# Decisions

Written by decision-broker. Newest on top. Answered items stay here as the record the orchestrator checks.

## Answered (human, 2026-10-04)

### D-0-1  Which phase first?
**Answer: Foundation first.** Phase 0, then Phase 1 (local-only mode, hardening, rebrand).

### D-0-2  Corporate build: shell, Python and file tools?
**Answer: keep them admin-only** (today's behaviour, no sandbox).

Consequences the fleet must honour:
- These tools stay blocked for non-admins. security-core adds regression tests that a non-admin and every non-admin team role can never reach them, including through the internal-tool loopback.
- The Phase 1b audit log must record every admin shell/Python/file tool call: who, when, the command, and the result size.
- The pitch and docs state it honestly: "admin tools run unsandboxed on the host; restrict admin accounts". Never write "sandboxed".

### D-0-3  Rename depth?
**Answer: full, with aliases.** This covers UI, docs, env vars, CLI names and image names. Old names (`ODYSSEUS_*` env vars, `odysseus-*` CLIs) keep working, and the `MAVEN_*` name wins when both are set.

### D-0-4  Knowledge graph store?
**Answer (human's words):** "separate graph server but make it in the same project i want to be able to deploy it on local or a server as i want or require".

Interpretation, binding for Phase 2:
- **Location.** The graph service is its own process and container. Its code lives in this repo (proposed: `graph_service/`), with its own requirements, Dockerfile and tests.
- **Interface.** Maven talks to it only over HTTP, through a client in `src/knowledge/`, with an endpoint from config (`MAVEN_GRAPH_URL`).
- **Deploy local.** A compose service on the same host is the default in `docker-compose.yml`, bound to the internal network only.
- **Deploy remote.** Point `MAVEN_GRAPH_URL` at another server. That requires auth between Maven and the graph service (a shared token or mTLS) and TLS, because company knowledge crosses the network. The same SSRF guard rules apply.
- **Data.** The graph data is backed up by its own snapshot/backup path, and `loop_snapshot.py` covers the local deployment's volume.
- **Library choice** (the graph database engine inside the service) is still open. It gets verified from the candidate repos (license, maintenance, Ollama/LangGraph fit) and proposed here before adoption.

## Answered (human, 2026-10-05, tick 1 dry run)

### D-1-1  F2: file tools reject the Windows temp folder (32 ids)
**Answer: change the tests, not the product.** `_tool_path_roots` in `src/tool_execution.py` stays as it is; the allowlist is not widened.
- Tests that use the OS temp dir switch to a root the tools already allow. They must keep exercising the same behaviour, with no weakened assertions.
- `test_code_nav_tools` stops hardcoding `/tmp`.
- The two `write_file` edge tests are separate: `recipe"draft.md` is an illegal Windows filename, and the other has a byte count off by CRLF. Changing their inputs could weaken them, so each goes to decision-broker with options before anyone edits it.

### D-1-2  F4: SearXNG migration on Windows (12 ids)
**Answer: guard it.**
- Call `os.fchmod`/`os.fchown` only where they exist (`hasattr`).
- Skip only the chmod-before-chown ordering test, with an explicit reason, on non-POSIX.
- Behaviour inside the Linux container must stay byte-identical, and the Linux CI path must still run every test.

### D-1-3  Platform-only tests (~10 ids)
**Answer: approved: skip with an explicit reason.** These are tests that need AF_UNIX, Apple Silicon, metal hwfit, Docker GPU or the cookbook docker paths.
- Use `pytest.mark.skipif(<platform condition>, reason=...)`, never unconditional skip or xfail. Each must still run on Linux CI.
- The gate will still return NEEDS-HUMAN on these. That is intended. decision-broker lists each added skip, referencing D-1-3, and the human confirms the landing. Never approve a skip outside this list.

### D-1-4  Upstream report for T-1-1 (`_is_sensitive_path` misses `/`-separated Windows paths)
**Answer: draft a private GitHub security advisory** for the human to send to odysseus-dev/odysseus after T-1-1 lands. Do not post it publicly and do not open a PR.

## Answered (human, 2026-10-05, Phase 1c rename)

### D-1c-0  Order
**Answer:** start Phase 1c (the rename) now. The batch-2 gate re-run (T-1-7 and T-1-8, killed for low memory) moves to the END of Phase 1c and gates batch 2 and the rename together.

### D-1c-1  Product name
**Answer: keep "Maven", as ONE setting.** The visible name lives in a single `BRAND_NAME` constant (Python `src/brand.py`, JS `static/js/brand.js`, with a test asserting they match), so a later legal check can change it in one place. The risks were flagged to the human: Apache Maven(TM), DoD Project Maven / Maven Smart System, and Maven AGI.

### D-1c-2  Env var prefix
**Answer: `MAVEN_AI_*`** (e.g. `MAVEN_AI_DATA_DIR`). This avoids Apache Maven's `MAVEN_HOME`/`MAVEN_OPTS`. Legacy `ODYSSEUS_*` keeps working through an alias shim, and the new name wins when both are set (D-0-3).

### D-1c-3  Internals
**Answer: leave invisible internals unchanged for now.** That covers browser storage keys (`odysseus-theme` …), cookies, `X-Odysseus-*` headers including the security-critical internal-tool token header, internal function and module names, and env vars the app sets only for its own child processes. Rename everything users or admins see or configure.

### D-1c-4  Logo
**Answer: concept B, "Secure M"**: an M inside a rounded vault shape, with an accent keyhole dot (#e06c75), on the app palette (#282c34 / #9cdef2). The human picked it from the concepts canvas https://claude.ai/artifact/Uc4Y6HdPCamTiycVF1ZQSf. Master files are in `.claude/brand/b-secure-m/` (concept C, the prompt mark, is saved in `.claude/brand/c-prompt-mark/` for later, at the human's request): mark, light mark, solid favicon, wordmark lockup (SVG), plus icon-192/512, maskable-512 and favicon-16/32 (PNG). Below 32px the keyhole dot drops and the tile fills solid.

## Pending

### D-1c-7  Fine-tuned model prompts still say "Odysseus" (S-1, agent-core)
context: The LoRA minimal prompts in src/agent_loop.py (~1770-1915) keep "Odysseus" ("Use Odysseus tool-call format"), because the `odysseus-qwen3` fine-tunes were trained on exactly that text. Changing it likely degrades those models.
options: A) keep them (recommended); only users running those specific fine-tunes see the old name. B) rebrand anyway, which is mechanical, and accept the quality risk for those models.
if no answer: kept.

### D-1c-6  Rename wording for files only you edit (drafted by docs-keeper, S-1)
kind: human-owned edits. Optional, but until done these still say Odysseus.

**SECURITY.md** (product name only; every security statement unchanged):
1. L3 "Odysseus is a self-hosted AI workspace…" → "Maven is a self-hosted AI workspace…"
2. L13 "(for a proxy Odysseus cannot see the scheme of)" → "Maven"
3. L15 "authenticated Odysseus web/API entrypoint" → "Maven"
4. L22 "Odysseus API tokens" → "Maven API tokens"
5. L24 "internal-only ports are Odysseus `7000`" → "Maven `7000`"

**THREAT_MODEL.md**:
1. L3 "Odysseus is a **self-hosted AI workspace…**" → "Maven"
2. L7 "Odysseus is designed for **trusted users…**" → "Maven"

Keep `X-Odysseus-Internal-Token` (L49) unchanged; it is a real header name (D-1c-3).

**Also mention Odysseus:**
- ROADMAP.md (2)
- website/: setup.md, index.html, agent-migration.md, guides, _config.yml
- specs/ (read-only by project rule; a spec-maintenance pass)
- .github/: bug_report.yml and feature_request.yml issue templates, pull_request_template.md
- .github/scripts/check-issue-description.js expects the "Odysseus Revision" field label that bug_report.yml defines. **Change both together or neither**, or issue checks break.

options: A) apply the SECURITY/THREAT_MODEL lines now and leave website/specs/.github for later (recommended, because those two are what a security reviewer reads); B) leave all until later.


### D-0-5  Promote the gate baseline and commit the fleet scripts (Phase 0)
kind: dependency (loop setup)

context: The agents are denied these two edits by design. Until both are done, every gate run is RED and nothing can land.

Status: the scripts were committed on 2026-10-04 (`12f5967c`). **Remaining:** promote the baseline. Agents are denied this; run:
```
! mv .claude/loop/gate-baseline.proposed.txt .claude/loop/gate-baseline.txt
```

Note: the baseline masks 186 failing tests, including `test_write_file_empty_body`, `test_tool_path_confinement` and `test_agent_state_dir_confinement`. Phase 0's first tickets shrink it.
