# Issue Tracker

Issues are tracked in GitHub Issues for this repo: `ccanalesb/lightroom-tagger`.

## Workflow

- Use the `gh` CLI for all issue operations
- Create: `gh issue create --title "..." --body "..."`
- List: `gh issue list`
- View: `gh issue view <number>`
- Close: `gh issue close <number>`

## Labels

Apply triage labels via `gh issue edit <number> --add-label "<label>"`.

See `docs/agents/triage-labels.md` for the canonical label vocabulary.

## Conventions

- One issue per bug or feature
- Link PRs to issues with `Closes #<number>` in the PR body
- Use issue comments for status updates rather than editing the body
