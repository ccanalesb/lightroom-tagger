# Issue Tracker

Issues are tracked as local markdown files under `.scratch/` in this repo.

## Workflow

- Create issues as `.scratch/<feature>/issue.md` or `.scratch/<slug>.md`
- Use YAML frontmatter for status, title, and labels
- No external CLI required — all file operations are local

## Frontmatter schema

```yaml
---
title: Short issue title
status: needs-triage   # one of the canonical triage labels
labels: []
created: YYYY-MM-DD
---
```

## Conventions

- One directory per feature/bug under `.scratch/`
- `issue.md` is the primary file; supporting files (screenshots, notes) go in the same directory
- Closed/resolved issues can be moved to `.scratch/_archive/`
