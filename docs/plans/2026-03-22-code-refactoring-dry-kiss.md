# Code Refactoring for DRY, KISS, and String Constants

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refactor backend and frontend code to eliminate DRY violations, simplify complex components (KISS), and extract all string literals to constants files.

**Architecture:** 
- Backend: Extract common database operations into decorators/utilities, move error messages to constants
- Frontend: Split monolithic modal into reusable components, extract all UI strings to constants, create reusable hooks

**Tech Stack:** Python (Flask), TypeScript (React), TinyDB, TailwindCSS

---

## Current Issues Identified

### Backend Violations
1. **DRY**: Database open/check/close pattern repeated 6x across routes
2. **String Literals**: Error messages hardcoded ('Library database not found', 'Image not found')
3. **DRY**: Error response pattern repeated 8x
4. **DRY**: Similar thumbnail logic duplicated for instagram vs catalog

### Frontend Violations
1. **String Literals**: UI text hardcoded in components ('Click for details', 'Image Details', etc.)
2. **Magic Numbers**: ITEMS_PER_PAGE defined locally
3. **KISS**: Modal component 300+ lines handling too many concerns
4. **DRY**: Inline SVG for close button, repeated Tailwind patterns
5. **Missing**: Many UI labels not in constants/strings.ts

---

## Phase 1: Backend - Database Utilities & Constants

### Task 1: Create Backend Error Constants

**Files:**
- Create: `apps/visualizer/backend/constants/errors.py`

**Step 1: Define all error message constants**

```python
"""Backend error message constants."""

# Database errors
ERROR_DB_NOT_FOUND = 'Library database not found'
ERROR_DB_CONNECTION = 'Database connection failed'

# Resource errors
ERROR_IMAGE_NOT_FOUND = 'Image not found'
ERROR_IMAGE_FILE_NOT_FOUND = 'Image file not found'
ERROR_MEDIA_NOT_FOUND = 'Media not found'

# General errors
ERROR_INTERNAL_SERVER = 'Internal server error'
ERROR_INVALID_REQUEST = 'Invalid request parameters'
```

**Step 2: Verify file is importable**

```bash
cd apps/visualizer/backend
python3 -c "from constants.errors import ERROR_DB_NOT_FOUND; print(ERROR_DB_NOT_FOUND)"
```

Expected: `Library database not found`

**Step 3: Commit**

```bash
git add apps/visualizer/backend/constants/errors.py
git commit -m "feat: add backend error message constants"
```

---

### Task 2: Create Database Context Manager

**Files:**
- Create: `apps/visualizer/backend/utils/db.py`

**Step 1: Create database context manager decorator**

```python
"""Database utilities for Flask routes."""
from functools import wraps
from flask import jsonify
from tinydb import TinyDB
import os
from config import LIBRARY_DB
from constants.errors import ERROR_DB_NOT_FOUND


class DatabaseError(Exception):
    """Custom exception for database errors."""
    pass


def with_db(handler_func=None, *, require_exists=True):
    """Decorator that provides database connection to route handlers.
    
    Usage:
        @with_db
        def my_route(db):
            # db is TinyDB instance, already validated
            pass
            
        @with_db(require_exists=False)
        def optional_route(db):
            # db may not exist
            pass
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            db_path = LIBRARY_DB
            
            if require_exists and not os.path.exists(db_path):
                return jsonify({'error': ERROR_DB_NOT_FOUND}), 404
            
            db = None
            try:
                db = TinyDB(db_path)
                return f(db, *args, **kwargs)
            except DatabaseError as e:
                return jsonify({'error': str(e)}), 500
            except Exception as e:
                return jsonify({'error': str(e)}), 500
            finally:
                if db:
                    db.close()
        return wrapper
    
    if handler_func is not None:
        return decorator(handler_func)
    return decorator
```

**Step 2: Create test file**

```python
# apps/visualizer/backend/tests/test_db_utils.py
import pytest
from unittest.mock import patch, MagicMock
from utils.db import with_db, DatabaseError


class TestWithDbDecorator:
    """Tests for with_db decorator."""
    
    @patch('utils.db.os.path.exists')
    @patch('utils.db.TinyDB')
    def test_with_db_when_file_exists(self, mock_tinydb, mock_exists):
        """Test that decorator provides db when file exists."""
        mock_exists.return_value = True
        mock_db = MagicMock()
        mock_tinydb.return_value = mock_db
        
        @with_db
        def test_handler(db):
            return {'data': db}
        
        result = test_handler()
        
        assert result[0]['data'] == mock_db
        mock_db.close.assert_called_once()
    
    @patch('utils.db.os.path.exists')
    def test_with_db_when_file_missing(self, mock_exists):
        """Test that decorator returns 404 when file missing."""
        mock_exists.return_value = False
        
        @with_db
        def test_handler(db):
            return {'data': 'should not reach'}
        
        result = test_handler()
        
        assert result[1] == 404
        assert 'error' in result[0].json
```

**Step 3: Run tests**

```bash
cd apps/visualizer/backend
python3 -m pytest tests/test_db_utils.py -v
```

Expected: PASS

**Step 4: Commit**

```bash
git add apps/visualizer/backend/utils/db.py apps/visualizer/backend/tests/test_db_utils.py
git commit -m "feat: add database context manager decorator"
```

---

