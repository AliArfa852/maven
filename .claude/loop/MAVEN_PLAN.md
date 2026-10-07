# Maven plan v2: a corporate, local-first AI workspace (fork of Odysseus)

**Status:** v2 draft, 2026-10-07. Replaces v1 (2026-10-04). Decisions marked **[DECIDE]** are mirrored into DECISIONS-PENDING.md (D-2-*). The defaults shown are recommendations until the human answers.

**Who reads this:** the human, and the orchestrator, which reads this file every tick and queues tickets only from the **active phase**.

**Product:** Maven is software a company installs on its own servers. It gives every employee AI help with chat, documents, spreadsheets, analysis and reports, and it knows the company's knowledge. Each person sees only what their role and clearance allow. Nothing leaves the company network, and every use can be audited.

**Pitch:** "Your AI, on your servers." We never claim cloud vendors are insecure. We claim **control, residency, least privilege and auditability**, and the product must prove each of those with tests (see "Proof points" below).

---

## 1. Requirements

v1 requirements R1–R11 still stand. R12–R20 were added on 2026-10-07.

| # | Requirement | Phase |
| --- | --- | --- |
| R1 | Rebrand to **Maven**, with a corporate look | 1 |
| R2 | Sheets: open, edit, query, and write results back | 3 |
| R3 | A local knowledge base: knowledge graph + GraphRAG on local (Ollama) models | 4 |
| R4 | Structured and unstructured document processing | 3 |
| R5 | Team personas, with automatic persona recommendation | 6 |
| R6 | A simple GUI for non-technical staff | 6 |
| R7 | Admin-locked local-only mode | 1 |
| R8 | Corporate hardening, so it is "safe to deploy locally" | 1, 2 |
| R9 | Visualizations from computed data, never from the model's memory; "show data" and a source on every chart | 5 |
| R10 | The knowledge graph as on-demand, cited context that respects permissions | 4 |
| R11 | Diagrams from simple to advanced, recommended from the data shape and the user's intent | 5 |
| **R12** | **File tools:** read and extract from PDF, DOCX, XLSX/CSV and PPTX (including tables and scanned pages), and **create** XLSX, DOCX, PDF, PPTX and CSV | 3 |
| **R13** | **Two-tier knowledge:** (a) context limited to a conversation and the resources given to it; (b) a company-wide knowledge graph built from the knowledge base and from approved insights out of chats | 3 (a), 4 (b) |
| **R14** | **Shared sessions:** several employees work in one conversation with shared resources | 3 |
| **R15** | **Data analysis:** finance and general analysis of structured and unstructured data, in a sandbox | 5 |
| **R16** | **Report builder:** reports with charts, tables and diagrams, exported to PDF, DOCX or PPTX | 5 |
| **R17** | **Role-based access:** Basic, Advanced, Manager, General Manager and Admin, plus the improvements in §3 | 2 |
| **R18** | **No data leakage:** email, contracts, financials and other sensitive data never leave through the model, tools, exports or other users | 2 onward |
| **R19** | **Conversation flagging:** inappropriate use is flagged for review | 2 (rules), 6 (classifier) |
| **R20** | **Sellable to corporations:** installer, SSO, updates, backups, compliance documents, support | 7 |
| **R21** | **Admin Console** with view-only access for Managers, duty-only access for Compliance Officers, full access for Admins; several roles per user; a default admin account | 2 (started) |

---

## 2. Main changes from v1, and why

