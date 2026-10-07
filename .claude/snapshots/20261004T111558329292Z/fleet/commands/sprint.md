---
description: Run the active (or a named) cross-owner sprint of the Odysseus agent fleet under its core-domain lead
argument-hint: "[S-<n>]"
---

Run one sprint as `.claude/loop/PROTOCOL.md` § Sprint defines it. Target: `$ARGUMENTS`, or the single active sprint in `.claude/loop/SPRINTS.md`.

1. **Check the sprint.** It must have been opened by the orchestrator in `SPRINTS.md` and must name:
   - a lead (one of `agent-core`, `chat-core`, `security-core`, `inference-core`)
   - one shared `done-when` command
   - a per-worker file list

   If any of these is missing, or another sprint is active, stop and say so.
2. **Snapshot.** `./venv/Scripts/python scripts/loop_snapshot.py create` must print `SNAPSHOT OK`, or stop.
3. **Branch.** Dispatch `git-manager` to branch `fleet/S-<n>` from `dev`.
4. **Lead.** Dispatch the lead with the sprint block. The lead dispatches roster workers on their assigned files (never gates, never git-manager), reviews the combined diff, and returns one summary. Do not relay the workers' transcripts.
5. **Verify each file.** Run `python scripts/fleet_ownership.py who <file>` for every changed file. Each file must belong to the worker it was assigned to in `SPRINTS.md`; anything else fails the sprint.
6. **Commit and judge.** `git-manager` commits, then `verification-gate` judges the sprint branch with a full gate. Gates are outside the sprint.
7. **Land.** `git-manager` lands on GREEN. Otherwise the sprint is marked failed and goes to `decision-broker`.
8. **Close.** Ask the orchestrator to close the sprint in `SPRINTS.md` with the outcome.
