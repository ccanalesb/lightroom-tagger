# Repository Reorganization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Consolidate duplicate code (root-level vs nested package) into a single, clean `lightroom_tagger` package with proper structure.

**Architecture:** Move all modules into the `lightroom_tagger/` package, delete root duplicates, restructure scripts as package entry points, move visualizer to `apps/`, and create pyproject.toml for modern Python packaging.

**Tech Stack:** Python 3.12, TinyDB, Flask (visualizer backend), React 19 (visualizer frontend), pip/pip install -e

---

## Prerequisites

**Branch:** `repo-reorganization`

---

## Phase 1: Clean Up Artifacts

### Task 1: Delete Old Worktree

**Files:**
- Delete: `.worktrees/feature-worktree/` (entire directory)

**Step 1: Remove worktree**
```bash
git worktree remove .worktrees/feature-worktree 2>/dev/null || true
rm -rf .worktrees/feature-worktree
```

**Step 2: Verify removal**
```bash
git worktree list
ls -la .worktrees/
```
Expected: `.worktrees/feature-worktree` should NOT appear

**Step 3: Commit**
```bash
git add -A
git commit -m "chore: remove old feature-worktree"
```

---

### Task 2: Remove Large HTML Report

**Files:**
- Delete: `subset_validation_report.html` (root level)

**Step 1: Delete file**
```bash
rm -f subset_validation_report.html
```

**Step 2: Add to .gitignore**
Add to `.gitignore`:
```
*_validation_report.html
```

**Step 3: Commit**
```bash
git add .gitignore
git commit -m "chore: remove large HTML report, add to gitignore"
```

---

## Phase 2: Package Consolidation - Core Module

### Task 3: Consolidate Config

**Files:**
- Modify: `lightroom_tagger/core/config.py`

**Step 1: Copy better root config to package**
```bash
cp core/config.py lightroom_tagger/core/config.py
```

**Step 2: Commit**
```bash
git add lightroom_tagger/core/config.py
git commit -m "chore: consolidate config - copy better root version to package"
```

---

### Task 4: Merge Database Modules

**Files:**
- Modify: `lightroom_tagger/core/database.py`

**Step 1: Append missing functions to package database.py**

Add these functions from root `core/database.py` to end of `lightroom_tagger/core/database.py`:
- `init_catalog_table()`
- `init_instagram_table()`
- `init_matches_table()`
- `store_catalog_image()`
- `store_instagram_image()`
- `store_match()`

**Step 2: Commit**
```bash
git add lightroom_tagger/core/database.py
git commit -m "feat: merge database modules - add Instagram/catalog/matches support"
```

---

### Task 5: Copy Missing Core Modules

**Files:**
- Create: `lightroom_tagger/core/analyzer.py`
- Create: `lightroom_tagger/core/matcher.py`
- Create: `lightroom_tagger/core/test_analyzer.py`
- Create: `lightroom_tagger/core/test_matcher.py`

**Step 1: Copy analyzer and matcher**
```bash
cp core/analyzer.py lightroom_tagger/core/analyzer.py
cp core/matcher.py lightroom_tagger/core/matcher.py
cp core/test_analyzer.py lightroom_tagger/core/test_analyzer.py
cp core/test_matcher.py lightroom_tagger/core/test_matcher.py
```

**Step 2: Update imports in analyzer.py**
Change `from core.config import load_config` to `from lightroom_tagger.core.config import load_config`

**Step 3: Update imports in matcher.py**
Change `from core.database import store_match` to `from lightroom_taster.core.database import store_match`

**Step 4: Update imports in test files**
Change imports from `core.` to `lightroom_tagger.core.`

**Step 5: Commit**
```bash
git add lightroom_tagger/core/analyzer.py lightroom_tagger/core/matcher.py
git add lightroom_tagger/core/test_analyzer.py lightroom_tagger/core/test_matcher.py
git commit -m "feat: add analyzer and matcher modules to package"
```

---

## Phase 3: Lightroom & Instagram Consolidation

### Task 6: Merge Lightroom Modules

**Files:**
- Modify: `lightroom_tagger/lightroom/writer.py`
- Create: `lightroom_tagger/lightroom/enricher.py`
- Create: `lightroom_tagger/lightroom/cleanup_wrong_links.py`

**Step 1: Copy writer.py (has bug fixes)**
```bash
cp lightroom/writer.py lightroom_tagger/lightroom/writer.py
```

**Step 2: Copy enricher.py**
```bash
cp lightroom/enricher.py lightroom_tagger/lightroom/enricher.py
```

**Step 3: Copy cleanup_wrong_links.py**
```bash
cp lightroom/cleanup_wrong_links.py lightroom_tagger/lightroom/cleanup_wrong_links.py
```

**Step 4: Update imports in enricher.py**
Change imports from `core.` to `lightroom_tagger.core.`

