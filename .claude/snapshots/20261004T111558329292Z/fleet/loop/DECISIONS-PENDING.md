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

## Pending

### D-0-5  Promote the gate baseline and commit the fleet scripts (Phase 0)
kind: dependency (loop setup)

context: The agents are denied these two edits by design. Until both are done, every gate run is RED and nothing can land.

Status: the scripts were committed on 2026-10-04 (`12f5967c`). **Remaining:** promote the baseline. Agents are denied this; run:
```
! mv .claude/loop/gate-baseline.proposed.txt .claude/loop/gate-baseline.txt
```

Note: the baseline masks 186 failing tests, including `test_write_file_empty_body`, `test_tool_path_confinement` and `test_agent_state_dir_confinement`. Phase 0's first tickets shrink it.
