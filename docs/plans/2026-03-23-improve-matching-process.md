# Improve Matching Process Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace brute-force matching with cascade matching using 90-day date window and add UI trigger for running matching with date filters.

**Architecture:** Filter Instagram images by date (month/year/last N), find catalog candidates within 90 days before posting, run vision comparison on filtered candidates, auto-update Lightroom with "Posted" keyword.

**Tech Stack:** Python, TinyDB, Flask-SocketIO, React/TypeScript

---

## Task 1: Add Date Filtering Function

**Files:**
- Modify: `lightroom_tagger/core/database.py`
- Test: `lightroom_tagger/core/test_database.py`

**Step 1: Write test for date filtering**

Add to `test_database.py`:
```python
def test_get_instagram_by_month_filter(self):
    """Test filtering Instagram images by month."""
    from datetime import datetime
    
    # Insert test data
    self.db.table('instagram_dump_media').insert({
        'media_key': '202603/123',
        'date_folder': '202603',
        'filename': 'test1.jpg'
    })
    self.db.table('instagram_dump_media').insert({
        'media_key': '202604/456',
        'date_folder': '202604',
        'filename': 'test2.jpg'
    })
    
    # Test month filter
    result = get_instagram_by_date_filter(self.db, month='202603')
    self.assertEqual(len(result), 1)
    self.assertEqual(result[0]['media_key'], '202603/123')
```

**Step 2: Run test to verify it fails**

```bash
cd /home/cristian/lightroom_tagger
python3 -m pytest lightroom_tagger/core/test_database.py::TestDatabase::test_get_instagram_by_month_filter -v
```

Expected: FAIL with "get_instagram_by_date_filter not defined"

**Step 3: Implement date filtering function**

Add to `database.py`:
```python
def get_instagram_by_date_filter(db, month: str = None, year: str = None,
                                  last_months: int = None) -> list:
    """Get Instagram dump media filtered by date.
    
    Args:
        month: Filter by month (e.g., '202603')
        year: Filter by year (e.g., '2026')
        last_months: Filter by last N months from now
    """
    from datetime import datetime, timedelta
    
    Media = Query()
    table = db.table('instagram_dump_media')
    
    if month:
        return table.search(Media.date_folder == month)
    
    elif year:
        return table.search(Media.date_folder.matches(f'{year}*'))
    
    elif last_months:
        from_date = (datetime.now() - timedelta(days=last_months * 30)).strftime('%Y%m')
        all_media = table.all()
        return [m for m in all_media if m.get('date_folder', '000000') >= from_date]
    
    return table.all()
```

**Step 4: Run test to verify it passes**

```bash
python3 -m pytest lightroom_tagger/core/test_database.py::TestDatabase::test_get_instagram_by_month_filter -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add lightroom_tagger/core/database.py
git add lightroom_tagger/core/test_database.py
git commit -m "feat: add date filtering for Instagram images"
```

---

## Task 2: Implement Cascade Matching

**Files:**
- Create: `lightroom_tagger/scripts/match_instagram_dump_v2.py`
- Modify: `lightroom_tagger/core/matcher.py`
- Test: Run script manually

**Step 1: Add cascade matching to matcher.py**

```python
def find_candidates_by_date(db, insta_image: dict, days_before: int = 90) -> list:
    """Find catalog candidates within date window before Instagram posting."""
    from datetime import datetime, timedelta
    
    date_folder = insta_image.get('date_folder', '')
    if len(date_folder) != 6:
        return []
    
    post_year = int(date_folder[:4])
    post_month = int(date_folder[4:6])
    post_date = datetime(post_year, post_month, 15)
    window_start = post_date - timedelta(days=days_before)
    
    candidates = []
    for img in db.table('images').all():
        date_taken = img.get('date_taken', '')
        if not date_taken:
            continue
        try:
            img_date = datetime.fromisoformat(date_taken.replace('Z', '+00:00'))
            if window_start <= img_date <= post_date:
                candidates.append(img)
        except:
            continue
    
    return candidates
```