1. **Access control and data classification now come before the knowledge graph** (the new Phase 2). Adding permissions afterwards to a RAG index or graph that already holds mixed-sensitivity data is the classic way these products leak. Every stored item gets an owner, a team and a label from the day it is created.
2. **Chats do not flow into the company graph automatically.** Doing so would leak one employee's conversation to everyone. Chat knowledge reaches the graph only through a **promotion pipeline**: the system proposes, the author consents, and the knowledge owner approves (§4.3).
3. **Permission checks happen before the model sees anything.** Retrieval filters by permission inside the store (security trimming). We never rely on a prompt telling the model "don't reveal X".
4. **Sessions carry a sensitivity level ("taint tracking").** A session takes the highest label of anything it has read. That level then gates outbound tools, exports and sharing (§3.4). This one mechanism covers most leak paths.
5. **Separation of duties.** An admin runs the system but does not automatically read everyone's content. Flag review belongs to a separate Compliance role. Using emergency "break-glass" access is itself audited.
6. **Data analysis runs in a sandbox, not with the admin-only Python tool.** D-0-2 keeps shell and Python tools admin-only and unsandboxed. Analysis for every employee therefore needs its own locked runtime (§5.2).
7. **PostgreSQL is the corporate database** (decided, D-2-1). SQLite stays for single-user installs. Postgres handles many concurrent users, and row-level security gives a second, database-level permission check. It can also hold vectors (pgvector) and possibly the graph (Apache AGE), so there is one store to back up.

---

## 3. Access model (R17, R18)

### 3.1 Three independent dimensions

The roles you listed mix three different questions. Keeping them separate is what makes the system configurable for real companies.

| Dimension | Question it answers | Values |
| --- | --- | --- |
| **Role** (capabilities) | What can this person *do*? | Basic, Advanced, Manager, General Manager, Admin, plus **Compliance Officer** (new) |
| **Clearance** (data level) | How sensitive can the data they *see* be? | Public < Internal < Confidential < Restricted |
| **Scope** (organisation) | *Whose* data is it? | own, team, department, company; plus explicit grants (e.g. "Finance contracts folder") |

A user can see an item only when **all three** allow it: role permits the feature, clearance ≥ the item's label, and scope covers the item's owner/team (or an explicit grant exists).

### 3.2 Default roles (companies can edit them)

| Capability | Basic | Advanced | Manager | General Manager | Compliance | Admin |
| --- | --- | --- | --- | --- | --- | --- |
| Chat, own files, team knowledge (read) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Read/extract files, create documents | ✓ | ✓ | ✓ | ✓ | – | ✓ |
| Data analysis sandbox, sheets write-back, report builder | – | ✓ | ✓ | ✓ | – | ✓ |
| Create shared sessions | – | ✓ | ✓ | ✓ | – | ✓ |
| Larger models / longer context | – | ✓ | ✓ | ✓ | – | ✓ |
| Curate team knowledge base, approve promotions | – | – | ✓ (team) | ✓ (dept/company) | – | – |
| Team usage reports (aggregate, no content) | – | – | ✓ | ✓ | – | ✓ |
| Review flagged conversations | – | – | – | – | ✓ | – |
| Users, roles, models, settings, integrations | – | – | – | – | – | ✓ |
| Shell / Python / file tools on the host (D-0-2) | – | – | – | – | – | ✓ (audited) |
| Read other users' content | – | – | – | – | flagged excerpts only | break-glass only, audited and notified |

**Default clearance (decided, D-2-2):** Basic = Internal, Advanced = Internal, Manager = Confidential, General Manager = Restricted, Compliance = Restricted (flag excerpts only), Admin = Internal (separation of duties). A new user gets the default for their roles unless an Admin sets an override.

**Several roles per user (decided, D-2-8):** capabilities are the union of the user's roles, and clearance is the highest default among them unless overridden. Every user holds Basic.

**Admin Console (decided, D-2-8):** one page for monitoring, decisions and changes.
- **Admin:** full access; changes users, roles, clearance and settings.
- **Manager / General Manager:** can open it and see everything on it, but **change nothing**.
- **Compliance Officer:** can open it and see it, and can carry out **only compliance duties** (the flag review queue); nothing else.
- **Basic / Advanced:** no access.
- The server enforces every read and change; the page only hides what a user may not do.
- **Default admin account:** the first-run setup creates an admin (`MAVEN_AI_ADMIN_USER` / `MAVEN_AI_ADMIN_PASSWORD`, or a generated password printed once). The last admin can never be removed.

**Built (2026-10-07, branch `claude/bold-lovelace-pppvnh`):** `src/access.py` (roles, clearance, capabilities); roles and clearance stored per user in `core/auth.py`, with Admin still driven by `is_admin` so every existing admin gate is unchanged; `require_capability` in `core/middleware.py`; `GET /api/auth/users` and `GET /api/auth/roles` for console viewers; `PUT /api/auth/users/{u}/roles` and `/clearance` for Admins; the `/admin-console` page, linked from Settings → Account; `tests/test_access_roles.py`.

