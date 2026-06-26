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
    ? {
        prompt:
          "You are a senior reviewer. A cheaper coding model just implemented " +
          `this task:\n\n${task}\n\nInspect the changes (run \`git status -s\` and ` +
          "`git --no-pager diff`), check correctness, repo conventions, and tests. " +
          `Fix any issues and run the test suite. ${commitNote}`,
      }
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
