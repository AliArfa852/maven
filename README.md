<p align="center">
  <img src="static/brand/maven-wordmark.svg" alt="Maven" width="238">
</p>

<p align="center">
  A self-hosted AI workspace for chat, agents, research, documents, email, notes, calendar, and local model workflows.
</p>

<p align="center">
  <a href="#quick-start">Quick Start</a> ·
  <a href="website/getting-started.md">Getting Started</a> ·
  <a href="website/setup.md">Setup Guide</a> ·
  <a href="CONTRIBUTING.md">Contributing</a> ·
  <a href="ROADMAP.md">Roadmap</a>
</p>

<p align="center">
  <img src="assets/branding/odysseus-browser.jpg" alt="Maven interface">
</p>

---

## Quick Start

> `dev` is the default branch and gets the newest changes first.

```bash
git clone https://github.com/AliArfa852/maven.git
cd maven
cp .env.example .env      # Windows: copy .env.example .env
docker compose up -d --build
```

Open `http://localhost:7000` when the containers are healthy and log in as `admin`. The password is printed once in `docker logs maven`; to choose it yourself, set `MAVEN_AI_ADMIN_PASSWORD` in `.env` before the first start. `.env.example` runs as-is for local testing and documents every other setting.

The app container is named `maven` (`docker logs maven`, `docker exec -it maven sh`) and the compose service is `maven` (`docker compose logs maven`).

**Upgrading an older install** (its compose service was renamed from `odysseus` to `maven`): run `docker compose up -d --build --remove-orphans` once, so the old container is removed and stops holding port 7000. Your data stays in `./data`.

The compose files use the image `ghcr.io/aliarfa852/maven` and build locally when it can't be pulled, so this also works on hosts without a published image, e.g. as a [Portainer](https://www.portainer.io/) stack.

**Production deployments:** pin an immutable tag instead of `:latest`. `:latest` and bare `:X.Y.Z` tags move on every push to `main`, but `:X.Y.Z-<sha>` (e.g. `1.0.2-7c8070f`) always refers to one specific build:

```bash
MAVEN_AI_IMAGE=ghcr.io/aliarfa852/maven:1.0.2-7c8070f docker compose up -d
```

Settings use `MAVEN_AI_*` names; the old `ODYSSEUS_*` names still work, and the new name wins when both are set.

**New to Maven?** The [getting started guide](website/getting-started.md) walks through a first run and every feature: models, agents, Office files and charts, roles and the Admin Console, compliance review, the audit log, PostgreSQL and backups.

Native installs, GPU notes, Windows/macOS instructions, HTTPS, and configuration live in the [setup guide](website/setup.md).

## Features

- **Chat + Agents** — local/API models, tools, MCP, files, shell, skills, and memory.
- **Cookbook** — hardware-aware model recommendations, downloads, and serving.
- **Deep Research** — multi-step web research with source reading and report generation.
- **Compare** — blind side-by-side model testing and synthesis.
- **Documents** — writing-first editor with AI edits, suggestions, Markdown, HTML, CSV, and syntax highlighting.
- **Email** — IMAP/SMTP inbox with triage, tags, summaries, reminders, and reply drafts.
- **Notes, Tasks + Calendar** — reminders, todos, scheduled agent tasks, and CalDAV sync.
- **Office files** — read Excel, Word, PowerPoint and PDF; create xlsx, docx, pptx, pdf and csv files with bar, line and pie charts.
- **Roles + Admin Console** — multiple roles per person, clearance levels, view-only access for managers.
- **Compliance + audit** — rule-based flagging of risky messages for Compliance Officers, and a tamper-evident audit log.
- **Extras** — gallery/image editor, themes, uploads, web search, presets, sessions, and 2FA.

## Based on Odysseus

Maven is a modified version of [Odysseus](https://github.com/odysseus-dev/odysseus), a self-hosted AI workspace by the Odysseus contributors. See [NOTICE.md](NOTICE.md) for details on the modifications and [ACKNOWLEDGMENTS.md](ACKNOWLEDGMENTS.md) for licensing information.

## Contributing

Help is welcome. The best entry points are fresh-install testing, provider setup bugs, mobile/editor polish, docs, and small focused refactors. See [CONTRIBUTING.md](CONTRIBUTING.md) and [ROADMAP.md](ROADMAP.md).

## Security

Maven is a self-hosted workspace with powerful local tools. Keep auth enabled, keep private data out of Git, and do not expose raw model/service ports publicly.

- Keep `AUTH_ENABLED=true` for any network-accessible deployment.
- Keep `LOCALHOST_BYPASS=false` outside local development.

Deployment details are in the [setup guide](website/setup.md#security-notes).

## License

AGPL-3.0-or-later -- see [LICENSE](LICENSE) and [ACKNOWLEDGMENTS.md](ACKNOWLEDGMENTS.md).