**Next for the console:** the flag review queue (with flagging, §6); audit-log and usage views; read-only views of the existing admin settings for Managers, after each one is checked for secrets it might show.

### 3.3 Labels on data

- Every document, chunk, graph node and edge, session, generated file and memory stores `owner`, `team`, `label` and optional `grants`.
- Labels come from the knowledge-base folder (e.g. `/Finance/*` defaults to Confidential), from the uploader (who can raise a label but not lower it below the folder default), and from a classifier (§3.5). **The highest of these wins.**
- Files Maven generates inherit the highest label of their inputs.

### 3.4 Taint tracking: how leaks are stopped

The session's level is the highest label it has read (retrieved chunks, attachments, tool results).

| Session level | Outbound tools (email send, webhooks, web fetch, external MCP) | Export / download | Share with |
| --- | --- | --- | --- |
| Public / Internal | allowed | allowed | anyone in scope |
| Confidential | needs per-call approval, and the DLP scan (§3.5) must pass | watermarked, logged | only users with Confidential+ clearance and scope |
| Restricted | **blocked** | admin policy (default: block), watermarked, logged | named users with Restricted clearance only |

Web fetches are checked for data carried in the URL or query string. Model answers are never cached across users.

### 3.5 Data loss prevention (DLP) and classification

- **Detectors, all running locally:** PII (names, IDs, IBANs, card numbers, emails, phone numbers), secrets (API keys, private keys), finance patterns, contract markers, and custom company dictionaries (project code names, client names).
- **Where they run:** on ingest (to propose a label), on every outbound tool call and export, on what gets promoted to the graph, and on logs (logs store redacted text).
- **Proposal:** start with rules plus a small local NER model. Add an LLM classifier only for borderline cases. **[DECIDE D-2-3: Microsoft Presidio (MIT) as the PII engine, after verifying its license and fit]**

### 3.6 Identity

- Roles and clearance live in `data/auth.json` for now (built). Phase 2 moves users into database tables (`users`, `teams`, `departments`, `user_roles`, `grants`), in Postgres for corporate installs, migrating existing users in place.
- **PostgreSQL rollout (D-2-1).** Built 2026-10-07: `docker/postgres.yml` overlay (internal network only, volume, required password); bare `postgresql://` URLs pinned to the shipped psycopg2 driver (SQLAlchemy 2.1 defaulted to psycopg v3, so Postgres never started); startup migrations read columns through a dialect-neutral helper instead of `PRAGMA`; the email MCP server reads accounts from `DATABASE_URL`; `scripts/maven-db copy-to-postgres` moves `app.db`; live-PostgreSQL tests behind `MAVEN_AI_TEST_POSTGRES_URL`. Verified by hand: login, roles, sessions, chat, history, notes, documents, archive/export/delete on a fresh and on a copied database. **Still to do:** run the whole suite against Postgres in CI (needs a `.github/` change, human-owned); include Postgres in `maven-backup`; history search uses plain text matching on Postgres (SQLite has FTS5), so add Postgres full-text search; scheduled-email, email-cache and lock files stay local SQLite by design.
- SSO through OIDC (Entra ID, Okta, Keycloak) and SAML. Map directory groups to roles, teams and clearance. SCIM provisioning in Phase 7.
- A "permission matrix" test, generated from the route table, checks every endpoint × role and fails CI if a new endpoint has no policy.

---

## 4. Knowledge (R3, R10, R13, R14)

### 4.1 Tier 0: personal memory (exists today)
This is the user's own memories, owner-scoped. No change apart from adding labels.

### 4.2 Tier 1: session knowledge (conversation-limited RAG)
- Each session has its own index namespace. It holds that session's attachments, linked documents, pasted resources, and the tool outputs the user pinned.
- Only the session's participants can query it. It is deleted with the session, or kept per the retention policy.
- **Shared sessions:** an owner adds participants as editor or viewer. Adding someone is checked against the session's level (§3.4). Participants share the Tier-1 index and each sees the others' messages. Per-participant personal memory is **never** shared.
- Retrieval order inside a session: Tier 1 first, then Tier 2 filtered by permission, then personal memory. Answers cite which tier each fact came from.

