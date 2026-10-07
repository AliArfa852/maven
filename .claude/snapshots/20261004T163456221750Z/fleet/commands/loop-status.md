---
description: Show the Odysseus agent fleet's current state (tick, queue, sprint, pending decisions, last summary, snapshots)
---

Read-only. Do not dispatch agents or edit anything. Report concisely:

1. The current tick (`.claude/loop/TICK`), and the latest `reports/_tick-*-summary.md` (its headline lines only).
2. Tickets in `.claude/loop/QUEUE.md`, grouped by `status:`.
3. Any active sprint in `SPRINTS.md`.
4. Every item in `DECISIONS-PENDING.md`, with its one-line question. Show these first if any are P0.
5. The count of BACKLOG items added since the last plan.
6. The last 3 lines of `./venv/Scripts/python scripts/loop_snapshot.py list`.
7. The result line of `python scripts/fleet_ownership.py check`.
8. `git branch --list "fleet/*" --merged dev`, as candidates for the human to clean up.
