# Odysseus agent fleet

A self-improving maintenance loop for this fork of odysseus-dev/odysseus. The roster is derived from the project's modules. The MVP, set by the human, is **agent, chat, security and local inference**.

Rules of the loop: `.claude/loop/PROTOCOL.md`. Run it with `/loop-tick`, use `/loop-tick dry-run` first, check on it with `/loop-status`, and run a cross-owner change with `/sprint`.

## Bands

| Band | Modules | Coverage |
| --- | --- | --- |
| **Core** | agent loop, LLM providers, tools, MCP manager | `agent-core` |
| **Core** | chat, sessions, streaming, compare, frontend shell | `chat-core` |
| **Core** | auth, owner scope, SSRF, tool policy, secrets, app/core platform, DB/migrations, Docker, test infra | `security-core` |
| **Core** | Cookbook, hwfit, local engine readers, GPU compose | `inference-core` |
| **Supporting** | email, contacts, calendar/CalDAV, notes, tasks, research, search, documents/RAG, memory/skills, gallery, speech, webhooks, CLIs, MCP servers, remaining static/js | `workspace-apps` (one shared owner) |
| **Optional** | `swift/`, `companion/`, `website/`, `integrations/`, packaging/launch scripts, `assets/`, `config/` | none (`human`) |
| **Human-only** | `specs/` (read-only by project rule), `.github/`, ROADMAP, SECURITY, THREAT_MODEL, LICENSE, fleet safety scripts | none |

## Roster: 14 agents (opus 2 · sonnet 8 · haiku 4)

| Agent | Tier | Why this tier |
| --- | --- | --- |
| orchestrator | opus | A wrong ticket wastes a whole tick of sonnet work. It is the only writer of QUEUE.md. |
| self-review | opus | Judges whether the fleet earns its cost, and edits the fleet itself. |
| agent-core | sonnet | Writes code. The most regression-prone module (48 + 33 recent fixes). Sprint lead. |
| chat-core | sonnet | Writes code: chat, streaming, frontend shell. Sprint lead. |
| security-core | sonnet | Writes code: boundaries and platform. Sprint lead. |
| inference-core | sonnet | Writes code: Cookbook, hwfit, local engines. Sprint lead. |
| workspace-apps | sonnet | Writes code across the supporting band. No `Agent` tool. |
| triage-reporter | sonnet | Turns logs and test output into ranked evidence, which needs reading, not just exit codes. |
| git-manager | sonnet | Reviews diffs against tickets before landing. |
| decision-broker | sonnet | Writes decisions a human can make in under a minute. |
| health-check | haiku | Settled by exit codes, including connectivity classification. |
| verification-gate | haiku | Runs `scripts/fleet_gate.py`; settled by exit codes. Holds no `Agent` tool and reports to nobody. |
| secrets-auditor | haiku | Pattern scan. |
| docs-keeper | haiku | Makes small factual corrections, verified by running the documented command. |

**Connectivity** is folded into `health-check`: is it offline, down, refusing, or not configured, for local engines and upstream. This saves a fifteenth agent.

**Escalation is one-way.** A cheap agent at a judgement call files to BACKLOG. Tiers are never lowered to save tokens. Only self-review lowers a tier, and only with evidence.

## Ownership

The source of truth is `.claude/agents/OWNERSHIP.txt`: ordered globs, first match wins, plus a `@source` rule that makes a test follow the module it is named after.

```
./venv/Scripts/python scripts/fleet_ownership.py check      # every file exactly one owner, no dead rules
./venv/Scripts/python scripts/fleet_ownership.py who <path>
./venv/Scripts/python scripts/fleet_ownership.py summary
```

At install (1,576 files): workspace-apps 708 · agent-core 301 · security-core 218 · human 136 · chat-core 113 · inference-core 93 · docs-keeper 4.

These are owned by one agent because everyone touches them:

| Files | Owner |
| --- | --- |
| `app.py`, `core/`, `src/constants.py`, test infrastructure | security-core |
| `static/style.css`, `index.html`, `app.js` | chat-core |

Other owners file tickets to them.

These fleet files are not covered by OWNERSHIP.txt, because `.claude/` is gitignored:

| Files | Owner |
| --- | --- |
| `QUEUE.md`, `SPRINTS.md` (open/close) | orchestrator |
| `BACKLOG.md` | anyone, append only |
| `reports/` | the named writer per section |
| `DECISIONS-PENDING.md` | decision-broker |
| agent files and `OWNERSHIP.txt` | self-review, within its limits |
| `PROTOCOL.md`, `settings.json`, `gate-baseline.txt` | human |

## Sprint mode

Only the four core owners hold `Agent`. In a sprint, the lead assigns file lists to roster workers, reviews the combined diff against one `done-when`, and returns one summary. The gates stay outside. One sprint at a time, and nesting stops at `main → lead → worker`.

## Safety

There are three layers: instructions (PROTOCOL plus each agent file), `.claude/settings.json` deny and ask rules, and a verified snapshot as step 0 of every tick. The settings rules are **defence in depth, not a sandbox**: they are prefix-matched and can be phrased around.

The snapshot covers:
- git state, pinned at `refs/loop-snapshots/<id>`
- untracked files
- a copy of `.claude/`
- SQLite online backups with an integrity check

Restore refuses the live data dir.

`.claude/` is gitignored in this repo, so the fleet's files are not under version control. Each snapshot copies them instead.