### 4.3 Tier 2: company knowledge graph
- **Sources:**
  - knowledge-base folders curated by Managers
  - uploaded document sets
  - later, read-only connectors (SharePoint, network shares, Confluence) running inside the network
  - **approved promotions from chats**
- **Promotion pipeline** (replaces "store context from all chats"):
  1. After a useful conversation, Maven proposes a short list of facts or decisions, each with a citation back to the chat.
  2. The author confirms what may be shared and picks the audience (team / department / company), capped by the session's level.
  3. The team's knowledge owner (a Manager) approves, edits or rejects.
  4. The promoted fact becomes a graph node, keeping its provenance, label and ACL.
- **Graph model:**
  - entities: person, team, client, project, contract, product, metric, document, decision
  - relations, each with a source, time and confidence
  - every node and edge carries a label and scope
- **Retrieval (GraphRAG as a LangGraph flow):**
  1. Route: does this question need company knowledge?
  2. Entity linking.
  3. Graph neighbourhood + passage retrieval, **both filtered by permission inside the store.**
  4. Rerank.
  5. Answer with citations.

  Retrieved text always goes through `untrusted_context_message` (it is data, not instructions).
- **Freshness and quality:** re-ingest when a source changes; flag contradictions between sources ("Contract A says 30 days, Policy B says 45"); show an "as of" date on facts.
- **Store:** a separate graph service (D-0-4 still holds: `graph_service/`, HTTP at `MAVEN_GRAPH_URL`, local or remote, token/mTLS + TLS). Candidate engines, all to be verified for license, maintenance and fit before a proposal: **PostgreSQL + Apache AGE + pgvector** (recommended: one store, row-level security, permissive licenses) or Neo4j Community. **[DECIDE D-2-4]**

### 4.4 Quality gates
- A golden question set per pilot company: answer accuracy, citation correctness, and **zero cross-scope leaks**.
- A leak red-team suite: users at lower clearance try prompt injection, "summarise everything about X", or indirect questions to pull Restricted facts. Any leak fails CI.

---

## 5. Documents, analysis and reports (R2, R4, R9, R11, R12, R15, R16)

### 5.1 File tools (R12)

| Format | Read / extract (today → target) | Create (target) |
| --- | --- | --- |
| PDF | pypdf text, plus PyMuPDF (optional) → add layout-aware tables, **OCR for scanned pages** (Tesseract/ocrmypdf, local), and form fields (`pdf_forms.py` exists) | Render from Markdown/HTML with company templates (header, footer, watermark, label banner) |
| DOCX | markitdown (optional) → python-docx for structure: headings, tables, tracked changes, comments | python-docx from templates (letterhead, styles); fill templates (contracts, memos) |
| XLSX / CSV | markitdown text dump → **typed tables**: sheets, headers, data types, formulas kept, named ranges; large files streamed | openpyxl: multiple sheets, formulas, number formats, frozen headers, native charts |
| PPTX | markitdown → slide text, speaker notes, tables | python-pptx from a company master: title, chart and table slides |

- **Structured extraction:** pull to a schema (invoice fields, contract clauses such as parties, term, renewal, liability cap, payment terms) with a **citation to the page, cell or paragraph** for every field. Users can review the result as a table before it is saved.
- **Agent tools:** `file_read`, `file_extract_tables`, `file_extract_schema`, `file_create_{xlsx,docx,pdf,pptx,csv}`, `sheet_query` (SQL over the uploaded tables), `sheet_write_back`.
- **Sheets (R2):** on-prem, without Google Sheets. Use the vendored SheetJS viewer/editor in the app. Later, optionally integrate OnlyOffice or Collabora for full office editing. **[DECIDE D-2-5]**
- **Dependencies:** move document extraction from optional to standard in the corporate build. Verify every library's license and record it in ACKNOWLEDGMENTS.