### Task 3: Create Error Response Utility

**Files:**
- Create: `apps/visualizer/backend/utils/responses.py`

**Step 1: Create standard error response functions**

```python
"""Standardized response utilities for Flask routes."""
from flask import jsonify
from constants.errors import (
    ERROR_IMAGE_NOT_FOUND,
    ERROR_IMAGE_FILE_NOT_FOUND,
    ERROR_DB_NOT_FOUND,
)


def error_not_found(resource_type='resource'):
    """Return 404 error for resource not found."""
    messages = {
        'image': ERROR_IMAGE_NOT_FOUND,
        'media': ERROR_IMAGE_NOT_FOUND,
        'database': ERROR_DB_NOT_FOUND,
        'file': ERROR_IMAGE_FILE_NOT_FOUND,
    }
    return jsonify({'error': messages.get(resource_type, f'{resource_type} not found')}), 404


def error_bad_request(message='Invalid request'):
    """Return 400 error."""
    return jsonify({'error': message}), 400


def error_server_error(message=None):
    """Return 500 error."""
    from constants.errors import ERROR_INTERNAL_SERVER
    return jsonify({'error': message or ERROR_INTERNAL_SERVER}), 500


def success_paginated(data, total, offset, limit):
    """Return standardized paginated response."""
    has_more = (offset + limit) < total
    current_page = (offset // limit) + 1
    total_pages = (total + limit - 1) // limit
    
    return jsonify({
        'total': total,
        'data': data,
        'pagination': {
            'offset': offset,
            'limit': limit,
            'current_page': current_page,
            'total_pages': total_pages,
            'has_more': has_more,
        }
    })
```

**Step 2: Write tests**

```python
# apps/visualizer/backend/tests/test_responses.py
import pytest
from utils.responses import error_not_found, success_paginated


class TestErrorResponses:
    """Tests for error response utilities."""
    
    def test_error_not_found_image(self):
        """Test image not found error."""
        response, status = error_not_found('image')
        assert status == 404
        assert 'Image not found' in response.json['error']
    
    def test_error_not_found_default(self):
        """Test generic not found error."""
        response, status = error_not_found('unknown')
        assert status == 404
        assert 'unknown not found' in response.json['error']


class TestSuccessResponses:
    """Tests for success response utilities."""
    
    def test_success_paginated(self):
        """Test paginated success response."""
        data = [{'id': 1}, {'id': 2}]
        response = success_paginated(data, 10, 0, 5)
        
        assert response.json['total'] == 10
        assert response.json['data'] == data
        assert response.json['pagination']['has_more'] == True
        assert response.json['pagination']['current_page'] == 1
        assert response.json['pagination']['total_pages'] == 2
```

**Step 3: Run tests**

```bash
python3 -m pytest tests/test_responses.py -v
```

Expected: PASS

**Step 4: Commit**

```bash
git add apps/visualizer/backend/utils/responses.py apps/visualizer/backend/tests/test_responses.py
git commit -m "feat: add standardized response utilities"
```

---

### Task 4: Refactor images.py to Use Utilities

**Files:**
- Modify: `apps/visualizer/backend/api/images.py`

**Step 1: Update imports and refactor list_instagram_images**

Replace the entire file with refactored version using @with_db and response utilities. Extract common patterns:

```python
from flask import Blueprint, jsonify, request, send_file
from utils.db import with_db
from utils.responses import error_not_found, error_server_error, success_paginated

bp = Blueprint('images', __name__)


def _enrich_instagram_media(media_items):
    """Transform database media items to API response format."""
    enriched = []
    for media in media_items:
        file_path = media.get('file_path', '')
        source_folder = _extract_source_folder(file_path)
        
        enriched.append({
            'key': media['media_key'],
            'local_path': file_path,
            'filename': media.get('filename', ''),
            'instagram_folder': media.get('date_folder', ''),
            'source_folder': source_folder,
            'image_hash': media.get('image_hash'),
            'description': media.get('caption', ''),
            'crawled_at': media.get('added_at', ''),
            'image_index': 1,
            'total_in_post': 1,
            'post_url': media.get('post_url'),
            'exif_data': media.get('exif_data'),
        })
    return enriched


def _extract_source_folder(file_path):
    """Extract source folder (posts, archived_posts) from file path."""
    if '/media/' in file_path:
        parts = file_path.split('/media/')
        if len(parts) > 1:
            subpath = parts[1].split('/')
            if len(subpath) > 0:
                return subpath[0]
    return 'unknown'


def _filter_by_date(images, date_folder, date_from, date_to):
    """Filter images by date parameters."""
    if date_folder:
        return [img for img in images if img['instagram_folder'] == date_folder]
    
    if date_from:
        images = [img for img in images if img['instagram_folder'] and img['instagram_folder'] >= date_from]
    if date_to:
        images = [img for img in images if img['instagram_folder'] and img['instagram_folder'] <= date_to]
    
    return images


@bp.route('/instagram', methods=['GET'])
@with_db
def list_instagram_images(db):
    """List Instagram images with filtering and pagination."""
    try:
        media_items = db.table('instagram_dump_media').all()
        enriched_images = _enrich_instagram_media(media_items)
        
        # Get filter parameters
        date_from = request.args.get('date_from', '')
        date_to = request.args.get('date_to', '')
        date_folder = request.args.get('date_folder', '')
        
        # Apply filters
        enriched_images = _filter_by_date(enriched_images, date_folder, date_from, date_to)
        
        # Sort by date folder descending
        enriched_images.sort(key=lambda x: x['instagram_folder'] or '', reverse=True)
        
        # Pagination
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        total = len(enriched_images)
        
        paginated = enriched_images[offset:offset+limit]
        
        return success_paginated(paginated, total, offset, limit)
    except Exception as e:
        return error_server_error(str(e))


@bp.route('/instagram/<path:image_key>/thumbnail', methods=['GET'])
@with_db
def get_instagram_thumbnail(db, image_key):
    """Get thumbnail for Instagram image."""
    from tinydb import Query
    
    try:
        Media = Query()
        media_items = db.table('instagram_dump_media').search(Media.media_key == image_key)
        
        if not media_items:
            return error_not_found('image')
        
        media = media_items[0]
        local_path = media.get('file_path')
        
        if not local_path or not os.path.exists(local_path):
            return error_not_found('file')
        
        return send_file(local_path, mimetype='image/jpeg')
    except Exception as e:
        return error_server_error(str(e))
```

