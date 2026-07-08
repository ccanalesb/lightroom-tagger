# Context

A previous agent (a cheaper coding model) just implemented a task on this
branch. Inspect what it changed (changes may be uncommitted):

!`git status -s`

!`git --no-pager diff --stat`

The task description lives in `.sandcastle/prompt.md` on the host (not in this
sandbox). Review against the change's evident intent and the repo conventions
in `docs/architecture.md` / `CONTEXT-MAP.md`.

# Task

Act as a senior reviewer and review along two independent axes.

## Axis 1 — Spec (does it match what was asked?)

Judge the diff against the change's evident intent (and `.sandcastle/prompt.md`
if it is present in the sandbox). Flag:

1. Intended behaviour that is missing or only partial.
2. Behaviour added that was not asked for (scope creep / dead code).
3. Behaviour that looks implemented but is implemented wrong. Check edge cases.

## Axis 2 — Standards (does it follow this repo's conventions?)

Check the diff against the documented conventions in `docs/architecture.md` and
`CONTEXT-MAP.md` (package layout under `lightroom_tagger/`, module
boundary/size policy, existing patterns). Cite the doc + rule for each
violation.

Then scan for these code smells — judgement calls, not hard rules; a documented
repo convention overrides them, and skip anything tooling already enforces:

- Mysterious Name — name doesn't reveal intent.
- Duplicated Code — same shape in >1 place → extract.
- Feature Envy — method reaches into another object's data more than its own.
- Data Clumps — same fields keep travelling together → bundle into a type.
- Primitive Obsession — primitive/string standing in for a domain concept.
- Repeated Switches — same switch/if-cascade recurs → polymorphism/shared map.
- Shotgun Surgery — one logical change forces scattered edits.
- Divergent Change — one module edited for several unrelated reasons.
- Speculative Generality — abstraction/params for needs the spec doesn't have.
- Message Chains — long `a.b().c().d()` navigation.
- Middle Man — class/function that mostly just delegates onward.
- Refused Bequest — subclass ignores most of what it inherits.

## Tests

Ensure coverage is adequate and the suite passes (`python -m pytest -q`).

# Done

Fix any issues directly and keep fixes minimal. When the review is complete,
stage and commit ALL changes (including the implementer's work if still
uncommitted):

    git add -A && git commit -m "Review + fixes"

Then output <promise>COMPLETE</promise>.