### 5.2 Data analysis (R15)
- **Sandbox:** a separate container with no network, a read-only input mount, CPU/RAM/time limits and a seccomp profile, running pandas, numpy and statsmodels. Small jobs can run in the browser with Pyodide instead. Never use the host Python tool. **[DECIDE D-2-6: container sandbox (recommended) vs Pyodide only]**
- **Flow:** profile the data (code, not the model) → the model writes analysis code → the sandbox runs it → the result is shown with the code ("show work") → the numbers in the answer come only from the result.
- **Finance helpers:** period-over-period, variance, budget vs actual, ratios, currency and number formatting, and reconciliation checks (totals must add up, or Maven says why they don't).
- **Unstructured data:** themes, sentiment and entity counts across documents, emails or tickets, then turned into tables the analysis tools can use.

### 5.3 Visualization and reports (R9, R11, R16)
- Keep v1's design: the data profiler → intent → a rules table of chart candidates ranked Simple/Detailed/Advanced → the model ranks and explains → validate, then repair up to 2 times.
- **Renderers, vendored locally (licenses verified):** Vega-Lite (charts), Mermaid (already vendored; flows and org charts), Cytoscape.js (graph views).
- **Report builder:** a report is a Document made of sections: text, chart, table, diagram, KPI tiles, citations.
  - It can be edited in the existing editor.
  - It exports to PDF, DOCX or PPTX through the §5.1 creators.
  - It carries the highest label of its data and gets a label banner.
  - Every chart offers "show data" and links to its source.
- **Templates:** monthly finance pack, project status, sales pipeline, board summary.

---

## 6. Oversight (R19)

- **Flagging, Phase 2 (rules):** attempts to reach data above the user's clearance, bulk-export or exfiltration patterns, prompt-injection and jailbreak patterns, and company keyword lists. **Phase 6 (classifier):** a small local model for harassment, abuse and clearly non-work misuse, with thresholds the company sets.
- **Review queue for the Compliance role:** reviewers see the flagged excerpt and its context window, not the whole history. Escalation to full access needs a reason and is audited. Outcomes are dismiss, warn or escalate. Maven itself never punishes anyone automatically.
- **Employee transparency:** a configurable notice in the UI explains what is logged and flagged. Retention periods are configurable, and the company decides whether flag outcomes are shown to the user. **Monitoring employees has legal rules** (GDPR, works councils in parts of the EU), so the deploying company's counsel must sign off on its configuration. Ship a DPIA template.
- **Audit log** (append-only, hash-chained so tampering is detectable): logins, role changes, data access by label, tool calls, exports, shares, promotions, break-glass use, and flag decisions. Admin and Compliance can export it to the company's SIEM (syslog or JSON).

---

## 7. Productization (R20)

| Area | Deliverable |
| --- | --- |
| Install | Docker Compose bundle; an **offline / air-gapped bundle** with images and models; hardware sizing guide (small / medium / large); later a Helm chart |
| Updates | Signed releases, automatic database migrations, a pre-upgrade backup, rollback |
| Backup | One command and a UI flow covering the database, vectors, graph and files; encrypted; restore tested in CI |
| Encryption | TLS everywhere; data at rest on encrypted volumes (documented); secrets via the existing `secret_storage` |
| Identity | OIDC/SAML SSO, SCIM, mapping directory groups to roles |
| Admin console | Users, roles, clearance, teams, knowledge sources, models, policies, usage dashboards |
| Trust pack | Security whitepaper, threat model, data-flow diagram, DPIA template, controls mapped to ISO 27001 / SOC 2 themes, results of an external pen test |
| Commercial | **AGPL constraints:** the code cannot be relicensed (351 contributors, no CLA), and customers who receive Maven get its source. Revenue therefore comes from **subscriptions for support and updates, installation, training, SLAs, managed hosting on the customer's own hardware, and certified appliance bundles.** Add-ons linked into Maven are AGPL as well. **Counsel reviews this before the first sale.** **[DECIDE D-2-7]** |
| Name | "Maven" trademark search before launch (Apache Maven, Project Maven, Maven AGI were flagged in D-1c-1). The name lives in one constant, so a change is cheap. |
| Pilot | One design-partner company, starting at the end of Phase 3 |

---

## 8. Phases and order

Only the **active** phase gets tickets. Each phase lands behind a GREEN full gate.

| Phase | Content | Exit (done-when) |
| --- | --- | --- |
| **0** | Shrink the test baseline (Windows harness fixes) | Baseline ≤ 40 entries, each with a reason |
| **1** | 1a local-only mode; 1b hardening (SSRF fix, admin-tool tests, audit-log v1); **1c rename (S-1)** | No-egress test and CSP test; rename completeness test; full gate GREEN |
| **2 (new)** | **Identity and governance:** user/team/role/clearance tables and migration; labels on all stored items; a single policy engine; permission-matrix test; taint tracking; DLP v1; flagging rules v1; hash-chained audit log; break-glass; Postgres option (D-2-1) | Permission-matrix test covers 100% of routes; leak red-team v1 passes; existing users migrate without data loss |
| **3** | **Files and sessions:** the R12 file tools; structured extraction; the sheets viewer and write-back; **Tier-1 session RAG**; **shared sessions** | Round-trip tests per format (read → create → read again); a session index never answers outside its session; share checks enforce clearance |
| **4** | **Company knowledge:** graph service, ingestion connectors, the promotion pipeline, GraphRAG, contradiction flags | Golden-set accuracy target met; **zero** cross-scope leaks in the red-team suite |
| **5** | **Analysis and reports:** analysis sandbox, finance helpers, chart pipeline, report builder and exports | Every number in a report traces to a computed result; the sandbox has no network (tested) |
| **6** | **People and oversight:** personas and recommendation; Simple mode as the default for non-admins; flag classifier; Compliance console | Usability test with non-technical staff; flag precision/recall measured on a labelled set |
| **7** | **Ship:** offline installer, SSO/SCIM, upgrades, backup/restore, trust pack, pen test, pilot go-live | A pilot company runs Maven in production for 30 days |

**What runs in parallel:** the trust-pack writing and the D-2-* decisions can start now. Phase 3's file creators do not depend on the graph, and may start once Phase 2's label fields exist.

---

## 9. Proof points (tests that back the pitch)

| Claim | Test |
| --- | --- |
| Nothing leaves your network | In local-only mode, an egress test records every outbound socket; only allowlisted hosts are reached |
| People see only what they're allowed | A permission-matrix test (route × role); retrieval tests (label × clearance × scope) for the vector store, the graph and the analysis sandbox |
| The AI can't be tricked into leaking | The leak red-team suite runs on every gate |
| Every number is real | The report-trace test: each figure maps to a sandbox result or a source cell |
| Everything is auditable | Audit-chain integrity test; a test that every sensitive action writes a log entry |

---

## 10. Legal guardrails (unchanged from v1, apply to every phase)

- **Maven stays AGPL-3.0-or-later** (relicensed 2026-06-09, `23f0d64e`; 351 contributors; no CLA).
- **Keep:** `LICENSE`, the "Odysseus Contributors" notices, `ACKNOWLEDGMENTS.md`, `licenses/*` (MIT and Apache; Apache also needs a statement of changes).
- **Done in S-1:** the AGPL §5a modified-version notice (`NOTICE.md`) and the §13 "Source" link in the UI.
- **Remove** the Odysseus name and logos from the product (no trademark grant). "Based on Odysseus" is fine.
- **New dependencies:** each needs a license line in ACKNOWLEDGMENTS, verified from the repo, not from memory.
- **Counsel** signs off on the AGPL position, the monitoring features (§6) and the trademark before any customer deployment. That is human-owned.

---

## 11. Fleet changes by phase

| Phase | Change |
| --- | --- |
| 0–1 | No new agents. |
| 2 | `security-core` leads. Proposed new agent: `governance-core` (policy engine, labels, DLP, audit, flagging), split out of `security-core` if Phase 2 makes it too large. Self-review decides. |
| 3 | `workspace-apps` owns the file tools; `chat-core` owns shared sessions. |
| 4 | Add `knowledge-core` (from v1), owning `src/knowledge/`, `graph_service/`, ingestion and retrieval. |
| 5 | `agent-core` owns the analysis sandbox and data tools; `chat-core` owns rendering and the report builder. |
| 6–7 | `docs-keeper` owns the trust pack; there is no agent for the pen test or legal review (human-owned). |