**Step 5: Commit**
```bash
git add lightroom_tagger/lightroom/writer.py lightroom_tagger/lightroom/enricher.py
git add lightroom_tagger/lightroom/cleanup_wrong_links.py
git commit -m "feat: merge lightroom modules - add enricher and cleanup tools"
```

---

### Task 7: Merge Instagram Modules

**Files:**
- Create: `lightroom_tagger/instagram/crawler.py`

**Step 1: Copy crawler.py**
```bash
cp instagram/crawler.py lightroom_tagger/instagram/crawler.py
```

**Step 2: Update imports in crawler.py**
Change imports from `core.` to `lightroom_tagger.core.`

**Step 3: Copy browser.py and scraper.py if newer**
```bash
cp instagram/browser.py lightroom_tagger/instagram/browser.py
cp instagram/scraper.py lightroom_tagger/instagram/scraper.py
```

**Step 4: Commit**
```bash
git add lightroom_tagger/instagram/
git commit -m "feat: merge instagram modules - add crawler and update browser/scraper"
```

---

## Phase 4: Restructure Scripts

### Task 8: Create Scripts Package

**Files:**
- Create: `lightroom_tagger/scripts/__init__.py`
- Create: `lightroom_tagger/scripts/analyze_instagram_images.py`
- Create: `lightroom_tagger/scripts/run_vision_matching.py`
- Create: `lightroom_tagger/scripts/generate_validation_report.py`
- Create: `lightroom_tagger/scripts/generate_subset_report.py`
- Create: `lightroom_tagger/scripts/test_subset_matching.py`

**Step 1: Create package init**
Create `lightroom_tagger/scripts/__init__.py`:
```python
"""Lightroom Tagger scripts package."""
```

**Step 2: Move and convert each script**
For each script:
1. Copy from `scripts/` to `lightroom_tagger/scripts/`
2. Remove `sys.path.insert()` hack
3. Change imports from `core.` to `lightroom_tagger.core.`
4. Wrap code in `main()` function

**Step 3: Commit**
```bash
git add lightroom_tagger/scripts/
git commit -m "feat: restructure scripts as package modules with entry points"
```

---

## Phase 5: Create pyproject.toml

### Task 9: Add Modern Python Packaging

**Files:**
- Create: `pyproject.toml`
- Create: `lightroom_tagger/py.typed`

**Step 1: Create pyproject.toml**
See full content in previous discussion - includes dependencies and entry points.

**Step 2: Create py.typed marker**
Create empty `lightroom_tagger/py.typed`

**Step 3: Test installation**
```bash
pip install -e .
lightroom-tagger --help
```

**Step 4: Commit**
```bash
git add pyproject.toml lightroom_tagger/py.typed
git commit -m "feat: add pyproject.toml with entry points and modern packaging"
```

---

## Phase 6: Move Visualizer

### Task 10: Restructure Visualizer

**Files:**
- Move: `backend/` → `apps/visualizer/backend/`
- Move: `frontend/` → `apps/visualizer/frontend/`

**Step 1: Create directory and move**
```bash
mkdir -p apps/visualizer
mv backend apps/visualizer/
mv frontend apps/visualizer/
```

**Step 2: Update backend imports if needed**

**Step 3: Commit**
```bash
git add apps/
git commit -m "chore: move visualizer to apps/visualizer/ directory"
```

---

## Phase 7: Delete Root Duplicates

### Task 11: Remove Root-Level Modules

**Files:**
- Delete: `core/`, `lightroom/`, `instagram/`, `scripts/`
- Delete: Root `__init__.py`, `__main__.py`

**Step 1: Delete all root duplicate directories**
```bash
rm -rf core/ lightroom/ instagram/ scripts/
rm -f __init__.py __main__.py
```

**Step 2: Test package still works**
```bash
python3 -c "from lightroom_tagger.core.database import init_database; print('OK')"
```

**Step 3: Commit**
```bash
git add -A
git commit -m "chore: remove root-level duplicate modules - all consolidated into package"
```

---

## Phase 8: Final Verification & Docs

### Task 12: Fix CLI Imports
Update any imports in `lightroom_tagger/core/cli.py` to use `lightroom_tagger.` prefix.

### Task 13: Run Tests
```bash
pip install -e ".[dev]"
pytest -v
```

### Task 14: Update README
Add installation instructions and usage examples with new entry points.

---

## Completion Checklist

- [ ] All modules consolidated into `lightroom_tagger/` package
- [ ] Root duplicates deleted
- [ ] Scripts have entry points in pyproject.toml
- [ ] Visualizer moved to `apps/visualizer/`
- [ ] pyproject.toml created
- [ ] Tests pass
- [ ] Entry points work: `lightroom-tagger --help`
- [ ] README updated

---

## Execution Options

1. **Subagent-Driven (this session)** - I execute task by task
2. **Parallel Session** - You open new session with executing-plans skill