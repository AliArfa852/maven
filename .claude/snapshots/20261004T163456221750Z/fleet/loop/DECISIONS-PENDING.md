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

## Pending

### D-0-5  Promote the gate baseline and commit the fleet scripts (Phase 0)
kind: dependency (loop setup)

context: The agents are denied these two edits by design. Until both are done, every gate run is RED and nothing can land.

Status: the scripts were committed on 2026-10-04 (`12f5967c`). **Remaining:** promote the baseline. Agents are denied this; run:
```
! mv .claude/loop/gate-baseline.proposed.txt .claude/loop/gate-baseline.txt
```

Note: the baseline masks 186 failing tests, including `test_write_file_empty_body`, `test_tool_path_confinement` and `test_agent_state_dir_confinement`. Phase 0's first tickets shrink it.
