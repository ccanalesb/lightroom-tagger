# Instagram OpenCLI Migration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the current Instagram `agent-browser` scraping path with an OpenCLI-backed ingestion flow that runs in WSL, preserves persisted metadata and downloaded media, and stops after a validated first POC for safeguard review.

**Architecture:** Introduce a single Python Instagram ingestion service that shells out to OpenCLI for structured metadata extraction and optional media download, then normalizes and persists canonical records in the existing app. Use the current working `agent-browser` scraper as the parity baseline, preserve stable local media paths, add duplicate prevention and stop-signal heuristics, and explicitly pause after the first real POC before broader cutover.

**Tech Stack:** Python, TinyDB, OpenCLI (`jackwener/opencli`), Node.js, Chrome Browser Bridge extension, pytest

---

## Background

- The current working baseline is the browser scraper in `lightroom_tagger/instagram/browser.py`, which already handled login/session reuse, post discovery, carousel extraction, media download, and screenshot fallback.
- The Instagram flow is currently split across:
  - `lightroom_tagger/instagram/browser.py`
  - `lightroom_tagger/instagram/scraper.py`
  - `lightroom_tagger/instagram/crawler.py`
  - `lightroom_tagger/core/cli.py`
- The migration must run in WSL. OpenCLI installation, invocation, adapter loading, and smoke tests should all assume WSL as the supported runtime.
- The migrated flow must preserve:
  - persistent structured Instagram records
  - persistent downloaded media
  - stable local paths usable by matching/debugging scripts
  - idempotent re-runs

---

## Task 1: Document the current `agent-browser` baseline and WSL assumptions

**Files:**
- Modify: `README.md`
- Modify: `docs/plans/2026-03-19-instagram-opencli-migration.md`

**Step 1: Write the failing documentation expectation**

Add a short checklist section to this plan noting the implementation is incomplete until the repo docs explicitly state:
- the old `agent-browser` path was working and is the regression baseline
- OpenCLI must be run from WSL
- the first delivery stops at POC

**Step 2: Inspect current docs for mismatches**

Run:

```bash
cd /home/cristian/lightroom_tagger
python -m pytest lightroom_tagger/instagram/test_browser.py lightroom_tagger/instagram/test_scraper.py -v
```

Expected:
- Existing tests may not fully prove runtime behavior, but they identify the current code surface we must preserve while changing internals.

**Step 3: Update README**

Add an Instagram migration note covering:
- WSL-only OpenCLI runtime assumption
- `agent-browser` as the current behavior baseline
- manual Chrome login/session reuse expectation

**Step 4: Verify docs are coherent**

Manually confirm there is no README guidance that still implies Windows PowerShell is the primary OpenCLI runtime.

**Step 5: Commit**

```bash
git add README.md docs/plans/2026-03-19-instagram-opencli-migration.md
git commit -m "docs(instagram): document opencli migration baseline and wsl runtime"
```

---

## Task 2: Define a canonical Instagram ingestion model

**Files:**
- Create: `lightroom_tagger/instagram/models.py`
- Create: `lightroom_tagger/instagram/test_models.py`
- Modify: `lightroom_tagger/instagram/__init__.py`

**Step 1: Write the failing test**

```python
from lightroom_tagger.instagram.models import InstagramMediaRecord, InstagramPostRecord


def test_media_record_key_is_stable():
    media = InstagramMediaRecord(
        post_id="ABC123",
        post_url="https://www.instagram.com/p/ABC123/",
        media_index=2,
        media_type="image",
        source_url="https://cdn.example/image.jpg",
    )

    assert media.stable_key == "ABC123:2"
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd /home/cristian/lightroom_tagger
python -m pytest lightroom_tagger/instagram/test_models.py -v
```

Expected: FAIL with import/module errors.

**Step 3: Implement minimal model layer**

Create dataclasses for:
- `InstagramPostRecord`
- `InstagramMediaRecord`
- `InstagramDownloadResult`
- `InstagramIngestionResult`

Include fields for:
- `post_id`
- `post_url`
- `caption`
- `timestamp`
- `media_index`
- `media_type`
- `source_url`
- `local_path`
- `status`

**Step 4: Run tests to verify they pass**

Run:

```bash
cd /home/cristian/lightroom_tagger
python -m pytest lightroom_tagger/instagram/test_models.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add lightroom_tagger/instagram/models.py lightroom_tagger/instagram/test_models.py lightroom_tagger/instagram/__init__.py
git commit -m "feat(instagram): add canonical ingestion models"
```

