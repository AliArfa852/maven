# Maven plan: corporate, local-first AI workspace (fork of Odysseus)

**Status:** draft, 2026-10-04. Decisions marked **[DECIDE]** are open in DECISIONS-PENDING.md. The defaults shown are recommendations until the human answers.

**Who reads this:** the human, and the orchestrator, which reads this file every tick and queues tickets only from the **active phase**.

**Pitch:** "Your AI, on your servers." Chats, documents, skills and the knowledge graph never leave hardware you own. It is open source, so it is auditable. It works offline. We never claim cloud vendors are insecure. We claim control, residency and auditability, and the product must prove each of those (Phase 1 gates).

## Requirements (from the human, 2026-10-04)

| # | Requirement |
| --- | --- |
| R1 | Rebrand to **Maven**, with a corporate-friendly look. |
| R2 | Sheets integration. |
| R3 | A local knowledge base: knowledge graph + GraphRAG, with LangGraph orchestration and Ollama models. |
| R4 | Structured and unstructured document processing: sheets, PDF, docs. |
| R5 | Team personas, with automatic persona recommendation. |
| R6 | A simple GUI for non-technical corporate staff. |
| R7 | Chat context, skills and knowledge files stored and processed locally, through an admin-locked local-only mode. |
| R8 | A "safe to deploy locally" pitch, which requires corporate hardening. |
| R9 | Visualizations from chat data. The numbers come from computed data, never from the model's memory. Every chart has "show data" and a source. |
| R10 | The knowledge graph as on-demand context for chat, charts and graph views. It is team-scoped and cited. |
| R11 | Diagrams from basic to complex, recommended by the chat from the data shape and the user's intent. They are ranked Simple / Detailed / Advanced, shown as preview cards, validated and auto-repaired, and learned per team. |

## Legal guardrails (apply to every phase)

- **Maven stays AGPL-3.0-or-later.** The project was relicensed on 2026-06-09 (`23f0d64e`). It has 351 contributors and no CLA.
- **Keep:**
  - `LICENSE`
  - the "Odysseus Contributors" notices
  - `ACKNOWLEDGMENTS.md`
  - `licenses/*` (the MIT and Apache notices; Apache also needs a statement of changes)
- **Add:** a modified-version notice under AGPL §5a, and a "Source" link in the UI under §13.
- **Remove:** the Odysseus name and logos from the product (no trademark grant). Saying "based on Odysseus" is fine.
- **New dependencies:** each needs a license line added to ACKNOWLEDGMENTS, verified from the repo, not from memory.
- **Counsel:** company counsel signs off on the AGPL position before any customer deployment. That is human-owned.

## Phase 0: make the loop able to land (human + security-core)

