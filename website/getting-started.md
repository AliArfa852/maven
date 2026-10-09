---
layout: default
---

# Getting Started with Maven

This guide walks you through a first run and then tours the main features:
chat and agents, working with Office files, the Admin Console, roles,
compliance review and the audit log. It covers what you *do*; the
[setup guide](setup.md) covers installation options in depth.

- [1. Start Maven](#1-start-maven)
- [2. Sign in and secure the admin account](#2-sign-in-and-secure-the-admin-account)
- [3. Connect a model](#3-connect-a-model)
- [4. Chat and agents](#4-chat-and-agents)
- [5. Read Excel, Word, PowerPoint and PDF files](#5-read-excel-word-powerpoint-and-pdf-files)
- [6. Create files and charts](#6-create-files-and-charts)
- [7. Find old conversations](#7-find-old-conversations)
- [8. Add people and give them roles](#8-add-people-and-give-them-roles)
- [9. Compliance: flagged conversations](#9-compliance-flagged-conversations)
- [10. The audit log](#10-the-audit-log)
- [11. Use PostgreSQL for a team install](#11-use-postgresql-for-a-team-install)
- [12. Back up and restore](#12-back-up-and-restore)
- [13. Everything else](#13-everything-else)
- [Settings reference](#settings-reference)
- [Troubleshooting](#troubleshooting)

---

## 1. Start Maven

You need Docker (Docker Desktop on Windows and macOS).

```bash
git clone https://github.com/AliArfa852/maven.git
cd maven
cp .env.example .env      # Windows: copy .env.example .env
docker compose up -d --build
```

`.env.example` is ready to run as-is for local testing. Every line in it is
commented, so it doubles as the settings reference.

When the container is healthy, open **http://localhost:7000**.

> Want a local model in the same stack? Add the Ollama overlay:
> `docker compose -f docker-compose.yml -f docker-compose.ollama.yml up -d --build`.
> GPU overlays live in `docker/gpu.nvidia.yml` and `docker/gpu.amd.yml`; see the
> [setup guide](setup.md).

Running without Docker (Linux, macOS, Windows) is covered in the
[setup guide](setup.md#native-linux--macos).

## 2. Sign in and secure the admin account

Maven creates one account on first start: **`admin`**, with the Admin role.

- **Where's the password?** It is printed once in the logs:
  `docker logs maven`. To choose it yourself, set
  `MAVEN_AI_ADMIN_PASSWORD` in `.env` **before the first start**.
- **Turn on 2FA** for the admin account under **Settings → Account**.
- The login page shows a short notice that messages may be checked for
  security risks (see [§9](#9-compliance-flagged-conversations)). You can reword it.

**Locked out?** Recover from the command line:

```bash
# Docker
docker exec -it maven python scripts/maven-users list
docker exec -it maven python scripts/maven-users reset-password admin --generate
# Native install (from the repo folder, inside your venv)
python scripts/maven-users check            # finds broken accounts, exits 1 if any
python scripts/maven-users make-admin alice # give someone the Admin role
```

## 3. Connect a model

Maven works with local models (Ollama, LM Studio, llama.cpp, vLLM and other
OpenAI-compatible servers) and with API providers.

- **Ollama on the same computer** is found automatically. In Docker, start
  Ollama with `OLLAMA_HOST=0.0.0.0:11434` so the container can reach it.
- **Easiest (admins):** open the **Admin Console → Models & APIs**
  (`/admin-console#models`) and click **Add a model**. Pick **On my computer
  or network** (presets for Ollama, LM Studio, llama.cpp and vLLM) or
  **Cloud API** (OpenAI, Anthropic, Gemini, OpenRouter, Mistral, DeepSeek,
  Groq and more), paste the API key if it needs one, **Test connection**, then
  **Save**. **Find local model servers** scans this computer and the hosts in
  `LLM_HOST` / `LLM_HOSTS` for running servers. `localhost` works even when
  Maven runs in Docker: Maven routes it to your computer.
- The same tab sets the **default chat model** and the **utility model**
  (used for titles and summaries), optionally for every user.
- Sign-in based providers (GitHub Copilot, ChatGPT subscription) are added
  in the app under **Settings → Added Models**, which also has every
  advanced option.
- **Cookbook** (in the sidebar) recommends models that fit your hardware and
  can download and serve them for you.

Pick the model for a chat from the model picker above the message box.

## 4. Chat and agents

- **Chat** answers directly.
- **Agent** mode lets the model use tools: web search, documents, notes,
  calendar, email, memory, file creation and more. Tools that change things
  ask for your approval first (see [§6](#6-create-files-and-charts)).
- **Deep Research** runs multi-step web research and writes a sourced report.
- **Compare** runs the same prompt on several models side by side, blind.
- **Memory** keeps facts you want Maven to remember about you. Only you see
  your memories.

## 5. Read Excel, Word, PowerPoint and PDF files

Attach files to a message (paperclip, or drag and drop) and ask about them:
"summarise this contract", "which region grew fastest in this sheet?",
"list the action items in these slides".

| File | What Maven reads |
| --- | --- |
| Excel `.xlsx` | Every sheet as a table (first 2,000 rows per sheet) |
| Word `.docx` | Text, headings and tables |
| PowerPoint `.pptx` | Each slide's title, text, tables and speaker notes |
| PDF | Text (form filling needs the optional extras in the setup guide) |
| CSV, Markdown, text, code | As is |

**Numbers from a spreadsheet.** In **Agent** mode, questions like "total
revenue by region", "spend per month", "average deal size for Q3" or "the ten
biggest invoices" are answered by calculating them from the whole sheet, not
estimated from the part the model can see. Maven can group by any column,
group dates by month, quarter or year, filter rows, and pick the top N. It
reads numbers like `1,234.50`, `1.234,50`, `$1,200`, `(500)` and `12%`
correctly. Ask for a chart of the result and it goes straight into a file
([§6](#6-create-files-and-charts)). Only your own uploads can be read.

**Long files.** Only the first part of a long file fits in the message the model
reads, but the full text is saved as a document in the chat. In **Agent**
mode, ask about any part of it ("what does the contract say about
termination?") and Maven searches all of this chat's files for the right
passages, citing the document. It never searches other chats or other
people's files.

Uploads belong to the person who uploaded them. Other users cannot open them.

## 6. Create files and charts

In **Agent** mode, ask for a file and Maven builds it:

- "Put this table in an Excel spreadsheet"
- "Make a 5-slide PowerPoint deck from our discussion"
- "Write this up as a Word document" / "...as a PDF report"
- "Export the results as CSV"

You get a download link in the chat. Supported formats: **xlsx, docx, pptx,
pdf, csv**.

**Charts.** Ask for one: "add a bar chart of revenue by region", "show the
trend as a line chart", "a pie chart of the cost split". Kinds: bar,
horizontal bar, line and pie.

| Format | Chart |
| --- | --- |
| Excel | A real Excel chart drawn from the sheet's own columns, so you can edit it |
| PowerPoint | A real, editable PowerPoint chart on its own slide |
| PDF | A vector chart that stays sharp when zoomed |
| Word | An image of the chart (Word files made by Maven can't hold live charts) |

Charts use a colour-blind-safe palette. Missing values are left as gaps
rather than drawn as zero.

**Why does it ask "Allow this task to continue?"** Creating a file saves data,
and Maven asks before any tool that saves or changes data when outside
content is in play (MCP tool descriptions count, and the built-in browser is
one). Choose **Allow for this chat session** to be asked once per chat.

**Safety built in:** spreadsheet text that starts with `=`, `+`, `-` or `@` is
stored as text, so a file can't run a formula when someone opens it. Size
limits stop a runaway request from building a huge file.

Developers can also call the same builder directly: `POST /api/files/create`
with `{"format": "xlsx", "filename": "...", "spec": {...}}`
(`GET /api/files/formats` lists the formats).

## 7. Find old conversations

Open conversation search (the **Search conversations…** box) and type. On SQLite it uses SQLite full-text
search; on PostgreSQL it uses a full-text index with ranked results. Words
can appear in any order, and `"quoted phrases"` match exactly. You only ever
search your own chats.

## 8. Add people and give them roles

Admins add accounts under **Settings → Users**, where **Open signup** lets
people register themselves. Then open the **Admin Console**: **Settings → Account → Admin
Console**, or go straight to **http://localhost:7000/admin-console**.

The console has tabs, and each person sees only the ones their roles allow:

| Tab | What it does | Who sees it |
| --- | --- | --- |
| Overview | People, model connections, open flags, audit-log health, and next steps | Everyone with console access |
| Users & roles | Roles and clearance for each person | Admin (change), Managers and Compliance (view) |
| Models & APIs | Connect local model servers and cloud APIs, switch them on and off, default models | Admin |
| Settings | Self sign-up, features on or off, web search provider and keys, assistant limits, public address | Admin |
| Compliance | Flagged conversations and flagging rules | Compliance Officers |
| Audit log | Who did what, with the integrity check | Admin, Managers, Compliance |

Saved API keys are never shown again: leave a key box empty to keep the
saved key, or type a new one to replace it.

A person can hold **several roles**. Everyone holds Basic.

| Role | Default clearance | Admin Console |
| --- | --- | --- |
| Basic | Internal | no access |
| Advanced | Internal | no access |
| Manager | Confidential | view only |
| General Manager | Restricted | view only |
| Compliance Officer | Restricted | view only, plus flag review and flagging rules |
| Admin | Internal | view and change users, roles and clearance |

- **Clearance** levels, lowest to highest: Public, Internal, Confidential,
  Restricted. A person's clearance is the highest default among their roles,
  unless an Admin sets it by hand in the console ("set by admin").
- **Separation of duties:** Admins run the system but do **not** review
  flagged conversations; that belongs to Compliance Officers. Managers can
  look at the console but change nothing.
- Every change is recorded in the [audit log](#10-the-audit-log).

> **Coming next:** clearance labels on documents and knowledge, so retrieval
> only returns what a person's clearance allows. Today, roles control the
> Admin Console; each user's chats, files, notes and memories are already
> private to them.

## 9. Compliance: flagged conversations

Maven checks each message people send against simple, explainable rules and
flags matches for a **Compliance Officer** to review. It never blocks or
changes the message.

What gets flagged:
- **Secrets pasted into chat:** private keys, AWS keys, GitHub and Slack
  tokens, API keys, `password=...`
- **Prompt injection:** "ignore previous instructions", "reveal your system prompt"
- **Bulk export of sensitive data:** "export all customer emails"
- **Other people's data:** "show me other employees' salaries"
- **Personal data:** a valid card number, ten or more email addresses in one message
- **Your own watch list:** project code names or other terms you choose

**Reviewing.** In the Admin Console, **Flagged conversations** lists each flag
with a short excerpt (secrets, card numbers and email addresses masked), not
the whole conversation. Choose **Dismiss**, **Warn** or **Escalate** and add a
note. Who decided and when is recorded.

**Tuning.** Under **Flagging rules**, Compliance Officers can add watch-list
keywords (one per line) and switch off a rule that flags too much ordinary
work. Changes apply to the next message.

**Settings** (in `.env`):

| Setting | Default | Meaning |
| --- | --- | --- |
| `MAVEN_AI_FLAGGING` | `1` | `0` turns flagging (and the login notice) off |
| `MAVEN_AI_FLAG_KEYWORDS` | empty | Extra watch-list terms, comma-separated |
| `MAVEN_AI_MONITORING_NOTICE` | built-in text | Your own wording for the login-page notice |
| `MAVEN_AI_FLAG_RETENTION_DAYS` | `180` | Decided flags are deleted after this many days; `0` keeps them. Open flags are never deleted. |

Telling employees their use is monitored is a legal requirement in many
places. Check the notice wording with your legal or HR team.

## 10. The audit log

The Admin Console's **Audit log** shows security-relevant actions: who, what,
when, from which IP address, and whether it worked. It never stores message
content, passwords or request bodies.

Recorded:
- sign-ins: succeeded, failed, rate-limited, wrong 2FA code
- role changes (before → after) and clearance changes
- every change made through the account, user, compliance, admin, API-token,
  webhook, model-endpoint, MCP, vault and import routes
- full data exports

Filter by type and outcome, and page back with **Older entries**.

**Check integrity.** Each entry is chained to the one before it with a
SHA-256 hash, so editing or deleting a past entry breaks the chain from that
point. The button tells you whether the chain is intact, or the first entry
that doesn't fit. It cannot detect the *newest* entries being deleted, so if
that matters, copy the "latest hash" it shows somewhere outside Maven from
time to time.

Admins, Managers, General Managers and Compliance Officers can read the log.
Nobody can edit it through Maven.

## 11. Use PostgreSQL for a team install

SQLite is fine for one person or a small team. For many users, use
PostgreSQL:

1. In `.env`, set `MAVEN_AI_POSTGRES_PASSWORD` to a long random value made
   of letters and digits.
2. Start with the overlay:
   ```bash
   docker compose -f docker-compose.yml -f docker/postgres.yml up -d --build
   ```
   (or put `COMPOSE_FILE=docker-compose.yml:docker/postgres.yml` in `.env`;
   on Windows separate the files with `;`).

The database is reachable only from inside the stack, with no port on the host.

**Moving an existing install:** stop the app, start only the database
(`docker compose -f docker-compose.yml -f docker/postgres.yml up -d postgres`),
then copy your data across:

```bash
docker compose -f docker-compose.yml -f docker/postgres.yml run --rm maven python scripts/maven-db copy-to-postgres
```

It refuses to copy into a database that already holds data, and leaves the
SQLite file untouched as a fallback. `python scripts/maven-db info` shows
which database Maven is using.

## 12. Back up and restore

```bash
python scripts/maven-backup snapshot          # writes backups/<timestamp>.tar.gz
python scripts/maven-backup list
python scripts/maven-backup verify backups/<file>.tar.gz
python scripts/maven-backup restore backups/<file>.tar.gz --yes
```

In Docker, run them with `docker exec -it maven python scripts/maven-backup ...`.

- A snapshot contains your encryption key and secrets: store it like a password.
- On PostgreSQL, the snapshot includes an export of every table. After a
  restore, load it into an **empty** database with
  `python scripts/maven-db load-export data/_db_export`.
- Restore keeps your previous data folder as `<name>.before-restore-<time>`.

Details: [Backup & Restore](backup-restore.md).

## 13. Everything else

- **Documents:** a writing-first editor with AI edits and suggestions.
- **Email:** IMAP/SMTP inbox with triage, summaries and reply drafts
  ([Outlook / Office 365](email-outlook.md)).
- **Notes, tasks and calendar:** reminders, todos, scheduled agent tasks, CalDAV sync.
- **Gallery, themes, presets, web search, skills, MCP servers.**

## Settings reference

Every setting is documented in `.env.example`. Maven settings use the
`MAVEN_AI_` prefix. The old `ODYSSEUS_` names still work, and the new name
wins when both are set.

Settings you are most likely to change:

| Setting | What it does |
| --- | --- |
| `AUTH_ENABLED` | Keep `true` for anything reachable over a network |
| `LOCALHOST_BYPASS` | Keep `false` outside local development |
| `MAVEN_AI_ADMIN_USER` / `MAVEN_AI_ADMIN_PASSWORD` | The first admin account (first start only) |
| `APP_BIND` / `APP_PORT` | Where Maven listens (default port 7000) |
| `ALLOWED_ORIGINS` | Browser origins allowed to call the API |
| `MAVEN_AI_DATA_DIR` | Where Maven keeps its data (default `./data`) |
| `DATABASE_URL` | Set automatically by the PostgreSQL overlay |
| `MAVEN_AI_FLAGGING` and friends | See [§9](#9-compliance-flagged-conversations) |

## Troubleshooting

| Problem | Fix |
| --- | --- |
| Port 7000 busy after upgrading from Odysseus | `docker compose up -d --build --remove-orphans` once |
| No admin password in the logs | It is printed only on the very first start. Use `maven-users reset-password admin --generate`. |
| Login fails with a server error | `python scripts/maven-users check` finds broken accounts; reset the password |
| Docker can't reach Ollama on the host | Start Ollama with `OLLAMA_HOST=0.0.0.0:11434` |
| Windows: model download fails with a symlink or `WinError` | Keep the repo outside OneDrive, or let Maven switch the cache to plain copies (it does this automatically inside OneDrive) |
| "Allow this task to continue?" on every new chat | Expected: see [§6](#6-create-files-and-charts) |
| The assistant answers instead of making the file | Use **Agent** mode, and name the format ("as an Excel file") |

More fixes: [setup guide troubleshooting](setup.md#troubleshooting--advanced-setup).