**Step 2: Update remaining routes similarly**

Refactor catalog and dump-media routes to use @with_db and response utilities.

**Step 3: Run tests**

```bash
python3 -m pytest tests/ -v
```

Expected: All tests pass

**Step 4: Commit**

```bash
git add apps/visualizer/backend/api/images.py
git commit -m "refactor: use database decorator and response utilities"
```

---

## Phase 2: Frontend - String Constants

### Task 5: Expand Frontend String Constants

**Files:**
- Modify: `apps/visualizer/frontend/src/constants/strings.ts`

**Step 1: Add all missing string constants**

```typescript
// App
export const APP_TITLE = 'Lightroom Tagger'

// Navigation
export const NAV_DASHBOARD = 'Dashboard'
export const NAV_INSTAGRAM = 'Instagram'
export const NAV_MATCHING = 'Matching'
export const NAV_JOBS = 'Jobs'

// Status
export const STATUS_PENDING = 'pending'
export const STATUS_RUNNING = 'running'
export const STATUS_COMPLETED = 'completed'
export const STATUS_FAILED = 'failed'
export const STATUS_CANCELLED = 'cancelled'

// Status Display
export const STATUS_LABELS: Record<string, string> = {
  pending: 'Pending',
  running: 'Running',
  completed: 'Completed',
  failed: 'Failed',
  cancelled: 'Cancelled',
}

// Messages
export const MSG_LOADING = 'Loading...'
export const MSG_NO_JOBS = 'No jobs found. Start a job to see it here.'
export const MSG_NO_IMAGES = 'No images found.'
export const MSG_NO_MATCHES = 'No matches found. Run vision matching first.'
export const MSG_CONNECTED = 'Connected'
export const MSG_DISCONNECTED = 'Disconnected'
export const MSG_ERROR_PREFIX = 'Error:'
export const MSG_NO_EXIF_DATA = 'No EXIF data available'
export const MSG_CLICK_FOR_DETAILS = 'Click for details'
export const MSG_PAGE_OF = 'Page {current} of {total}'
export const MSG_SHOWING_RANGE = 'Showing {start}-{end} of {total}'

// Dashboard
export const DASHBOARD_CATALOG_IMAGES = 'Catalog Images'
export const DASHBOARD_INSTAGRAM_IMAGES = 'Instagram Images'
export const DASHBOARD_POSTED = 'Posted to Instagram'
export const DASHBOARD_MATCHES = 'Matches Found'
export const DASHBOARD_RECENT_JOBS = 'Recent Jobs'
export const DASHBOARD_NO_JOBS = 'No recent jobs'
export const DASHBOARD_START_JOB = 'Start a Job'

// Instagram Page
export const INSTAGRAM_DOWNLOADED = 'Downloaded Instagram Images'
export const INSTAGRAM_POST_URL = 'Post URL'
export const INSTAGRAM_FILE = 'File'
export const INSTAGRAM_CRAWLED = 'Crawled'

// Modal
export const MODAL_TITLE_IMAGE_DETAILS = 'Image Details'
export const MODAL_CLOSE = 'Close'
export const MODAL_VIEW_ON_INSTAGRAM = 'View on Instagram'
export const MODAL_OPEN_LOCAL_FILE = 'Open Local File'

// Metadata Sections
export const META_SECTION_BASIC_INFO = 'Basic Information'
export const META_SECTION_IMAGE_ANALYSIS = 'Image Analysis'
export const META_SECTION_EXIF_DATA = 'EXIF Data'
export const META_SECTION_CAPTION = 'Caption'
export const META_SECTION_FILE_LOCATION = 'File Location'

// Metadata Labels
export const LABEL_FILENAME = 'Filename'
export const LABEL_MEDIA_KEY = 'Media Key'
export const LABEL_SOURCE_FOLDER = 'Source Folder'
export const LABEL_DATE_FOLDER = 'Date Folder'
export const LABEL_ADDED = 'Added'
export const LABEL_VISUAL_HASH = 'Visual Hash (pHash)'
export const LABEL_GPS_COORDINATES = 'GPS Coordinates'
export const LABEL_DATE_TAKEN = 'Date Taken'
export const LABEL_CAMERA = 'Camera'
export const LABEL_LENS = 'Lens'
export const LABEL_ISO = 'ISO'
export const LABEL_APERTURE = 'Aperture'
export const LABEL_SHUTTER_SPEED = 'Shutter Speed'

// Hash explanation
export const HASH_EXPLANATION = 'This hash is used to detect visually identical images across your collection.'

// Pagination
export const PAGINATION_PREVIOUS = '← Previous'
export const PAGINATION_NEXT = 'Next →'

// Filters
export const FILTER_ALL_DATES = 'All dates'
export const FILTER_CLEAR = 'Clear'

// Matching Page
export const MATCHING_RESULTS = 'Matching Results'
export const MATCHING_RUN = 'Run Vision Matching'
export const MATCHING_RUNNING = 'Running matching...'
export const MATCHING_SUCCESS = 'Matching completed successfully'

// Actions
export const ACTION_REFRESH = 'Refresh'
export const ACTION_VIEW = 'View'
export const ACTION_RUN_MATCHING = 'Run Matching'

// API
export const API_DEFAULT_URL = '/api'
export const WS_DEFAULT_URL = ''

// Config
export const ITEMS_PER_PAGE = 48
```

