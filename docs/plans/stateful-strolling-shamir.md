# Vision Cache System Fix Plan

## Context

I'm working on fixing the vision cache system architecture where:
- 303 catalog images exist in `images` table (from scan)
- `catalog_images` table is empty (enrichment never ran)
- Vision cache shows 0/0 because it queries empty `catalog_images` table
- The enrichment system exists but has no CLI command or automatic trigger

The goal is to create a comprehensive solution that provides both manual and automatic ways to enrich catalog data and enable the vision cache system.

## Recommended Approach

**Dual approach: Manual CLI + Automatic Job Integration**

1. **Manual CLI command** - Simple, user-controlled, good for debugging
2. **Automatic job integration** - User-friendly, ensures data consistency

## Implementation Plan

### Phase 1: CLI Command Integration

**File: `/home/cristian/lightroom_tagger/lightroom_tagger/cli.py`**

**Step 1: Add CLI command structure**

```python
# Add to create_parser() subparsers
senrich_parser = subparsers.add_parser("enrich-catalog", help="Enrich catalog with metadata")
enrich_parser.add_argument("--db", help="Path to TinyDB (overrides global)")
enrich_parser.add_argument("--limit", type=int, help="Limit number of images to process")
enrich_parser.add_argument("--dry-run", action="store_true", help="Show what would be processed")

# Add function
def cmd_enrich_catalog(args, config):
    """Enrich catalog with metadata."""
    db_path = args.db or config.db_path
    limit = args.limit
    dry_run = args.dry_run

    if dry_run:
        print("Dry run mode - will show what would be processed")

    try:
        db = init_database(db_path)
        result = enrich_catalog_images(db, limit=limit)
        db.close()

        print(f"Processed: {result['processed']} images")
        print(f"Skipped: {result['skipped']} images")
        print(f"Errors: {result['errors']} errors")
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1
```

**Step 2: Add to main() command routing**

```python
elif args.command == "enrich-catalog":
    return cmd_enrich_catalog(args, config)
```

### Phase 2: Automatic Job Integration

**File: `/home/cristian/lightroom_tagger/apps/visualizer/backend/jobs/handlers.py`**

**Step 1: Add new handler**

```python
def handle_enrich_catalog(runner, job_id: str, metadata: dict):
    """Enrich catalog with metadata and populate vision cache."""
    from lightroom_tagger.lightroom.enricher import enrich_catalog_images
    from lightroom_tagger.core.database import init_database

    runner.update_progress(job_id, 10, 'Initializing enrichment...')

    db_path = os.getenv('LIBRARY_DB')
    if not db_path:
        config = load_config()
        db_path = config.db_path or 'library.db'

    if not os.path.exists(db_path):
        runner.fail_job(job_id, f"Library database not found at: {db_path}")
        return

    try:
        db = init_database(db_path)
        result = enrich_catalog_images(db, limit=metadata.get('limit'))

        runner.complete_job(job_id, {
            'processed': result['processed'],
            'skipped': result['skipped'],
            'errors': result['errors'],
            'method': 'enrich_catalog',
            'limit': metadata.get('limit')
        })

    except Exception as e:
        runner.fail_job(job_id, str(e))
    finally:
        if db:
            db.close()
```

**Step 2: Register in JOB_HANDLERS**

```python
JOB_HANDLERS = {
    'analyze_instagram': handle_analyze_instagram,
    'vision_match': handle_vision_match,
    'enrich_catalog': handle_enrich_catalog,  # NEW
    'prepare_catalog': handle_prepare_catalog,
}
```

### Phase 3: Database Schema Enhancement

**File: `/home/cristian/lightroom_tagger/lightroom_tagger/core/database.py`**

**Step 1: Add table initialization**

```python
def init_catalog_table(db: TinyDB):
    """Ensure catalog_images table exists."""
    if 'catalog_images' not in db.tables():
        db.table('catalog_images')
```

**Step 2: Add missing table initializations**

```python
def init_vision_comparisons_table(db: TinyDB):
    """Ensure vision_comparisons table exists."""
    if 'vision_comparisons' not in db.tables():
        db.table('vision_comparisons')
```

### Phase 4: Backend API Enhancement

**File: `/home/cristian/lightroom_tagger/apps/visualizer/backend/api/system.py`**

**Step 1: Add cache status endpoint (already exists)**