**Step 2: Create new match script**

Create `match_instagram_dump_v2.py`:
```python
#!/usr/bin/env python3
"""Match Instagram dump with cascade filtering."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lightroom_tagger.core.database import init_database, get_instagram_by_date_filter
from lightroom_tagger.core.matcher import find_candidates_by_date, score_candidates_with_vision

def match_with_cascade(db, month=None, year=None, last_months=None, threshold=0.7):
    """Run cascade matching with date filtering."""
    stats = {'processed': 0, 'matched': 0}
    
    unprocessed = get_instagram_by_date_filter(db, month=month, year=year,
                                                last_months=last_months)
    unprocessed = [u for u in unprocessed if not u.get('processed')]
    
    for dump_media in unprocessed:
        stats['processed'] += 1
        candidates = find_candidates_by_date(db, dump_media)
        
        if candidates:
            dump_image = {
                'key': dump_media['media_key'],
                'local_path': dump_media.get('file_path'),
                'image_hash': dump_media.get('image_hash'),
                'description': dump_media.get('caption', ''),
            }
            
            vision_candidates = [{
                'key': c['key'],
                'local_path': c.get('filepath'),
                'image_hash': c.get('phash'),
                'description': '',
            } for c in candidates]
            
            results = score_candidates_with_vision(
                db, dump_image, vision_candidates,
                phash_weight=0.0, desc_weight=0.0, vision_weight=1.0
            )
            
            if results and results[0]['total_score'] >= threshold:
                stats['matched'] += 1
                # TODO: Store match and update Lightroom
    
    return stats

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--db', default='library.db')
    parser.add_argument('--month')
    parser.add_argument('--year')
    parser.add_argument('--last-months', type=int)
    args = parser.parse_args()
    
    db = init_database(args.db)
    stats = match_with_cascade(db, month=args.month, year=args.year,
                               last_months=args.last_months)
    print(f"Processed: {stats['processed']}, Matched: {stats['matched']}")
    db.close()
```

**Step 3: Test manually**

```bash
cd /home/cristian/lightroom_tagger
python3 -m lightroom_tagger.scripts.match_instagram_dump_v2 --month 202603 --db library.db
```

Expected: Shows processed count for March 2026

**Step 4: Commit**

```bash
git add lightroom_tagger/core/matcher.py
git add lightroom_tagger/scripts/match_instagram_dump_v2.py
git commit -m "feat: implement cascade matching with 90-day window"
```

---

## Task 3: Add Lightroom Auto-Update

**Files:**
- Modify: `lightroom_tagger/lightroom/writer.py`
- Modify: `lightroom_tagger/scripts/match_instagram_dump_v2.py`

**Step 1: Implement batch update function**

Add to `writer.py`:
```python
def update_lightroom_from_matches(catalog_path: str, matches: list) -> dict:
    """Add 'Posted' keyword to matched catalog images."""
    stats = {'success': 0, 'failed': 0}
    
    if not matches:
        return stats
    
    conn = connect_catalog(catalog_path)
    keyword_id = get_or_create_keyword(conn, "Posted")
    
    for match in matches:
        catalog_key = match.get('catalog_key')
        if not catalog_key:
            continue
        
        # Extract filename from key
        filename = catalog_key.split('_')[-1] if '_' in catalog_key else catalog_key
        
        cursor = conn.cursor()
        cursor.execute("SELECT id_local FROM AgLibraryFile WHERE name LIKE ?", (f"{filename}%",))
        result = cursor.fetchone()
        
        if result and add_keyword_to_image(conn, result[0], keyword_id):
            stats['success'] += 1
        else:
            stats['failed'] += 1
    
    conn.commit()
    conn.close()
    return stats
```

**Step 2: Update match script to call Lightroom update**