**Step 2: Commit**

```bash
git add apps/visualizer/frontend/src/constants/strings.ts
git commit -m "refactor: expand string constants for all UI text"
```

---

## Phase 3: Frontend - Component Refactoring

### Task 6: Create Reusable Modal Components

**Files:**
- Create: `apps/visualizer/frontend/src/components/modal/Modal.tsx`
- Create: `apps/visualizer/frontend/src/components/modal/ModalHeader.tsx`
- Create: `apps/visualizer/frontend/src/components/modal/ModalFooter.tsx`
- Create: `apps/visualizer/frontend/src/components/modal/index.ts`

**Step 1: Create base Modal component**

```typescript
// apps/visualizer/frontend/src/components/modal/Modal.tsx
import { useEffect, ReactNode } from 'react'

interface ModalProps {
  children: ReactNode
  onClose: () => void
  maxWidth?: 'sm' | 'md' | 'lg' | 'xl' | '2xl' | '4xl'
}

const maxWidthClasses = {
  sm: 'max-w-sm',
  md: 'max-w-md',
  lg: 'max-w-lg',
  xl: 'max-w-xl',
  '2xl': 'max-w-2xl',
  '4xl': 'max-w-4xl',
}

export function Modal({ children, onClose, maxWidth = '4xl' }: ModalProps) {
  // Handle escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose()
      }
    }
    
    document.addEventListener('keydown', handleEscape)
    return () => document.removeEventListener('keydown', handleEscape)
  }, [onClose])
  
  // Prevent body scroll when modal is open
  useEffect(() => {
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = 'unset'
    }
  }, [])
  
  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      onClose()
    }
  }
  
  return (
    <div 
      className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4"
      onClick={handleBackdropClick}
    >
      <div className={`bg-white rounded-lg shadow-xl w-full max-h-[90vh] overflow-hidden flex flex-col ${maxWidthClasses[maxWidth]}`}>
        {children}
      </div>
    </div>
  )
}
```

**Step 2: Create ModalHeader component**

```typescript
// apps/visualizer/frontend/src/components/modal/ModalHeader.tsx
import { MODAL_CLOSE } from '../../constants/strings'

interface ModalHeaderProps {
  title: string
  onClose: () => void
}

export function ModalHeader({ title, onClose }: ModalHeaderProps) {
  return (
    <div className="flex items-center justify-between p-4 border-b border-gray-200">
      <h3 className="text-lg font-semibold text-gray-900">{title}</h3>
      <button
        onClick={onClose}
        className="text-gray-400 hover:text-gray-600 transition-colors"
        aria-label={MODAL_CLOSE}
      >
        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  )
}
```

**Step 3: Create ModalFooter component**

```typescript
// apps/visualizer/frontend/src/components/modal/ModalFooter.tsx
import { ReactNode } from 'react'

interface ModalFooterProps {
  children: ReactNode
}

export function ModalFooter({ children }: ModalFooterProps) {
  return (
    <div className="border-t border-gray-200 p-4 flex justify-end gap-2">
      {children}
    </div>
  )
}
```

**Step 4: Create index.ts for clean imports**

```typescript
// apps/visualizer/frontend/src/components/modal/index.ts
export { Modal } from './Modal'
export { ModalHeader } from './ModalHeader'
export { ModalFooter } from './ModalFooter'
```

**Step 5: Commit**

```bash
git add apps/visualizer/frontend/src/components/modal/
git commit -m "feat: create reusable modal components"
```

---

### Task 7: Create Metadata Section Components

**Files:**
- Create: `apps/visualizer/frontend/src/components/metadata/MetadataSection.tsx`
- Create: `apps/visualizer/frontend/src/components/metadata/MetadataRow.tsx`
- Create: `apps/visualizer/frontend/src/components/metadata/ExifDataSection.tsx`
- Create: `apps/visualizer/frontend/src/components/metadata/index.ts`

**Step 1: Create MetadataSection component**

