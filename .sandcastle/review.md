# Context

A previous agent (a cheaper coding model) just implemented a task on this
branch. Inspect what it changed (changes may be uncommitted):

!`git status -s`

!`git --no-pager diff --stat`

The task description lives in `.sandcastle/prompt.md` on the host (not in this
sandbox). Review against the change's evident intent and the repo conventions
in `docs/architecture.md` / `CONTEXT-MAP.md`.

# Task

Act as a senior reviewer:

1. Correctness: does it satisfy the intended change? Edge cases handled?
2. Conventions: matches the `lightroom_tagger/` layout, module boundary/size
   policy, and existing patterns.
3. Tests: adequate coverage, and they pass (`python -m pytest -q`).
4. No scope creep or dead code.

Fix any issues directly and keep fixes minimal.

# Done

When the review is complete and any fixes are made, stage and commit ALL
changes (including the implementer's work if still uncommitted):

    git add -A && git commit -m "Review + fixes"

Then output <promise>COMPLETE</promise>.