---

## Task 3: Add an OpenCLI runner for WSL-backed command execution

**Files:**
- Create: `lightroom_tagger/instagram/opencli_runner.py`
- Create: `lightroom_tagger/instagram/test_opencli_runner.py`
- Modify: `lightroom_tagger/core/config.py`

**Step 1: Write the failing test**

```python
from unittest.mock import MagicMock, patch

from lightroom_tagger.instagram.opencli_runner import OpenCLIRunner


@patch("subprocess.run")
def test_runner_invokes_opencli_in_json_mode(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stdout='{"posts":[]}', stderr="")

    runner = OpenCLIRunner(command="opencli")
    result = runner.run_json(["instagram", "profile", "--username", "im.canales"])

    assert result == {"posts": []}
    mock_run.assert_called_once()
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd /home/cristian/lightroom_tagger
python -m pytest lightroom_tagger/instagram/test_opencli_runner.py -v
```

Expected: FAIL because the runner does not exist yet.

**Step 3: Implement the runner**

Add a runner that:
- shells out to `opencli`
- always requests JSON output where supported
- raises clear errors for non-zero exit, missing binary, or invalid JSON
- exposes helpers for:
  - setup/doctor checks
  - metadata extraction commands
  - download commands

Add config defaults for:
- `opencli_command`
- optional adapter path

**Step 4: Run tests to verify they pass**

Run:

```bash
cd /home/cristian/lightroom_tagger
python -m pytest lightroom_tagger/instagram/test_opencli_runner.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add lightroom_tagger/instagram/opencli_runner.py lightroom_tagger/instagram/test_opencli_runner.py lightroom_tagger/core/config.py
git commit -m "feat(instagram): add opencli runner and config"
```

---

## Task 4: Add the OpenCLI ingestion backend with metadata-first and download modes

**Files:**
- Create: `lightroom_tagger/instagram/opencli_backend.py`
- Create: `lightroom_tagger/instagram/test_opencli_backend.py`

**Step 1: Write the failing test**

```python
from unittest.mock import Mock

from lightroom_tagger.instagram.opencli_backend import OpenCLIInstagramBackend


def test_backend_parses_profile_payload_into_media_records():
    runner = Mock()
    runner.run_json.return_value = {
        "posts": [
            {
                "post_id": "ABC123",
                "post_url": "https://www.instagram.com/p/ABC123/",
                "caption": "caption",
                "media": [
                    {"media_index": 0, "media_type": "image", "source_url": "https://cdn.example/0.jpg"},
                    {"media_index": 1, "media_type": "image", "source_url": "https://cdn.example/1.jpg"},
                ],
            }
        ]
    }

    backend = OpenCLIInstagramBackend(runner=runner)
    result = backend.list_profile_media("im.canales", limit=5)

    assert len(result.media) == 2
    assert result.media[1].stable_key == "ABC123:1"
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd /home/cristian/lightroom_tagger
python -m pytest lightroom_tagger/instagram/test_opencli_backend.py -v
```

Expected: FAIL

**Step 3: Implement backend behavior**

Add methods for:
- `list_profile_media(username, limit)`
- `download_media(records, output_dir)`

Requirements:
- parse OpenCLI JSON into the canonical models
- support metadata-only operation
- support download-enabled operation
- preserve post/media indexing and post association

**Step 4: Run tests to verify they pass**

Run:

```bash
cd /home/cristian/lightroom_tagger
python -m pytest lightroom_tagger/instagram/test_opencli_backend.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add lightroom_tagger/instagram/opencli_backend.py lightroom_tagger/instagram/test_opencli_backend.py
git commit -m "feat(instagram): add opencli-backed ingestion backend"
```

---

## Task 5: Add canonical persistence and duplicate protection

**Files:**
- Modify: `lightroom_tagger/core/database.py`
- Create: `lightroom_tagger/instagram/persistence.py`
- Create: `lightroom_tagger/instagram/test_persistence.py`

**Step 1: Write the failing test**

```python
from lightroom_tagger.instagram.models import InstagramMediaRecord
from lightroom_tagger.instagram.persistence import should_download_media


def test_known_media_is_skipped_before_download():
    existing = {
        "ABC123:0": {
            "stable_key": "ABC123:0",
            "source_url": "https://cdn.example/0.jpg",
            "local_path": "/tmp/instagram_images/ABC123/img_0.jpg",
        }
    }

    media = InstagramMediaRecord(
        post_id="ABC123",
        post_url="https://www.instagram.com/p/ABC123/",
        media_index=0,
        media_type="image",
        source_url="https://cdn.example/0.jpg",
    )

    assert should_download_media(media, existing) is False
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd /home/cristian/lightroom_tagger
python -m pytest lightroom_tagger/instagram/test_persistence.py -v
```