```typescript
// apps/visualizer/frontend/src/components/metadata/MetadataSection.tsx
import { ReactNode } from 'react'

interface MetadataSectionProps {
  title: string
  children: ReactNode
}

export function MetadataSection({ title, children }: MetadataSectionProps) {
  return (
    <div>
      <h4 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">
        {title}
      </h4>
      <div className="bg-gray-50 rounded-lg p-4">
        {children}
      </div>
    </div>
  )
}
```

**Step 2: Create MetadataRow component**

```typescript
// apps/visualizer/frontend/src/components/metadata/MetadataRow.tsx
interface MetadataRowProps {
  label: string
  value: string
  monospace?: boolean
}

export function MetadataRow({ label, value, monospace = false }: MetadataRowProps) {
  return (
    <div className="flex flex-col sm:flex-row sm:justify-between sm:gap-4">
      <span className="text-sm text-gray-500">{label}</span>
      <span className={`text-sm text-gray-900 text-right ${monospace ? 'font-mono' : ''}`}>
        {value}
      </span>
    </div>
  )
}
```

**Step 3: Create ExifDataSection component**

```typescript
// apps/visualizer/frontend/src/components/metadata/ExifDataSection.tsx
import { MetadataSection } from './MetadataSection'
import { MetadataRow } from './MetadataRow'
import { 
  META_SECTION_EXIF_DATA,
  MSG_NO_EXIF_DATA,
  LABEL_GPS_COORDINATES,
  LABEL_DATE_TAKEN,
  LABEL_CAMERA,
  LABEL_LENS,
  LABEL_ISO,
  LABEL_APERTURE,
  LABEL_SHUTTER_SPEED,
} from '../../constants/strings'

interface ExifData {
  latitude?: number
  longitude?: number
  date_time_original?: string
  device_id?: string
  lens_model?: string
  iso?: number
  aperture?: string
  shutter_speed?: string
}

interface ExifDataSectionProps {
  exifData?: ExifData
}

export function ExifDataSection({ exifData }: ExifDataSectionProps) {
  const hasData = exifData && Object.keys(exifData).length > 0
  
  return (
    <MetadataSection title={META_SECTION_EXIF_DATA}>
      {hasData ? (
        <div className="space-y-2">
          {exifData?.latitude !== undefined && exifData?.longitude !== undefined && (
            <MetadataRow 
              label={LABEL_GPS_COORDINATES}
              value={`${exifData.latitude.toFixed(6)}, ${exifData.longitude.toFixed(6)}`}
            />
          )}
          {exifData?.date_time_original && (
            <MetadataRow label={LABEL_DATE_TAKEN} value={exifData.date_time_original} />
          )}
          {exifData?.device_id && (
            <MetadataRow label={LABEL_CAMERA} value={exifData.device_id} />
          )}
          {exifData?.lens_model && (
            <MetadataRow label={LABEL_LENS} value={exifData.lens_model} />
          )}
          {exifData?.iso !== undefined && (
            <MetadataRow label={LABEL_ISO} value={String(exifData.iso)} />
          )}
          {exifData?.aperture && (
            <MetadataRow label={LABEL_APERTURE} value={exifData.aperture} />
          )}
          {exifData?.shutter_speed && (
            <MetadataRow label={LABEL_SHUTTER_SPEED} value={exifData.shutter_speed} />
          )}
        </div>
      ) : (
        <p className="text-sm text-gray-500 italic">{MSG_NO_EXIF_DATA}</p>
      )}
    </MetadataSection>
  )
}
```

**Step 4: Commit**

```bash
git add apps/visualizer/frontend/src/components/metadata/
git commit -m "feat: create metadata section components"
```

---

### Task 8: Create Hooks for Modal and Pagination

**Files:**
- Create: `apps/visualizer/frontend/src/hooks/useModal.ts`
- Create: `apps/visualizer/frontend/src/hooks/usePagination.ts`
- Create: `apps/visualizer/frontend/src/hooks/index.ts`

**Step 1: Create useModal hook**

```typescript
// apps/visualizer/frontend/src/hooks/useModal.ts
import { useState, useCallback } from 'react'

interface UseModalReturn<T> {
  isOpen: boolean
  selectedItem: T | null
  open: (item: T) => void
  close: () => void
}

export function useModal<T>(): UseModalReturn<T> {
  const [isOpen, setIsOpen] = useState(false)
  const [selectedItem, setSelectedItem] = useState<T | null>(null)
  
  const open = useCallback((item: T) => {
    setSelectedItem(item)
    setIsOpen(true)
  }, [])
  
  const close = useCallback(() => {
    setIsOpen(false)
    setSelectedItem(null)
  }, [])
  
  return { isOpen, selectedItem, open, close }
}
```

**Step 2: Create usePagination hook**