Add to end of `match_with_cascade()`:
```python
from lightroom_tagger.core.config import load_config
from lightroom_tagger.lightroom.writer import update_lightroom_from_matches

config = load_config()
catalog_path = config.get('catalog_path') or config.get('small_catalog_path')

if catalog_path and os.path.exists(catalog_path):
    lr_stats = update_lightroom_from_matches(catalog_path, matches_found)
    print(f"Lightroom: {lr_stats['success']} updated")
```

**Step 3: Test**

```bash
python3 -m lightroom_tagger.scripts.match_instagram_dump_v2 --db library.db --month 202603
```

Expected: Shows Lightroom update count

**Step 4: Commit**

```bash
git add lightroom_tagger/lightroom/writer.py
git add lightroom_tagger/scripts/match_instagram_dump_v2.py
git commit -m "feat: auto-update Lightroom with Posted keyword on match"
```

---

## Task 4: Delete DumpMediaPage

**Files:**
- Delete: `apps/visualizer/frontend/src/pages/DumpMediaPage.tsx`
- Modify: `apps/visualizer/frontend/src/App.tsx`
- Modify: `apps/visualizer/frontend/src/components/Layout.tsx`

**Step 1: Remove from Layout.tsx**

Remove Dump Media from navigation array.

**Step 2: Remove from App.tsx**

Remove `/dump-media` route.

**Step 3: Delete file**

```bash
rm /home/cristian/lightroom_tagger/apps/visualizer/frontend/src/pages/DumpMediaPage.tsx
```

**Step 4: Verify build**

```bash
cd /home/cristian/lightroom_tagger/apps/visualizer/frontend
npm run build
```

Expected: Build succeeds with no errors

**Step 5: Commit**

```bash
git add -A
git commit -m "chore: remove redundant DumpMediaPage"
```

---

## Task 5: Update MatchingPage UI

**Files:**
- Modify: `apps/visualizer/frontend/src/pages/MatchingPage.tsx`
- Modify: `apps/visualizer/frontend/src/services/api.ts`

**Step 1: Add job creation endpoint**

Add to `api.ts`:
```typescript
export const JobsAPI = {
  create: async (type: string, metadata: Record<string, any>) => {
    const response = await fetch(`${API_BASE}/jobs`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type, metadata }),
    });
    return response.json();
  },
};
```

**Step 2: Update MatchingPage with trigger UI**

Add to MatchingPage:
```typescript
import { ACTION_RUN_MATCHING, MSG_NO_MATCHES, MATCHING_RESULTS } from '../constants/strings';
import { JobsAPI } from '../services/api';

// Add state
const [showTrigger, setShowTrigger] = useState(false);
const [dateFilter, setDateFilter] = useState<'all' | '3months' | '6months' | '2026'>('all');

// Add trigger function
async function startMatching() {
  const metadata: any = {};
  if (dateFilter === '3months') metadata.last_months = 3;
  else if (dateFilter === '6months') metadata.last_months = 6;
  else if (dateFilter === '2026') metadata.year = '2026';
  
  await JobsAPI.create('vision_match', metadata);
  alert('Matching started');
  setShowTrigger(false);
}
```

**Step 3: Add UI elements**

Add button and dropdown:
```typescript
<button onClick={() => setShowTrigger(true)}>
  {ACTION_RUN_MATCHING}
</button>

{showTrigger && (
  <select value={dateFilter} onChange={(e) => setDateFilter(e.target.value as any)}>
    <option value="all">All time</option>
    <option value="3months">Last 3 months</option>
    <option value="6months">Last 6 months</option>
    <option value="2026">2026 only</option>
  </select>
  <button onClick={startMatching}>Start</button>
)}
```

**Step 4: Test**

```bash
cd /home/cristian/lightroom_tagger/apps/visualizer/frontend
npm run dev
```

Open MatchingPage, click Run Matching, select filter, start. Alert should appear.

**Step 5: Commit**

```bash
git add apps/visualizer/frontend/src/pages/MatchingPage.tsx
git add apps/visualizer/frontend/src/services/api.ts
git commit -m "feat: add matching trigger UI with date filter"
```