Expected: FAIL

**Step 3: Implement persistence helpers**

Add helpers that:
- generate canonical local paths like `{output_dir}/{post_id}/img_{index}.jpg`
- determine if a media item is already known using:
  - `post_id + media_index`
  - canonicalized `source_url`
  - optional stored file hash or perceptual hash
- upsert post/media records into the DB
- record download status and timestamps

**Step 4: Run tests to verify they pass**

Run:

```bash
cd /home/cristian/lightroom_tagger
python -m pytest lightroom_tagger/instagram/test_persistence.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add lightroom_tagger/core/database.py lightroom_tagger/instagram/persistence.py lightroom_tagger/instagram/test_persistence.py
git commit -m "feat(instagram): persist media canonically and skip known duplicates"
```

---

## Task 6: Add stop-signal heuristics for repeated duplicate loops

**Files:**
- Create: `lightroom_tagger/instagram/stop_conditions.py`
- Create: `lightroom_tagger/instagram/test_stop_conditions.py`
- Modify: `lightroom_tagger/instagram/opencli_backend.py`

**Step 1: Write the failing test**

```python
from lightroom_tagger.instagram.stop_conditions import StopSignalTracker


def test_tracker_stops_after_consecutive_known_media():
    tracker = StopSignalTracker(
        max_consecutive_known_media=3,
        max_consecutive_posts_without_new_media=2,
    )

    assert tracker.should_stop() is False
    tracker.record_known_media()
    tracker.record_known_media()
    tracker.record_known_media()

    assert tracker.should_stop() is True
    assert tracker.stop_reason == "max_consecutive_known_media"
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd /home/cristian/lightroom_tagger
python -m pytest lightroom_tagger/instagram/test_stop_conditions.py -v
```

Expected: FAIL

**Step 3: Implement the tracker**

Track:
- consecutive known media
- consecutive posts with no new media
- repeated page windows/post ID slices

Expose:
- `should_stop()`
- `stop_reason`
- serializable counters for run-state persistence

Wire the tracker into the OpenCLI ingestion loop so repeated duplicate content causes a clean early stop instead of endless downloading.

**Step 4: Run tests to verify they pass**

Run:

```bash
cd /home/cristian/lightroom_tagger
python -m pytest lightroom_tagger/instagram/test_stop_conditions.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add lightroom_tagger/instagram/stop_conditions.py lightroom_tagger/instagram/test_stop_conditions.py lightroom_tagger/instagram/opencli_backend.py
git commit -m "feat(instagram): add stop-signal heuristics for duplicate loops"
```

---

## Task 7: Add a unified Instagram ingestion service and stop at first POC

**Files:**
- Create: `lightroom_tagger/instagram/service.py`
- Create: `lightroom_tagger/instagram/test_service.py`
- Modify: `lightroom_tagger/instagram/crawler.py`

**Step 1: Write the failing test**

```python
from unittest.mock import Mock

from lightroom_tagger.instagram.service import InstagramIngestionService


def test_service_returns_poc_summary_with_stop_reason():
    backend = Mock()
    backend.run_poc.return_value = {
        "new_media": 2,
        "skipped_media": 3,
        "stop_reason": "max_consecutive_known_media",
    }

    service = InstagramIngestionService(backend=backend)
    result = service.run_poc("im.canales", "/tmp/instagram_images", limit=5)

    assert result["stop_reason"] == "max_consecutive_known_media"
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd /home/cristian/lightroom_tagger
python -m pytest lightroom_tagger/instagram/test_service.py -v
```

Expected: FAIL

**Step 3: Implement the service**

The service should:
- run setup/doctor validation
- extract metadata
- download only new media
- persist canonical DB/file state
- return a POC summary including:
  - discovered posts/media
  - new downloads
  - skipped duplicates
  - stop reason
- intentionally stop after the first bounded POC run instead of continuing toward full migration behavior

Update `crawler.py` to use the unified service instead of directly importing the old API scraper.

**Step 4: Run tests to verify they pass**

Run:

```bash
cd /home/cristian/lightroom_tagger
python -m pytest lightroom_tagger/instagram/test_service.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add lightroom_tagger/instagram/service.py lightroom_tagger/instagram/test_service.py lightroom_tagger/instagram/crawler.py
git commit -m "feat(instagram): add unified ingestion service with poc stop gate"
```

---

## Task 8: Refactor CLI to call the unified OpenCLI service

**Files:**
- Modify: `lightroom_tagger/core/cli.py`
- Create: `lightroom_tagger/core/test_cli_instagram.py`

**Step 1: Write the failing test**

```python
from unittest.mock import Mock, patch

from lightroom_tagger.core.cli import cmd_instagram_sync


def test_cli_delegates_to_instagram_service():
    args = Mock(
        db="library.db",
        catalog=None,
        instagram_url="https://www.instagram.com/im.canales/",
        keyword="Posted",
        hash_threshold=5,
        limit=5,
        dry_run=True,
        output_dir="/tmp/instagram_images",
        browser=False,
        login=False,
        check_opencli=False,
    )
    config = Mock(
        db_path="library.db",
        instagram_url="https://www.instagram.com/im.canales/",
        instagram_keyword="Posted",
        hash_threshold=5,
        small_catalog_path="",
    )

    with patch("lightroom_tagger.core.cli.InstagramIngestionService") as mock_service_cls:
        mock_service = mock_service_cls.return_value
        mock_service.run_poc.return_value = {"new_media": 1, "skipped_media": 0, "stop_reason": None}

        result = cmd_instagram_sync(args, config)

    assert result == 0
    mock_service.run_poc.assert_called_once()
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd /home/cristian/lightroom_tagger
python -m pytest lightroom_tagger/core/test_cli_instagram.py -v
```

Expected: FAIL

**Step 3: Refactor the CLI**

Update `cmd_instagram_sync` to:
- validate DB/config as before
- call the new ingestion service
- print a concise POC summary
- optionally support a lightweight OpenCLI check mode
- keep `--browser` as a temporary compatibility alias only if required for user continuity

Do not remove old code until the new tests and POC smoke checks pass.

**Step 4: Run tests to verify they pass**

Run:

```bash
cd /home/cristian/lightroom_tagger
python -m pytest lightroom_tagger/core/test_cli_instagram.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add lightroom_tagger/core/cli.py lightroom_tagger/core/test_cli_instagram.py
git commit -m "refactor(cli): delegate instagram sync to opencli ingestion service"
```

---

## Task 9: Create the first real POC smoke checklist and stop for review

**Files:**
- Modify: `README.md`
- Modify: `docs/plans/2026-03-19-instagram-opencli-migration.md`

**Step 1: Write the manual validation checklist**

Add a checklist for the first WSL-only POC:
- confirm `opencli` exists in WSL
- run adapter/doctor check
- confirm logged-in Chrome session reuse
- scrape a small profile sample
- persist metadata and media
- immediately re-run the same sample
- verify duplicate skips and stop reason behavior

**Step 2: Run bounded verification commands**

Run:

```bash
cd /home/cristian/lightroom_tagger
python -m pytest \
  lightroom_tagger/instagram/test_models.py \
  lightroom_tagger/instagram/test_opencli_runner.py \
  lightroom_tagger/instagram/test_opencli_backend.py \
  lightroom_tagger/instagram/test_persistence.py \
  lightroom_tagger/instagram/test_stop_conditions.py \
  lightroom_tagger/instagram/test_service.py \
  lightroom_tagger/core/test_cli_instagram.py -v
```

Expected: PASS

**Step 3: Record the review gate**

Add a note to README and this plan:
- after the first real POC, stop implementation
- review what additional safeguards are needed before broader rollout
- specifically evaluate duplicate suppression quality and stop-signal thresholds

**Step 4: Commit**

```bash
git add README.md docs/plans/2026-03-19-instagram-opencli-migration.md
git commit -m "docs(instagram): add poc smoke checklist and review gate"
```

---

## Summary

After this plan:
- Instagram ingestion has one canonical Python-facing interface.
- OpenCLI is the primary runtime target and is assumed to run in WSL.
- Persisted metadata and local downloaded media remain first-class outputs.
- Duplicate media prevention and stop signals are implemented before broader rollout.
- Work intentionally pauses after the first validated POC so we can add more safeguards based on observed behavior.

**Plan complete and saved to `docs/plans/2026-03-19-instagram-opencli-migration.md`. Two execution options:**

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

**Which approach?**