```typescript
// apps/visualizer/frontend/src/hooks/usePagination.ts
import { useState, useCallback } from 'react'

interface PaginationState {
  offset: number
  limit: number
  currentPage: number
  totalPages: number
  hasMore: boolean
}

interface UsePaginationReturn {
  pagination: PaginationState
  goToPage: (page: number) => void
  nextPage: () => void
  prevPage: () => void
  reset: () => void
}

export function usePagination(
  itemsPerPage: number,
  totalItems: number
): UsePaginationReturn {
  const [offset, setOffset] = useState(0)
  
  const totalPages = Math.ceil(totalItems / itemsPerPage)
  const currentPage = Math.floor(offset / itemsPerPage) + 1
  const hasMore = (offset + itemsPerPage) < totalItems
  
  const goToPage = useCallback((page: number) => {
    setOffset((page - 1) * itemsPerPage)
  }, [itemsPerPage])
  
  const nextPage = useCallback(() => {
    if (hasMore) {
      setOffset(prev => prev + itemsPerPage)
    }
  }, [hasMore, itemsPerPage])
  
  const prevPage = useCallback(() => {
    setOffset(prev => Math.max(0, prev - itemsPerPage))
  }, [itemsPerPage])
  
  const reset = useCallback(() => {
    setOffset(0)
  }, [])
  
  return {
    pagination: {
      offset,
      limit: itemsPerPage,
      currentPage,
      totalPages,
      hasMore,
    },
    goToPage,
    nextPage,
    prevPage,
    reset,
  }
}
```

**Step 3: Commit**

```bash
git add apps/visualizer/frontend/src/hooks/
git commit -m "feat: add useModal and usePagination hooks"
```

---

### Task 9: Refactor InstagramPage.tsx

**Files:**
- Modify: `apps/visualizer/frontend/src/pages/InstagramPage.tsx`

**Step 1: Rewrite using new components, hooks, and constants**

Replace with refactored version that:
- Imports all string constants
- Uses useModal hook
- Uses extracted components (Modal, ModalHeader, ModalFooter, etc.)
- Uses new metadata components
- Removes inline strings