---

## Task 6: Implement Job Handler

**Files:**
- Modify: `apps/visualizer/backend/jobs/handlers.py`

**Step 1: Implement handle_vision_match**

Replace stub:
```python
def handle_vision_match(runner: JobRunner, job_id: str, metadata: dict):
    """Run vision matching with cascade filtering."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
    
    from lightroom_tagger.core.database import init_database
    from lightroom_tagger.scripts.match_instagram_dump_v2 import match_with_cascade
    from lightroom_tagger.core.config import load_config
    
    runner.update_progress(job_id, 0, 'Initializing...')
    
    config = load_config()
    db = init_database(config.get('db_path', 'library.db'))
    
    try:
        runner.update_progress(job_id, 20, 'Matching...')
        
        stats = match_with_cascade(
            db,
            month=metadata.get('month'),
            year=metadata.get('year'),
            last_months=metadata.get('last_months')
        )
        
        runner.update_progress(job_id, 100, 'Complete')
        runner.complete_job(job_id, stats)
        
    finally:
        db.close()
```

**Step 2: Test**

```bash
curl -X POST http://localhost:5000/api/jobs \
  -H "Content-Type: application/json" \
  -d '{"type": "vision_match", "metadata": {"last_months": 3}}'
```

**Step 3: Commit**

```bash
git add apps/visualizer/backend/jobs/handlers.py
git commit -m "feat: implement vision_match job handler"
```

---

## Task 7: Add Match Detail Modal

**Files:**
- Create: `apps/visualizer/frontend/src/components/MatchDetailModal.tsx`
- Modify: `apps/visualizer/frontend/src/pages/MatchingPage.tsx`

**Step 1: Create modal component**

```typescript
import { useState } from 'react';
import { MODAL_CLOSE } from '../constants/strings';

export function MatchDetailModal({ match, onClose }: { match: any, onClose: () => void }) {
  if (!match) return null;
  
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg max-w-4xl w-full p-6">
        <button onClick={onClose}>{MODAL_CLOSE}</button>
        <div className="grid grid-cols-2 gap-4">
          <img src={`/api/images/instagram/${match.instagram_key}`} />
          <img src={`/api/images/catalog/${match.catalog_key}`} />
        </div>
      </div>
    </div>
  );
}
```

**Step 2: Add to MatchingPage**

```typescript
const [selectedMatch, setSelectedMatch] = useState(null);

// In MatchCard:
<div onClick={() => setSelectedMatch(match)}>

// At bottom:
{selectedMatch && (
  <MatchDetailModal match={selectedMatch} onClose={() => setSelectedMatch(null)} />
)}
```

**Step 3: Test**

Click match card → modal opens with images.

**Step 4: Commit**

```bash
git add apps/visualizer/frontend/src/components/MatchDetailModal.tsx
git add apps/visualizer/frontend/src/pages/MatchingPage.tsx
git commit -m "feat: add match detail modal"
```

---

## Summary

**Files Modified:**
- `lightroom_tagger/core/database.py` - Date filtering
- `lightroom_tagger/core/matcher.py` - Cascade matching
- `lightroom_tagger/scripts/match_instagram_dump_v2.py` - New match script
- `lightroom_tagger/lightroom/writer.py` - Lightroom update
- `apps/visualizer/frontend/src/pages/DumpMediaPage.tsx` - Deleted
- `apps/visualizer/frontend/src/pages/MatchingPage.tsx` - Trigger UI
- `apps/visualizer/frontend/src/services/api.ts` - Jobs API
- `apps/visualizer/frontend/src/components/MatchDetailModal.tsx` - New
- `apps/visualizer/backend/jobs/handlers.py` - Job handler

**Result:**
- 137k comparisons → ~1-5k per run
- UI-controlled matching with date filters
- Auto Lightroom updates
- Match detail modal

---

**Plan complete.** Ready to execute.