```python
@bp.route('/cache/status', methods=['GET'])
def get_cache_status():
    """Get vision cache status."""
    try:
        db_path = config.LIBRARY_DB
        if not os.path.exists(db_path):
            return jsonify({'error': 'Library database not found'}), 404

        db = TinyDB(db_path)
        from lightroom_tagger.core.database import get_cache_stats
        cache_stats = get_cache_stats(db)

        lt_config = load_lt_config()
        cache_dir = lt_config.vision_cache_dir

        db.close()
        return jsonify({
            'total_images': cache_stats['total'],
            'cached_images': cache_stats['cached'],
            'missing': cache_stats['missing'],
            'cache_size_mb': round(cache_stats['cache_size_mb'], 2),
            'cache_dir': cache_dir,
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
```

### Phase 5: Frontend Integration

**File: `/home/cristian/lightroom_tagger/apps/visualizer/frontend/src/pages/DashboardPage.tsx`**

**Step 1: Add cache status display**

```typescript
// Add to DashboardPage component
const [cacheStatus, setCacheStatus] = useState<CacheStatus | null>(null);

useEffect(() => {
    const loadCacheStatus = async () => {
        try {
            const response = await fetch('/api/cache/status');
            if (response.ok) {
                const data = await response.json();
                setCacheStatus(data);
            }
        } catch (error) {
            console.warn('Failed to load cache status:', error);
        }
    };
    loadCacheStatus();
}, []);

// Add to render
{cacheStatus && (
    <div className="mt-4 p-4 bg-gray-50 rounded-lg">
        <h3 className="text-lg font-semibold mb-2">Vision Cache Status</h3>
        <div className="grid grid-cols-2 gap-4">
            <div>
                <p className="text-sm text-gray-600">Total Catalog Images</p>
                <p className="text-lg font-bold">{cacheStatus.total_images}</p>
            </div>
            <div>
                <p className="text-sm text-gray-600">Cached</p>
                <p className="text-lg font-bold text-green-600">{cacheStatus.cached_images}</p>
            </div>
            <div>
                <p className="text-sm text-gray-600">Missing</p>
                <p className="text-lg font-bold text-red-600">{cacheStatus.missing}</p>
            </div>
            <div>
                <p className="text-sm text-gray-600">Cache Size</p>
                <p className="text-lg font-bold">{cacheStatus.cache_size_mb}MB</p>
            </div>
        </div>
    </div>
)}
```

### Phase 6: Documentation

**File: `/home/cristian/lightroom_tagger/README.md`**

**Step 1: Add documentation section**

```markdown
## Vision Cache System

The vision cache system pre-compresses catalog images for efficient vision matching.

### Status
```bash
# Check cache status via API
curl http://localhost:5000/api/cache/status
```

### Manual Enrichment
```bash
# Scan catalog first (if not done)
lightroom-tagger scan --catalog /path/to/catalog.lrcat

# Enrich catalog with metadata
lightroom-tagger enrich-catalog --db library.db

# Check results
lightroom-tagger stats --db library.db
```

### Automatic Enrichment

The visualizer provides a "Prepare Catalog" job that automatically enriches and caches images before matching.
```
```

## Benefits of This Solution

### ✅ Data Flow Fixed
- `scan` → populates `images` table
- `enrich-catalog` → populates `catalog_images` and `vision_cache` tables
- Vision matching works automatically

### ✅ Multiple User Options
1. **Manual CLI** - Simple, scriptable, good for debugging
2. **Automatic Jobs** - User-friendly, ensures consistency

### ✅ Clear Status Visibility
- Cache status endpoint
- Frontend dashboard display
- CLI stats command

### ✅ Backward Compatibility
- Existing `scan` command still works
- No breaking changes to current API
- Optional new features

### ✅ Testable Architecture
- Each component independently testable
- Clear separation of concerns
- Well-defined interfaces

## Critical Files for Implementation

Based on my exploration, here are the most critical files for implementing this plan:

### Core Files (must modify):
- `/home/cristian/lightroom_tagger/lightroom_tagger/cli.py` - Add CLI command
- `/home/cristian/lightroom_tagger/apps/visualizer/backend/jobs/handlers.py` - Add job handler
- `/home/cristian/lightroom_tagger/apps/visualizer/backend/api/system.py` - Add endpoint

### Support Files (may need modification):
- `/home/cristian/lightroom_tagger/lightroom_tagger/core/database.py` - Add table init
- `/home/cristian/lightroom_tagger/apps/visualizer/frontend/src/pages/DashboardPage.tsx` - Add UI

### Existing Files (reference):
- `/home/cristian/lightroom_tagger/lightroom_tagger/lightroom/enricher.py` - Core enrichment logic
- `/home/cristian/lightroom_tagger/apps/visualizer/frontend/src/pages/DashboardPage.tsx` - Example UI structure

This solution provides a comprehensive, maintainable fix that addresses the root cause while giving users multiple ways to work with the system. The dual approach ensures both simplicity for manual users and automation for visualizer users.
```