```typescript
import { useEffect, useState, useCallback } from 'react'
import { ImagesAPI, InstagramImage } from '../services/api'
import { 
  MSG_ERROR_PREFIX, 
  INSTAGRAM_DOWNLOADED,
  MODAL_TITLE_IMAGE_DETAILS,
  MODAL_CLOSE,
  MODAL_VIEW_ON_INSTAGRAM,
  MODAL_OPEN_LOCAL_FILE,
  META_SECTION_BASIC_INFO,
  META_SECTION_IMAGE_ANALYSIS,
  META_SECTION_CAPTION,
  META_SECTION_FILE_LOCATION,
  LABEL_FILENAME,
  LABEL_MEDIA_KEY,
  LABEL_SOURCE_FOLDER,
  LABEL_DATE_FOLDER,
  LABEL_ADDED,
  LABEL_VISUAL_HASH,
  HASH_EXPLANATION,
  PAGINATION_PREVIOUS,
  PAGINATION_NEXT,
  FILTER_ALL_DATES,
  FILTER_CLEAR,
  MSG_CLICK_FOR_DETAILS,
  MSG_PAGE_OF,
  MSG_SHOWING_RANGE,
  ITEMS_PER_PAGE,
} from '../constants/strings'
import { useModal } from '../hooks/useModal'
import { Modal, ModalHeader, ModalFooter } from '../components/modal'
import { MetadataSection, MetadataRow } from '../components/metadata'
import { ExifDataSection } from '../components/metadata/ExifDataSection'

export function InstagramPage() {
  const [images, setImages] = useState<InstagramImage[]>([])
  const [total, setTotal] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [offset, setOffset] = useState(0)
  const [pagination, setPagination] = useState({
    current_page: 1,
    total_pages: 1,
    has_more: false,
  })
  const [dateFilter, setDateFilter] = useState('')
  const [availableMonths, setAvailableMonths] = useState<string[]>([])
  const [isLoading, setIsLoading] = useState(false)
  
  const { isOpen: isModalOpen, selectedItem: selectedImage, open: openModal, close: closeModal } = useModal<InstagramImage>()

  const extractMonths = useCallback((imgs: InstagramImage[]) => {
    const months = new Set<string>()
    imgs.forEach(img => {
      if (img.instagram_folder) {
        months.add(img.instagram_folder)
      }
    })
    return Array.from(months).sort().reverse()
  }, [])

  const fetchImages = useCallback(async (newOffset: number = 0) => {
    setIsLoading(true)
    try {
      const params = {
        limit: ITEMS_PER_PAGE,
        offset: newOffset,
        ...(dateFilter && { date_folder: dateFilter }),
      }
      
      const data = await ImagesAPI.listInstagram(params)
      
      setImages(data.images)
      setTotal(data.total)
      setPagination(data.pagination)
      setOffset(newOffset)
      setError(null)
      
      if (availableMonths.length === 0 && data.images.length > 0) {
        const allData = await ImagesAPI.listInstagram({ limit: 10000, offset: 0 })
        setAvailableMonths(extractMonths(allData.images))
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setIsLoading(false)
    }
  }, [dateFilter, availableMonths.length, extractMonths])

  useEffect(() => {
    fetchImages(0)
  }, [fetchImages])

  const handlePrevPage = () => {
    if (offset > 0) {
      fetchImages(Math.max(0, offset - ITEMS_PER_PAGE))
    }
  }

  const handleNextPage = () => {
    if (pagination.has_more) {
      fetchImages(offset + ITEMS_PER_PAGE)
    }
  }

  const handleDateFilterChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setDateFilter(e.target.value)
    setOffset(0)
  }

  const clearDateFilter = () => {
    setDateFilter('')
    setOffset(0)
  }

  if (error) {
    return (
      <div className="text-center py-12">
        <p className="text-red-600">{MSG_ERROR_PREFIX} {error}</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <h2 className="text-xl font-bold text-gray-900">
          {INSTAGRAM_DOWNLOADED}
        </h2>
        
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <select
              value={dateFilter}
              onChange={handleDateFilterChange}
              className="text-sm border border-gray-300 rounded-md px-3 py-1.5 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">{FILTER_ALL_DATES}</option>
              {availableMonths.map(month => (
                <option key={month} value={month}>
                  {formatMonth(month)}
                </option>
              ))}
            </select>
            {dateFilter && (
              <button
                onClick={clearDateFilter}
                className="text-xs text-gray-500 hover:text-gray-700 underline"
              >
                {FILTER_CLEAR}
              </button>
            )}
          </div>
          
          <p className="text-sm text-gray-500">{total} images</p>
        </div>
      </div>

      {/* Grid */}
      {isLoading && images.length === 0 ? (
        <LoadingGrid />
      ) : (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
            {images.map((image) => (
              <InstagramImageCard 
                key={image.key} 
                image={image} 
                onClick={() => openModal(image)}
              />
            ))}
          </div>

          {pagination.total_pages > 1 && (
            <Pagination 
              pagination={pagination}
              total={total}
              offset={offset}
              onPrev={handlePrevPage}
              onNext={handleNextPage}
              isLoading={isLoading}
            />
          )}
        </>
      )}
      
      {isModalOpen && selectedImage && (
        <ImageDetailsModal image={selectedImage} onClose={closeModal} />
      )}
    </div>
  )
}

// Extracted sub-components...

function LoadingGrid() {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
      {Array.from({ length: 12 }).map((_, i) => (
        <ImageSkeleton key={i} />
      ))}
    </div>
  )
}

function ImageSkeleton() {
  return (
    <div className="border rounded-lg overflow-hidden bg-white">
      <div className="aspect-square bg-gray-200 animate-pulse" />
      <div className="p-2 space-y-1">
        <div className="h-3 bg-gray-200 rounded animate-pulse" />
        <div className="h-2 bg-gray-200 rounded w-2/3 animate-pulse" />
      </div>
    </div>
  )
}

function Pagination({ pagination, total, offset, onPrev, onNext, isLoading }: {
  pagination: { current_page: number; total_pages: number; has_more: boolean }
  total: number
  offset: number
  onPrev: () => void
  onNext: () => void
  isLoading: boolean
}) {
  return (
    <div className="flex items-center justify-between pt-6 border-t border-gray-200">
      <button
        onClick={onPrev}
        disabled={offset === 0 || isLoading}
        className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {PAGINATION_PREVIOUS}
      </button>
      
      <div className="text-sm text-gray-600">
        {MSG_PAGE_OF.replace('{current}', String(pagination.current_page)).replace('{total}', String(pagination.total_pages))}
        <span className="text-gray-400 mx-2">|</span>
        {MSG_SHOWING_RANGE
          .replace('{start}', String(offset + 1))
          .replace('{end}', String(Math.min(offset + ITEMS_PER_PAGE, total)))
          .replace('{total}', String(total))}
      </div>
      
      <button
        onClick={onNext}
        disabled={!pagination.has_more || isLoading}
        className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {PAGINATION_NEXT}
      </button>
    </div>
  )
}

function InstagramImageCard({ image, onClick }: { image: InstagramImage; onClick: () => void }) {
  const [loaded, setLoaded] = useState(false)
  const [error, setError] = useState(false)
  const thumbnailUrl = `/api/images/instagram/${encodeURIComponent(image.key)}/thumbnail`

  return (
    <div 
      className="border rounded-lg overflow-hidden hover:shadow-md transition-shadow group bg-white cursor-pointer"
      onClick={onClick}
    >
      <div className="aspect-square bg-gray-100 relative">
        {!loaded && !error && (
          <div className="absolute inset-0 bg-gray-200 animate-pulse" />
        )}
        {error && (
          <div className="absolute inset-0 flex items-center justify-center bg-gray-100">
            <span className="text-xs text-gray-400">Error</span>
          </div>
        )}
        <img
          src={thumbnailUrl}
          alt={image.filename}
          className={`absolute inset-0 w-full h-full object-cover transition-opacity duration-300 ${loaded ? 'opacity-100' : 'opacity-0'}`}
          loading="lazy"
          onLoad={() => setLoaded(true)}
          onError={() => setError(true)}
        />
        {image.total_in_post > 1 && (
          <div className="absolute top-1 right-1 bg-black/60 text-white text-xs px-1.5 py-0.5 rounded">
            {image.image_index}/{image.total_in_post}
          </div>
        )}
        <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
          <span className="text-white text-sm font-medium">{MSG_CLICK_FOR_DETAILS}</span>
        </div>
      </div>
      <div className="p-2">
        <div className="flex items-start justify-between gap-1">
          <div className="flex flex-col min-w-0">
            <p className="text-xs font-medium text-gray-900 truncate" title={image.instagram_folder}>
              {image.instagram_folder}
            </p>
            <p className="text-[10px] text-gray-500 uppercase truncate" title={image.source_folder}>
              {image.source_folder}
            </p>
          </div>
        </div>
        <p className="text-xs text-gray-400 mt-0.5">
          {new Date(image.crawled_at).toLocaleDateString()}
        </p>
      </div>
    </div>
  )
}

function ImageDetailsModal({ image, onClose }: { image: InstagramImage; onClose: () => void }) {
  const thumbnailUrl = `/api/images/instagram/${encodeURIComponent(image.key)}/thumbnail`
  
  return (
    <Modal onClose={onClose}>
      <ModalHeader title={MODAL_TITLE_IMAGE_DETAILS} onClose={onClose} />
      
      <div className="flex-1 overflow-auto p-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Image Preview */}
          <div className="space-y-4">
            <div className="aspect-square bg-gray-100 rounded-lg overflow-hidden">
              <img src={thumbnailUrl} alt={image.filename} className="w-full h-full object-contain" />
            </div>
            
            <div className="flex gap-2">
              {image.post_url ? (
                <a
                  href={image.post_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex-1 bg-blue-600 text-white text-center py-2 px-4 rounded-md hover:bg-blue-700 transition-colors text-sm font-medium"
                >
                  {MODAL_VIEW_ON_INSTAGRAM}
                </a>
              ) : (
                <button
                  onClick={() => window.open(`file://${image.local_path}`, '_blank')}
                  className="flex-1 bg-gray-600 text-white text-center py-2 px-4 rounded-md hover:bg-gray-700 transition-colors text-sm font-medium"
                >
                  {MODAL_OPEN_LOCAL_FILE}
                </button>
              )}
            </div>
          </div>
          
          {/* Metadata */}
          <div className="space-y-4">
            <MetadataSection title={META_SECTION_BASIC_INFO}>
              <div className="space-y-2">
                <MetadataRow label={LABEL_FILENAME} value={image.filename} />
                <MetadataRow label={LABEL_MEDIA_KEY} value={image.key} />
                <MetadataRow label={LABEL_SOURCE_FOLDER} value={image.source_folder} />
                <MetadataRow label={LABEL_DATE_FOLDER} value={image.instagram_folder} />
                <MetadataRow label={LABEL_ADDED} value={new Date(image.crawled_at).toLocaleString()} />
              </div>
            </MetadataSection>
            
            {image.image_hash && (
              <MetadataSection title={META_SECTION_IMAGE_ANALYSIS}>
                <MetadataRow label={LABEL_VISUAL_HASH} value={image.image_hash} monospace />
                <p className="text-xs text-gray-500 mt-2">{HASH_EXPLANATION}</p>
              </MetadataSection>
            )}
            
            <ExifDataSection exifData={image.exif_data} />
            
            {image.description && (
              <MetadataSection title={META_SECTION_CAPTION}>
                <p className="text-sm text-gray-800 whitespace-pre-wrap">{image.description}</p>
              </MetadataSection>
            )}
            
            <MetadataSection title={META_SECTION_FILE_LOCATION}>
              <code className="text-xs text-gray-600 break-all">{image.local_path}</code>
            </MetadataSection>
          </div>
        </div>
      </div>
      
      <ModalFooter>
        <button
          onClick={onClose}
          className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200 transition-colors"
        >
          {MODAL_CLOSE}
        </button>
      </ModalFooter>
    </Modal>
  )
}

