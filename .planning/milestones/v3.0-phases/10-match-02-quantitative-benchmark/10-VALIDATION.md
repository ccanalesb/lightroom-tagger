---
phase: 10
slug: match-02-quantitative-benchmark
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-01
---

# Phase 10 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (backend) |
| **Config file** | `pyproject.toml` (existing) |
| **Quick run command** | `python -m lightroom_tagger.scripts.benchmark_clip_recall --help` |
| **Full suite command** | `pytest lightroom_tagger/ -x -q` |
| **Estimated runtime** | ~30 seconds (pytest sweep) |

---

## Sampling Rate

- **After every task commit:** Run `python -m lightroom_tagger.scripts.benchmark_clip_recall --help` (verifies the script is importable and argparse is wired)
- **After every plan wave:** Run `pytest lightroom_tagger/ -x -q`
- **Before `/gsd-verify-work`:** Full suite must be green; `10-RECALL.md` and `10-recall-data.csv` must exist in phase dir
- **Max feedback latency:** ~30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 10-01-01 | 01 | 1 | MATCH-02 | — | Read-only — no DB writes | import | `python -c "from lightroom_tagger.scripts.benchmark_clip_recall import main"` | ❌ W0 | ⬜ pending |
| 10-01-02 | 01 | 1 | MATCH-02 | — | Correct argparse help | cli | `python -m lightroom_tagger.scripts.benchmark_clip_recall --help` | ❌ W0 | ⬜ pending |
| 10-02-01 | 02 | 2 | MATCH-02 | — | Report file exists | manual | `test -f .planning/phases/10-match-02-quantitative-benchmark/10-RECALL.md` | manual | ⬜ pending |
| 10-02-02 | 02 | 2 | MATCH-02 | — | CSV file exists with required columns | manual | `head -1 .planning/phases/10-match-02-quantitative-benchmark/10-recall-data.csv \| grep shortlist_includes_validated` | manual | ⬜ pending |
| 10-03-01 | 03 | 3 | MATCH-02 | — | REQUIREMENTS.md no longer contains ≥10× | grep | `rg "≥10×" .planning/REQUIREMENTS.md` (must return no matches) | ✅ | ⬜ pending |
| 10-03-02 | 03 | 3 | MATCH-02 | — | Traceability table row says Complete | grep | `rg "MATCH-02.*Complete" .planning/REQUIREMENTS.md` | ✅ | ⬜ pending |
| 10-04-01 | 04 | 3 | — | — | Todo moved to done/ | shell | `test -f .planning/todos/done/benchmark-embedding-recall.md` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `lightroom_tagger/scripts/benchmark_clip_recall.py` — script file created (importable)
- [ ] Existing pytest infrastructure covers backend — no new conftest needed

*Existing infrastructure covers all phase requirements. Wave 0 is just the script file creation.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `10-RECALL.md` contains recall %, miss table, funnel table | MATCH-02 | Requires live DB with validated pairs + IG embeddings | Run `python -m lightroom_tagger.scripts.benchmark_clip_recall --db library.db --out-dir .planning/phases/10-match-02-quantitative-benchmark/` and inspect output |
| `10-recall-data.csv` has one row per validated pair with correct status taxonomy | MATCH-02 | Requires live DB | Check CSV columns: `insta_key, validated_catalog_key, date_window_size, candidates_after_filters, shortlist_size, shortlist_includes_validated, status` |
| IG embeddings populated before recall run | MATCH-02 (D-04) | Job system prerequisite | Run `batch_embed_image` with `image_type='catalog_and_instagram'` via UI or API, wait for completion, then run benchmark |

---

## Validation Architecture Notes (from Research)

**Verifiable from artifacts alone:**
- Raw funnel counts: `total_validated`, `embedded`, `skipped_no_embedding`, `filtered_out`, `hits`, `misses`
- Per-pair `status` ∈ `{hit, miss, filtered_out, skipped_no_embedding}` with all D-12 CSV columns
- Miss list for operator review

**Requires executing the script:**
- That candidate construction actually used `find_candidates_by_date(days_before=90)` + `get_rejected_pairs` + `catalog_key_is_primary_grid_row` + `top_k=50`
- That DB snapshot had CLIP rows for IG keys claimed as "embedded"

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
