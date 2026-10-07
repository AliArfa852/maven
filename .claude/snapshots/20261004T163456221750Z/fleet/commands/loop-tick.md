---
description: Run one tick of the Odysseus agent fleet loop (pass "dry-run" to triage and plan without dispatching)
argument-hint: "[dry-run]"
---

Run one tick of the fleet loop exactly as `.claude/loop/PROTOCOL.md` defines it. Read PROTOCOL.md first. Mode: `$ARGUMENTS` (empty = full tick; `dry-run` = steps 0–4 only).

1. **Tick number.** Read `.claude/loop/TICK`, add 1, and call the result `n`. Write it back only after step 0 succeeds.
2. **Step 0, snapshot.** Run `./venv/Scripts/python scripts/loop_snapshot.py create`. If the output is not `SNAPSHOT OK`, stop the tick and report the error. Do not continue.
3. **Steps 1–3.** Dispatch `health-check`, then `triage-reporter` and `secrets-auditor` in parallel. Pass each one `n` and the snapshot id. If health says `ABORT`, stop and report.
4. **Step 4.** Dispatch `orchestrator` with `n`.
   - **dry-run:** show the human the plan (`reports/_tick-<n>-plan.md`) and stop here. No branches, no edits.
5. **Step 5.** Follow the plan's dispatch order. For each ticket:
   1. `git-manager` branches.
   2. The owner agent works, briefed with its ticket block from QUEUE.md.
   3. `git-manager` commits.
   4. `verification-gate` judges.
   5. `git-manager` lands if GREEN, or the ticket is marked failed.

   Run at most 3 tickets concurrently, never two with the same owner, and never two that touch the same file. Update the ticket's `status:` via the orchestrator only. Workers report; they do not edit QUEUE.md.
6. **Steps 6–8.** Run `docs-keeper` for landed behaviour changes, `decision-broker` if anything needs the human, and `self-review` if `n % 10 == 0`.
7. **Step 9.** Write `reports/_tick-<n>-summary.md` and print it. Cover:
   - landed, failed and idle tickets
   - decisions pending
   - `fleet/*` branches awaiting human cleanup

**You are the main loop, not a worker.** Do not edit project code yourself during a tick; route everything through the roster. If a step's agent fails to produce its report, record that and continue only where PROTOCOL allows.