function formatMonth(yyyymm: string): string {
  if (yyyymm.length !== 6) return yyyymm
  
  const year = yyyymm.substring(0, 4)
  const month = yyyymm.substring(4, 6)
  
  const date = new Date(parseInt(year), parseInt(month) - 1)
  return date.toLocaleDateString('en-US', { year: 'numeric', month: 'long' })
}
```

**Step 2: Run tests**

```bash
cd apps/visualizer/frontend
npm run lint
npm run test
```

**Step 3: Commit**

```bash
git add apps/visualizer/frontend/src/pages/InstagramPage.tsx
git commit -m "refactor: InstagramPage using new components, hooks, and constants"
```

---

## Summary

**Files Created:**
- `apps/visualizer/backend/constants/errors.py` - Error message constants
- `apps/visualizer/backend/utils/db.py` - Database context manager
- `apps/visualizer/backend/utils/responses.py` - Response utilities
- `apps/visualizer/backend/tests/test_db_utils.py` - DB utility tests
- `apps/visualizer/backend/tests/test_responses.py` - Response tests
- `apps/visualizer/frontend/src/components/modal/*` - Reusable modal components
- `apps/visualizer/frontend/src/components/metadata/*` - Metadata section components
- `apps/visualizer/frontend/src/hooks/useModal.ts` - Modal state hook
- `apps/visualizer/frontend/src/hooks/usePagination.ts` - Pagination hook

**Files Modified:**
- `apps/visualizer/backend/api/images.py` - Refactored to use utilities
- `apps/visualizer/backend/api/system.py` - Refactored to use utilities
- `apps/visualizer/frontend/src/constants/strings.ts` - Expanded constants
- `apps/visualizer/frontend/src/pages/InstagramPage.tsx` - Refactored with new patterns

**Benefits:**
1. **DRY**: Database operations, error responses, and UI components now reused
2. **KISS**: Modal component reduced from 300+ lines to ~50, split into focused components
3. **String Constants**: All UI text extracted, supports i18n in future
4. **Testability**: Smaller components and utilities easier to test
5. **Maintainability**: Changes to error messages or UI text in one place

---

**Plan complete and saved to:** `docs/plans/2026-03-22-code-refactoring-dry-kiss.md`

**Execution options:**

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

**Which approach?**