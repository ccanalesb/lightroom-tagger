# Frontend Redesign Fixes

**Date**: 2026-04-09  
**Status**: Active

## Issues Found

### Critical (Removed Functionality)
1. **Job Queue**: No clickable rows, no detail modal, no cancel functionality
2. **Providers Tab**: Complete removal of provider management (cards, fallback order, model management)
3. **Modal Background**: Dark mode visibility issues with modal background
4. **Button Legibility**: Contrast issues with buttons in Processing tabs

### Design/UX Issues
5. **Catalog Tab**: Empty placeholder when catalog data may be available
6. **Navigation**: Potential active state visibility issues in dark mode

---

## Fix Plan

### Task 1: Restore Job Detail Modal & Clickable Rows

**Files:**
- Copy OLD: `git show HEAD~13:apps/visualizer/frontend/src/components/jobs/JobDetailModal.tsx > /tmp/JobDetailModal.old.tsx`
- Create: `apps/visualizer/frontend/src/components/jobs/JobDetailModal.tsx`
- Modify: `apps/visualizer/frontend/src/components/processing/JobQueueTab.tsx`
- Add strings: `apps/visualizer/frontend/src/constants/strings.ts`

**Step 1: Copy old JobDetailModal implementation**

```bash
git show HEAD~13:apps/visualizer/frontend/src/components/jobs/JobDetailModal.tsx > apps/visualizer/frontend/src/components/jobs/JobDetailModal.tsx
```

**Step 2: Update JobDetailModal to use new design system**

Update imports and classes in `JobDetailModal.tsx`:
- Replace old color classes with semantic tokens
- Use new Card, Button, Badge components
- Apply rounded-base, rounded-card, shadow-deep
- Use text-text, bg-bg, border-border classes

**Step 3: Make JobQueueTab rows clickable**

Update `apps/visualizer/frontend/src/components/processing/JobQueueTab.tsx`:

```typescript
import { useState, useEffect, useCallback } from 'react';
import { useJobSocket } from '../../hooks/useJobSocket';
import { JobsAPI } from '../../services/api';
import type { Job } from '../../types/job';
import { Card, CardHeader, CardTitle, CardContent } from '../ui/Card';
import { Button } from '../ui/Button';
import { Badge } from '../ui/Badge';
import { JobDetailModal } from '../jobs/JobDetailModal';
import { BADGE_MATCHED, BADGE_DESCRIBED, BADGE_PROCESSED } from '../../constants/strings';

export function JobQueueTab() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  const [cancellingId, setCancellingId] = useState<string | null>(null);

  const cancelJob = async (jobId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setCancellingId(jobId);
    try {
      await JobsAPI.cancel(jobId);
      setJobs(prev => prev.map(job =>
        job.id === jobId ? { ...job, status: 'cancelled' as const } : job
      ));
    } catch (err) {
      alert(`Failed to cancel job: ${err instanceof Error ? err.message : 'Unknown error'}`);
    } finally {
      setCancellingId(null);
    }
  };

  useEffect(() => {
    let mounted = true;
    async function fetchJobs() {
      try {
        const data = await JobsAPI.list();
        if (mounted) {
          setJobs(data.jobs);
        }
      } catch (err) {
        console.error('Failed to load jobs:', err);
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    }
    fetchJobs();
    return () => { mounted = false };
  }, []);

  const handleJobCreated = useCallback((job: Job) => {
    setJobs(prev => [job, ...prev]);
  }, []);

  const handleJobUpdated = useCallback((updatedJob: Job) => {
    setJobs(prev => prev.map(job =>
      job.id === updatedJob.id ? updatedJob : job
    ));
    if (selectedJob?.id === updatedJob.id) {
      setSelectedJob(updatedJob);
    }
  }, [selectedJob]);

  const { connected } = useJobSocket({
    onJobCreated: handleJobCreated,
    onJobUpdated: handleJobUpdated,
  });

  const getStatusVariant = (status: Job['status']) => {
    switch (status) {
      case 'completed': return 'success';
      case 'failed': return 'error';
      case 'running': return 'accent';
      case 'cancelled': return 'warning';
      default: return 'default';
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${connected ? 'bg-success' : 'bg-error'}`} />
          <span className="text-sm text-text-secondary">
            {connected ? 'Connected' : 'Disconnected'}
          </span>
        </div>
        <Button variant="secondary" size="sm" onClick={() => window.location.reload()}>
          Refresh
        </Button>
      </div>

      {loading ? (
        <Card padding="lg">
          <div className="text-center py-8 text-text-secondary">Loading jobs...</div>
        </Card>
      ) : jobs.length === 0 ? (
        <Card padding="lg">
          <div className="text-center py-12">
            <svg className="mx-auto h-12 w-12 text-text-tertiary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
            </svg>
            <h3 className="mt-2 text-sm font-medium text-text">No jobs</h3>
            <p className="mt-1 text-sm text-text-secondary">
              Start a matching or description job to see it here
            </p>
          </div>
        </Card>
      ) : (
        <Card padding="none">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border bg-surface">
                  <th className="px-6 py-3 text-left text-xs font-medium text-text-secondary uppercase tracking-wider">Type</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-text-secondary uppercase tracking-wider">Status</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-text-secondary uppercase tracking-wider">Created</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-text-secondary uppercase tracking-wider">Progress</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-text-secondary uppercase tracking-wider">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {jobs.map((job) => (
                  <tr
                    key={job.id}
                    onClick={() => setSelectedJob(job)}
                    className="hover:bg-surface cursor-pointer transition-colors"
                  >
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm font-medium text-text">{job.type}</div>
                      <div className="text-xs text-text-tertiary font-mono">{job.id.slice(0, 8)}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <Badge variant={getStatusVariant(job.status)}>{job.status}</Badge>
                    </td>
                    <td className="px-6 py-4 text-sm text-text-secondary whitespace-nowrap">
                      {new Date(job.created_at).toLocaleString()}
                    </td>
                    <td className="px-6 py-4">
                      {job.status === 'running' && (
                        <div className="w-full bg-surface rounded-full h-2">
                          <div
                            className="bg-accent h-2 rounded-full transition-all duration-300"
                            style={{ width: `${(job.progress || 0) * 100}%` }}
                          />
                        </div>
                      )}
                    </td>
                    <td className="px-6 py-4 text-right text-sm">
                      {(job.status === 'pending' || job.status === 'running') && (
                        <Button
                          variant="danger"
                          size="sm"
                          onClick={(e) => cancelJob(job.id, e)}
                          disabled={cancellingId === job.id}
                        >
                          {cancellingId === job.id ? 'Cancelling...' : 'Cancel'}
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {selectedJob && (
        <JobDetailModal job={selectedJob} onClose={() => setSelectedJob(null)} />
      )}
    </div>
  );
}
```

**Step 4: Commit**

```bash
git add apps/visualizer/frontend/src/components/jobs/JobDetailModal.tsx apps/visualizer/frontend/src/components/processing/JobQueueTab.tsx
git commit -m "fix(frontend): restore job detail modal and clickable job rows"
```

---

### Task 2: Restore Provider Management UI

**Files:**
- Copy OLD providers components from git history
- Create: `apps/visualizer/frontend/src/components/providers/` directory
- Modify: `apps/visualizer/frontend/src/components/processing/ProvidersTab.tsx`
- Add: `apps/visualizer/frontend/src/hooks/useProviders.ts`

**Step 1: Extract old provider components**

```bash
mkdir -p apps/visualizer/frontend/src/components/providers
git show HEAD~13:apps/visualizer/frontend/src/components/providers/ProviderCard.tsx > apps/visualizer/frontend/src/components/providers/ProviderCard.tsx
git show HEAD~13:apps/visualizer/frontend/src/components/providers/FallbackOrderPanel.tsx > apps/visualizer/frontend/src/components/providers/FallbackOrderPanel.tsx
git show HEAD~13:apps/visualizer/frontend/src/components/providers/index.ts > apps/visualizer/frontend/src/components/providers/index.ts
git show HEAD~13:apps/visualizer/frontend/src/hooks/useProviders.ts > apps/visualizer/frontend/src/hooks/useProviders.ts
```

**Step 2: Update provider components to use new design system**

For each file in `components/providers/`:
- Update all color classes to semantic tokens (bg-gray-50 → bg-surface, text-gray-700 → text-text, etc.)
- Replace button/card classes with new Button and Card components
- Use rounded-base, shadow-card, border-border
- Apply text-text-secondary for labels, text-text-tertiary for hints

**Step 3: Replace ProvidersTab placeholder with full functionality**

Replace `apps/visualizer/frontend/src/components/processing/ProvidersTab.tsx`:

```typescript
import { useState, useEffect, useCallback } from 'react';
import { ProvidersAPI, type ProviderModel } from '../../services/api';
import { useProviders } from '../../hooks/useProviders';
import { ProviderCard, FallbackOrderPanel } from '../providers';
import { Card } from '../ui/Card';

export function ProvidersTab() {
  const { providers, fallbackOrder, loading, error, updateFallbackOrder } = useProviders();
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [modelCache, setModelCache] = useState<Record<string, ProviderModel[]>>({});

  const refreshModelsForProvider = useCallback(async (providerId: string) => {
    const models = await ProvidersAPI.listModels(providerId);
    setModelCache(previous => ({ ...previous, [providerId]: models }));
  }, []);

  useEffect(() => {
    if (!expandedId || modelCache[expandedId]) return;
    refreshModelsForProvider(expandedId).catch(console.error);
  }, [expandedId, modelCache, refreshModelsForProvider]);

  const handleAddModel = useCallback(
    async (providerId: string, model: { id: string; name: string; vision: boolean }) => {
      await ProvidersAPI.addModel(providerId, model);
      await refreshModelsForProvider(providerId);
    },
    [refreshModelsForProvider],
  );

  const handleRemoveModel = useCallback(
    async (providerId: string, modelId: string) => {
      await ProvidersAPI.removeModel(providerId, modelId);
      await refreshModelsForProvider(providerId);
    },
    [refreshModelsForProvider],
  );

  if (loading) {
    return (
      <Card padding="lg">
        <div className="text-center py-8 text-text-secondary">Loading providers...</div>
      </Card>
    );
  }

  if (error) {
    return (
      <Card padding="lg">
        <div className="text-center py-8 text-error">Error: {error}</div>
      </Card>
    );
  }

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h3 className="text-card-title text-text mb-2">AI Model Providers</h3>
        <p className="text-sm text-text-secondary">
          Configure vision model providers and manage fallback order
        </p>
      </div>

      <div className="space-y-3">
        {providers.map(provider => (
          <ProviderCard
            key={provider.id}
            provider={provider}
            models={modelCache[provider.id] ?? []}
            expanded={expandedId === provider.id}
            onToggle={() => setExpandedId(previous => (previous === provider.id ? null : provider.id))}
            onAddModel={model => handleAddModel(provider.id, model)}
            onRemoveModel={modelId => {
              handleRemoveModel(provider.id, modelId).catch(console.error);
            }}
          />
        ))}
      </div>

      <FallbackOrderPanel
        providers={providers}
        order={fallbackOrder}
        onReorder={order => {
          updateFallbackOrder(order).catch(console.error);
        }}
      />
    </div>
  );
}
```

**Step 4: Commit**

```bash
git add apps/visualizer/frontend/src/components/providers/ apps/visualizer/frontend/src/components/processing/ProvidersTab.tsx apps/visualizer/frontend/src/hooks/useProviders.ts
git commit -m "fix(frontend): restore full provider management UI with cards and fallback ordering"
```

---

### Task 3: Fix Modal Background & Dark Mode Visibility

**Files:**
- Modify: `apps/visualizer/frontend/src/components/instagram/ImageDetailsModal.tsx`

**Step 1: Enhance modal backdrop and container styling**

Update modal backdrop to be more visible:

```typescript
// In ImageDetailsModal.tsx, update the backdrop div:
<div
  className="fixed inset-0 z-50 flex items-center justify-center p-4"
  style={{ backgroundColor: 'rgba(0, 0, 0, 0.75)' }}
  onClick={onClose}
>
```

Add explicit background to modal container:

```typescript
// Update modal container:
<div
  className="relative w-full max-w-4xl max-h-[90vh] rounded-card shadow-deep overflow-hidden"
  style={{ backgroundColor: 'var(--color-background)' }}
  onClick={(e) => e.stopPropagation()}
>
```

**Step 2: Verify Card components render backgrounds**

Update `apps/visualizer/frontend/src/components/ui/Card/Card.tsx`:

```typescript
export function Card({
  children,
  className = '',
  onClick,
  hoverable = false,
  padding = 'md',
}: CardProps) {
  return (
    <div
      className={`
        bg-bg border border-border rounded-card
        shadow-card transition-all duration-150
        ${paddingClasses[padding]}
        ${hoverable || onClick ? 'hover:shadow-deep hover:border-border-strong cursor-pointer' : ''}
        ${className}
      `.trim()}
      onClick={onClick}
      style={{ backgroundColor: 'var(--color-background)' }} // Explicit fallback
    >
      {children}
    </div>
  );
}
```

**Step 3: Commit**

```bash
git add apps/visualizer/frontend/src/components/instagram/ImageDetailsModal.tsx apps/visualizer/frontend/src/components/ui/Card/Card.tsx
git commit -m "fix(frontend): improve modal backdrop visibility and card backgrounds in dark mode"
```

---

### Task 4: Fix Button Contrast & Legibility

**Files:**
- Modify: `apps/visualizer/frontend/src/components/ui/Button/Button.tsx`
- Modify: `apps/visualizer/frontend/src/index.css`

**Step 1: Enhance button contrast for dark mode**

Update button variant classes:

```typescript
const variantClasses: Record<ButtonVariant, string> = {
  primary: 'bg-accent text-white hover:bg-accent-hover border border-accent font-semibold',
  secondary: 'bg-surface text-text hover:bg-surface-hover border border-border font-medium',
  ghost: 'bg-transparent text-text hover:bg-surface border border-transparent',
  danger: 'bg-error text-white hover:opacity-90 border border-error font-semibold',
};
```

**Step 2: Add focus-visible for better keyboard navigation**

```typescript
<button
  className={`
    ${variantClasses[variant]}
    ${sizeClasses[size]}
    ${fullWidth ? 'w-full' : ''}
    rounded-base transition-all duration-150
    focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2
    disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-accent disabled:hover:opacity-50
    ${className}
  `.trim()}
  disabled={disabled}
  {...props}
>
  {children}
</button>
```

**Step 3: Verify accent color contrast in dark mode**

Check `apps/visualizer/frontend/src/index.css` dark mode accent:

```css
.dark {
  --color-background: #191919;
  --color-surface: #31302e;
  --color-surface-hover: #3d3b38;
  --color-text-primary: #f7f6f5;
  --color-text-secondary: #9b9a97;
  --color-text-tertiary: #6f6e69;
  --color-border: rgba(255,255,255,0.1);
  --color-border-strong: rgba(255,255,255,0.15);
  --color-accent: #4A9EFF; /* Lighter blue for better contrast */
  --color-accent-hover: #7AB8FF;
  --color-accent-light: rgba(74, 158, 255, 0.15);
  --color-success: #2a9d99;
  --color-warning: #ff8c42;
  --color-error: #ff6b6b;
}
```

**Step 4: Commit**

```bash
git add apps/visualizer/frontend/src/components/ui/Button/Button.tsx apps/visualizer/frontend/src/index.css
git commit -m "fix(frontend): improve button contrast and legibility in dark mode"
```

---

### Task 5: Improve Catalog Tab (Future Data)

**Files:**
- Modify: `apps/visualizer/frontend/src/components/images/CatalogTab.tsx`

**Step 1: Add better placeholder with API check**

```typescript
import { useEffect, useState } from 'react';
import { Card, CardContent } from '../ui/Card';
import { Button } from '../ui/Button';
import { ImagesAPI } from '../../services/api';

export function CatalogTab() {
  const [checking, setChecking] = useState(true);
  const [hasCache, setHasCache] = useState(false);

  useEffect(() => {
    async function checkCache() {
      try {
        // Check if catalog cache exists
        const response = await fetch('/api/catalog/status');
        const data = await response.json();
        setHasCache(data.cached);
      } catch (err) {
        console.error('Failed to check catalog status:', err);
      } finally {
        setChecking(false);
      }
    }
    checkCache();
  }, []);

  if (checking) {
    return (
      <Card padding="lg">
        <div className="text-center py-8 text-text-secondary">Checking catalog status...</div>
      </Card>
    );
  }

  return (
    <Card padding="lg">
      <div className="text-center py-12">
        <svg className="mx-auto h-12 w-12 text-text-tertiary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
        </svg>
        <h3 className="mt-2 text-sm font-medium text-text">Catalog Browser</h3>
        <p className="mt-1 text-sm text-text-secondary mb-4">
          {hasCache 
            ? 'Catalog browsing interface coming soon. Catalog cache is ready.'
            : 'Catalog needs to be prepared first. Run a prepare_catalog job from Processing.'}
        </p>
        {!hasCache && (
          <Button variant="primary" onClick={() => window.location.href = '/processing'}>
            Go to Processing
          </Button>
        )}
      </div>
    </Card>
  );
}
```

**Step 2: Commit**

```bash
git add apps/visualizer/frontend/src/components/images/CatalogTab.tsx
git commit -m "feat(frontend): improve catalog tab with cache status check"
```

---

### Task 6: Fix Navigation Active State Contrast

**Files:**
- Modify: `apps/visualizer/frontend/src/components/Layout.tsx`

**Step 1: Enhance active nav link visibility**

Update NavLink className for better contrast:

```typescript
className={({ isActive }) =>
  `px-3 py-1.5 rounded-base text-sm font-medium transition-all duration-150
  ${isActive 
    ? 'bg-accent text-white shadow-sm' // Stronger active state
    : 'text-text-secondary hover:bg-surface hover:text-text'
  }`
}
```

**Step 2: Commit**

```bash
git add apps/visualizer/frontend/src/components/Layout.tsx
git commit -m "fix(frontend): improve navigation active state contrast"
```

---

## Testing Checklist

After implementing all fixes:

- [ ] Job Queue: Click job rows → modal opens with details
- [ ] Job Queue: Cancel button works for running jobs
- [ ] Providers: ProviderCard expands/collapses
- [ ] Providers: Add/remove models works
- [ ] Providers: Fallback order can be reordered
- [ ] Modal: Background is visible in dark mode
- [ ] Modal: Content is readable in both themes
- [ ] Buttons: Primary buttons have good contrast
- [ ] Buttons: All buttons are legible in dark mode
- [ ] Navigation: Active page is clearly visible
- [ ] Catalog: Shows appropriate message based on cache status
- [ ] Dark/Light toggle: All components transition smoothly

---

## Build & Deploy

```bash
cd apps/visualizer/frontend
npm run build
# Verify no errors
```