| Step | Owner |
| --- | --- |
| Commit `scripts/fleet_gate.py`, `fleet_ownership.py`, `loop_snapshot.py` | human |
| Promote `gate-baseline.proposed.txt` to `gate-baseline.txt` (186 failures, 5,956 tests) | human |
| Shrink the baseline by fixing the Windows-only harness failures: about 60 Node ESM `C:\` URL errors, about 20 cp1252 encoding errors, `socket.AF_UNIX` | security-core (tests/helpers, conftest) |

The confinement and `write_file` failures in the baseline mask exactly the areas the pitch depends on, so they come first.

**Exit:** the baseline has ≤ 40 entries, and every remaining entry has a one-line reason.

## Phase 1: foundation (R1, R7, R8)

These are cheap and unblock the pitch. **Decided (D-0-1): this phase goes first.**

### 1a. Local-only mode, admin-locked, on by default
- Ollama is the only chat provider and the only embedding provider.
- Cloud providers are hidden and blocked server-side.
- Embeddings never call an external HTTP API.
- Pyodide and PDFObject are vendored into `static/lib/`. No CDN scripts, and the CSP drops `cdn.jsdelivr.net`.
- Web search and deep research are off by default.
- **done-when:** a test asserts that no outbound request goes to a non-allowlisted host in local-only mode (owner: security-core). A CSP test asserts no third-party script origin (owner: chat-core).

### 1b. Hardening

| Item | Owner | Notes |
| --- | --- | --- |
| Fix the SSRF via `/api/v1/chat` `base_url` (THREAT_MODEL gap 2) | security-core | regression test first |
| Shell, Python and file tools stay **admin-only, unsandboxed (D-0-2)**. Add tests that non-admins and team roles can never reach them; the audit log records every call; the docs say "unsandboxed". | security-core | |
| Audit log: who asked what, and which documents and tools were used | security-core | append-only, local |
| Per-team roles: a `team` on users and on stored items, with owner-scope checks extended to team scope | security-core | It is a design, so it needs a sprint |
| SSO (OIDC: Entra ID, Okta) | — | Phase 1 design, Phase 2 build |

### 1c. Rebrand to Maven (sprint, led by chat-core)

- **Decided (D-0-3): depth is full.** That means "UI/docs plus env/CLI/image names with compatibility aliases": `ODYSSEUS_DATA_DIR` keeps working, and `MAVEN_DATA_DIR` wins when both are set.
- **Size:** 2,649 occurrences across 397 files.
- **Human-owned edits:** `assets/branding/*` (new logo), `website/`, `specs/`, and the license notices.
- **Visual review** of the corporate theme ends as `needs-human`.
- **done-when:** `git grep -i odysseus` returns only allowlisted lines (license notices, compatibility aliases, ACKNOWLEDGMENTS, the "based on" credit), checked by a test, and the §5a notice is present.

### 1c-end. Batch-2 gate re-run (D-1c-0)
Gate `fleet/batch-2-verify` (T-1-7, T-1-8) together with the rename sprint branch, which is based on it, in one full gate. Land on GREEN.

## Phase 2: documents in, knowledge out (R4, R2, R3)

| Item | Detail |
| --- | --- |
| Ingestion pipeline | `.xlsx`/`.csv`/`.pdf`/`.docx`/`.pptx`. Structured inputs become typed tables (SQLite). Unstructured inputs become chunks plus entities and relations. Every fact carries its source document, page or cell, team, and ingest time. |
| Knowledge graph store | **Decided (D-0-4):** a **separate graph service in this repo** (`graph_service/`: its own container, requirements and tests). Maven reaches it only over HTTP through `src/knowledge/` at `MAVEN_GRAPH_URL`. It runs locally (compose, internal network) or on a remote server (token/mTLS auth plus TLS required). The graph engine inside the service is chosen after verifying the candidates' licenses and maintenance; it is proposed to the human first. |
| GraphRAG retrieval as a LangGraph flow | route (does this need company knowledge?) → graph query + passage retrieval → answer with citations. Retrieved content always goes through `untrusted_context_message`. |
| Sheets integration (R2) | Open, preview and query sheets in chat; write results back to a new sheet. SheetJS is already vendored. |

**Re-banding (the default; the human can reject it):** documents/RAG and the knowledge base become **core**, so a new owner `knowledge-core` is split out of `workspace-apps` when Phase 2 creates `src/knowledge/`. Its OWNERSHIP rules land in the same change.

## Phase 3: visualization (R9, R10, R11) (sprint: chat-core + agent-core)

- **Data profiler:** column types, cardinality, time, hierarchy, flows, links. It is code, not the model.
- **Intent classification:** compare, trend, composition, distribution, relationship, flow, connections.
- **Recommendation:** a rules table maps (shape × intent) to diagram candidates, ranked Simple → Advanced. The model only ranks them and explains each in one sentence.
- **Renderers,** bundled locally:
  - Mermaid (already vendored) for processes and diagrams
  - Vega-Lite for data charts and linked dashboards
  - Cytoscape.js for knowledge-graph network views

  Each library's license is verified before it is vendored.
- **Validate before showing:** a broken spec goes back to the model for repair, up to 2 retries. Templates are used for the complex types.
- **"Show data" and a source citation on every chart.** Export to PNG/SVG and to a sheet.
- **Learned preferences** per team and persona, stored locally.

## Phase 4: people (R5, R6)

- **Team personas:** prompt, default knowledge scope, tools, and preferred chart complexity, per team.
- **Automatic persona recommendation** from the question and the parts of the graph it touches.
- **Simple mode:** a single chat box plus "Ask about a document" and suggested actions, with no model or provider jargon. It is the default for non-admin users. Advanced mode is admin-only.

## Fleet changes by phase

| Phase | Change |
| --- | --- |
| 0–1 | No new agents. |
| 2 | Add `knowledge-core` (sonnet, sprint lead), owning `src/knowledge/`, ingestion and graph retrieval. That is 15 agents. Self-review checks whether `workspace-apps` shrinks enough to justify it. |
| 3–4 | No new agents unless the evidence asks for one. Visualization belongs to chat-core (rendering) and agent-core (the data query tool). |
