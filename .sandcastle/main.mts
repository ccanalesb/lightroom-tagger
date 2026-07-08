import { readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { createSandbox, cursor } from "@ai-hero/sandcastle";
import { docker } from "@ai-hero/sandcastle/sandboxes/docker";

// Multi-model pipeline: cheap/fast model does the bulk coding, the smart model
// does a review/fix pass. Run locally with: npx tsx .sandcastle/main.mts
//
// In CI (GitHub Actions), the task comes from the labeled issue via env vars:
//   SANDCASTLE_TASK   - the issue title + body (the work to do)
//   SANDCASTLE_BRANCH - the branch to produce (e.g. sandcastle/issue-42)
// When SANDCASTLE_TASK is unset (local runs), it falls back to the prompt files.

const branch = process.env.SANDCASTLE_BRANCH ?? "sandcastle/run";
const task = process.env.SANDCASTLE_TASK?.trim();

const commitNote =
  "When done and tests pass, stage and commit ALL changes " +
  '(`git add -A && git commit -m "..."`), then output <promise>COMPLETE</promise>.';

// Two-axis review (ported from the code-review skill): Spec = does the diff
// match what was asked; Standards = does it follow repo conventions + the
// Fowler smell baseline. The reviewer FIXES issues, it does not just report.
const reviewGuidance = `You are a senior reviewer. A cheaper coding model just implemented the task (shown below) on this branch. First inspect what it changed (may be uncommitted):

- \`git status -s\`
- \`git --no-pager diff\`

Review along two independent axes.

## Axis 1 — Spec (does it match what was asked?)
Compare the diff against the task text. Quote the relevant task line for each finding:
(a) requirements asked for but missing or only partial;
(b) behaviour added that the task did NOT ask for (scope creep / dead code);
(c) requirements that look implemented but are implemented wrong.

## Axis 2 — Standards (does it follow this repo's conventions?)
Check the diff against the documented conventions in \`docs/architecture.md\` and \`CONTEXT-MAP.md\` (package layout under \`lightroom_tagger/\`, module boundary/size policy, existing patterns). Cite the doc + rule for each violation.
Then scan for these code smells — judgement calls, not hard rules; a documented repo convention overrides them, and skip anything tooling already enforces:
- Mysterious Name — name doesn't reveal intent.
- Duplicated Code — same shape in >1 place → extract.
- Feature Envy — method reaches into another object's data more than its own.
- Data Clumps — same fields keep travelling together → bundle into a type.
- Primitive Obsession — primitive/string standing in for a domain concept.
- Repeated Switches — same switch/if-cascade recurs → polymorphism/shared map.
- Shotgun Surgery — one logical change forces scattered edits.
- Divergent Change — one module edited for several unrelated reasons.
- Speculative Generality — abstraction/params for needs the spec doesn't have.
- Message Chains — long a.b().c().d() navigation.
- Middle Man — class/function that mostly just delegates onward.
- Refused Bequest — subclass ignores most of what it inherits.

## Tests
Ensure coverage is adequate and the suite passes: \`python -m pytest -q\`.

## Done
Fix the issues you find directly and keep fixes minimal. Then stage and commit ALL changes (including the implementer's work if still uncommitted):
\`git add -A && git commit -m "Review + fixes"\`
Then output <promise>COMPLETE</promise>.`;

await using sandbox = await createSandbox({
  branch,
  sandbox: docker(),
  // On sandbox start: give git an identity (so agents can commit) and install
  // the editable project into the pre-baked venv (deps already present, so this
  // is fast). Both run steps can then just `python -m pytest`.
  hooks: {
    sandbox: {
      onSandboxReady: [
        { command: "git config user.email agent@sandcastle.local" },
        { command: "git config user.name 'Sandcastle Agent'" },
        { command: "uv pip install -e . --no-deps" },
      ],
    },
  },
});

// Step 1 — implement with Composer 2.5 (cheap, fast coder)
await sandbox.run({
  agent: cursor("composer-2.5"),
  ...(task
    ? { prompt: `# Task\n\n${task}\n\n# Done\n\n${commitNote}` }
    : { promptFile: "./.sandcastle/prompt.md" }),
  maxIterations: 5,
});

// Step 2 — review & fix with Opus 4.8 (smart, used sparingly) on the same branch
await sandbox.run({
  agent: cursor("claude-opus-4-8-medium"),
  ...(task
    ? { prompt: `${reviewGuidance}\n\n# Task the implementer worked from\n\n${task}` }
    : { promptFile: "./.sandcastle/review.md" }),
});

// Step 3 — write the PR description with the cheap model. The agent inspects the
// branch itself and writes PR_BODY.md in the worktree; we relay it to the repo
// root so CI can pass `gh pr create --body-file .sandcastle/PR_BODY.md`.
await sandbox.run({
  agent: cursor("composer-2.5"),
  prompt:
    "Inspect this branch's changes (`git --no-pager log` and `git --no-pager diff`), " +
    "then write a concise GitHub pull request description as Markdown to a file named " +
    "PR_BODY.md in the repo root: a one-line summary, a short bullet list of what " +
    "changed and why, and any testing notes. Do not reference an issue number and do " +
    "not commit the file. When done, output <promise>COMPLETE</promise>.",
});

try {
  const prBody = await readFile(join(sandbox.worktreePath, "PR_BODY.md"), "utf8");
  await writeFile("./.sandcastle/PR_BODY.md", prBody, "utf8");
  console.log("wrote .sandcastle/PR_BODY.md");
} catch {
  console.log("no PR_BODY.md produced; CI will use its fallback body");
}

console.log("branch:", branch);
