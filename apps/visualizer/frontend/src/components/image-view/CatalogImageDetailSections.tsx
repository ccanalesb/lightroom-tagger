import { useCallback, useEffect, useMemo, useState } from 'react'
import type { ImageDescription, ImageView } from '../../services/api'
import { DescriptionsAPI, JobsAPI, PerspectivesAPI, ProvidersAPI } from '../../services/api'
import type { Job } from '../../types/job'
import { DescriptionPanel } from '../DescriptionPanel/DescriptionPanel'
import { GenerateButton } from '../ui/description-atoms/GenerateButton'
import { ProviderModelSelect } from '../ui/ProviderModelSelect'
import { Badge } from '../ui/Badge'
import { MetadataRow } from '../ui/MetadataRow'
import ImageScoresPanel from '../catalog/ImageScoresPanel'
import { useJobSocket } from '../../hooks/useJobSocket'
import {
  ACTION_RUN_SCORING,
  ACTION_SCORING_IN_PROGRESS,
  DATE_NO_DATE,
  LABEL_DATE,
  LABEL_FILENAME,
  LABEL_SCORES_PERSPECTIVES,
  SCORES_FAILED_GENERIC,
  SCORES_FORCE_SAME_RUBRIC,
  SCORES_LOADING_PERSPECTIVES,
  SCORES_NO_ACTIVE_PERSPECTIVES,
  SECTION_IMAGE_SCORES,
} from '../../constants/strings'
import { ImagePerspectiveBreakdown } from './ImagePerspectiveBreakdown'

interface CatalogImageDetailSectionsProps {
  image: ImageView
  /** Called when the caller should re-fetch detail (after description or
   *  score jobs complete) so the modal header / breakdown stay in sync. */
  onDataChanged?: () => void
}

/**
 * Catalog-specific body sections for the consolidated ImageDetailModal.
 * Extracted near-verbatim from legacy `CatalogImageModal` so behavior
 * parity is preserved; differences:
 *
 *   - Accepts the canonical `ImageView` rather than `CatalogImage`.
 *   - Renders `ImagePerspectiveBreakdown` on top so every modal entry
 *     point (CONTEXT Q3) sees the identity breakdown when present.
 *   - Delegates header/close/wrapper chrome to the shell.
 */
export function CatalogImageDetailSections({
  image,
  onDataChanged,
}: CatalogImageDetailSectionsProps) {
  const [description, setDescription] = useState<ImageDescription | null>(null)
  const [loadingDesc, setLoadingDesc] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [descError, setDescError] = useState<string | null>(null)
  const [pendingJobId, setPendingJobId] = useState<string | null>(null)
  const [descProviderId, setDescProviderId] = useState<string | null>(null)
  const [descModelId, setDescModelId] = useState<string | null>(null)
  const [showModelOptions, setShowModelOptions] = useState(false)
  const [scoring, setScoring] = useState(false)
  const [scoreError, setScoreError] = useState<string | null>(null)
  const [pendingScoreJobId, setPendingScoreJobId] = useState<string | null>(null)
  const [scoresReloadToken, setScoresReloadToken] = useState(0)
  const [scoreForce, setScoreForce] = useState(false)
  const [activePerspectiveRows, setActivePerspectiveRows] = useState<
    { slug: string; display_name: string }[]
  >([])
  const [selectedPerspectiveSlugs, setSelectedPerspectiveSlugs] = useState<string[]>([])

  useEffect(() => {
    ProvidersAPI.getDefaults()
      .then((defaults) => {
        const d = defaults.description
        if (d?.provider) setDescProviderId(d.provider)
        if (d?.model) setDescModelId(d.model)
      })
      .catch(() => {})
  }, [])

  useEffect(() => {
    PerspectivesAPI.list({ active_only: true })
      .then((rows) => {
        const sorted = [...rows].sort((a, b) => a.slug.localeCompare(b.slug))
        setActivePerspectiveRows(
          sorted.map((r) => ({ slug: r.slug, display_name: r.display_name })),
        )
        setSelectedPerspectiveSlugs(sorted.map((r) => r.slug))
      })
      .catch(() => {})
  }, [image.key])

  useEffect(() => {
    let cancelled = false
    setLoadingDesc(true)
    setDescError(null)
    setDescription(null)

    DescriptionsAPI.get(image.key)
      .then((data) => {
        if (!cancelled) setDescription(data.description)
      })
      .catch((err) => {
        if (!cancelled) setDescError(String(err))
      })
      .finally(() => {
        if (!cancelled) setLoadingDesc(false)
      })

    return () => {
      cancelled = true
    }
  }, [image.key])

  const refreshDescription = useCallback(() => {
    DescriptionsAPI.get(image.key)
      .then((data) => setDescription(data.description))
      .catch(() => {})
  }, [image.key])

  const perspectiveLabels = useMemo(() => {
    const m: Record<string, string> = {}
    for (const r of activePerspectiveRows) m[r.slug] = r.display_name
    return m
  }, [activePerspectiveRows])

  useJobSocket({
    onJobUpdated: useCallback(
      (job: Job) => {
        if (pendingJobId && job.id === pendingJobId) {
          if (job.status === 'completed') {
            setPendingJobId(null)
            setGenerating(false)
            refreshDescription()
            onDataChanged?.()
          } else if (job.status === 'failed') {
            setPendingJobId(null)
            setGenerating(false)
            setDescError(job.error ?? 'Description generation failed')
          } else if (job.status === 'cancelled') {
            setPendingJobId(null)
            setGenerating(false)
          }
        }
        if (pendingScoreJobId && job.id === pendingScoreJobId) {
          if (job.status === 'completed') {
            setPendingScoreJobId(null)
            setScoring(false)
            setScoresReloadToken((t) => t + 1)
            onDataChanged?.()
          } else if (job.status === 'failed') {
            setPendingScoreJobId(null)
            setScoring(false)
            setScoreError(job.error ?? SCORES_FAILED_GENERIC)
          } else if (job.status === 'cancelled') {
            setPendingScoreJobId(null)
            setScoring(false)
          }
        }
      },
      [pendingJobId, pendingScoreJobId, refreshDescription, onDataChanged],
    ),
  })

  const handleGenerateDescription = useCallback(async () => {
    setGenerating(true)
    setDescError(null)
    try {
      const job = await JobsAPI.create('single_describe', {
        image_key: image.key,
        image_type: 'catalog',
        force: false,
        ...(descProviderId && { provider_id: descProviderId }),
        ...(descModelId && { provider_model: descModelId }),
      })
      setPendingJobId(job.id)
    } catch (err) {
      setDescError(String(err))
      setGenerating(false)
    }
  }, [image.key, descProviderId, descModelId])

  const handleRunScoring = useCallback(async () => {
    const slugs =
      selectedPerspectiveSlugs.length > 0
        ? selectedPerspectiveSlugs
        : activePerspectiveRows.map((r) => r.slug)
    if (slugs.length === 0) {
      setScoreError(SCORES_NO_ACTIVE_PERSPECTIVES)
      return
    }
    setScoring(true)
    setScoreError(null)
    try {
      const job = await JobsAPI.create('single_score', {
        image_key: image.key,
        image_type: 'catalog',
        perspective_slugs: slugs,
        force: scoreForce,
        ...(descProviderId && { provider_id: descProviderId }),
        ...(descModelId && { provider_model: descModelId }),
      })
      setPendingScoreJobId(job.id)
    } catch (err) {
      setScoreError(String(err))
      setScoring(false)
    }
  }, [
    image.key,
    selectedPerspectiveSlugs,
    activePerspectiveRows,
    scoreForce,
    descProviderId,
    descModelId,
  ])

  const dateDisplay = image.date_taken
    ? new Date(image.date_taken).toLocaleString()
    : DATE_NO_DATE
  const keywords = Array.isArray(image.keywords) ? image.keywords : []

  return (
    <div className="space-y-6">
      <ImagePerspectiveBreakdown
        perspectives={image.identity_per_perspective}
        aggregateScore={image.identity_aggregate_score ?? null}
        perspectivesCovered={image.identity_perspectives_covered}
      />

      <div className="space-y-3">
        <MetadataRow label={LABEL_FILENAME} value={image.filename ?? image.key} />
        {image.title ? <MetadataRow label="Title" value={image.title} /> : null}
        <MetadataRow label={LABEL_DATE} value={dateDisplay} />
        {image.filepath ? <MetadataRow label="Path" value={image.filepath} mono /> : null}
        {image.width && image.height ? (
          <MetadataRow
            label="Dimensions"
            value={`${image.width} × ${image.height}`}
          />
        ) : null}
      </div>

      {image.caption ? (
        <div className="p-4 bg-surface rounded-base border border-border">
          <h3 className="text-sm font-medium text-text mb-2">Caption</h3>
          <p className="text-sm text-text-secondary">{image.caption}</p>
        </div>
      ) : null}

      {keywords.length > 0 ? (
        <div className="p-4 bg-surface rounded-base border border-border">
          <h3 className="text-sm font-medium text-text mb-2">Keywords</h3>
          <div className="flex flex-wrap gap-2">
            {keywords.map((keyword, idx) => (
              <Badge key={idx} variant="default">
                {keyword}
              </Badge>
            ))}
          </div>
        </div>
      ) : null}

      <div className="p-4 bg-surface rounded-base border border-border">
        <h3 className="text-sm font-medium text-text mb-2">AI description</h3>
        {loadingDesc ? (
          <p className="text-sm text-text-tertiary">Loading description…</p>
        ) : null}
        {descError ? <p className="text-sm text-error">{descError}</p> : null}
        {generating ? (
          <div className="flex items-center gap-2 py-2">
            <Spinner />
            <span className="text-sm text-text-secondary">Generating description…</span>
          </div>
        ) : null}
        <DescriptionPanel description={description} compact />
        <div className="mt-3 flex items-center justify-between">
          <button
            type="button"
            onClick={() => setShowModelOptions((v) => !v)}
            className="text-xs text-text-tertiary hover:text-text-secondary transition-colors"
          >
            {showModelOptions ? 'Hide options' : 'Model options'}
          </button>
          <GenerateButton
            hasDescription={Boolean(description?.summary)}
            generating={generating}
            onClick={() => {
              void handleGenerateDescription()
            }}
          />
        </div>
        {showModelOptions ? (
          <ProviderModelSelect
            providerId={descProviderId}
            modelId={descModelId}
            onChange={(pid, mid) => {
              setDescProviderId(pid)
              setDescModelId(mid)
            }}
            className="mt-3"
          />
        ) : null}
      </div>

      <div className="p-4 bg-surface rounded-base border border-border">
        <h3 className="text-sm font-medium text-text mb-2">{SECTION_IMAGE_SCORES}</h3>
        <ImageScoresPanel
          imageKey={image.key}
          imageType="catalog"
          reloadToken={scoresReloadToken}
          perspectiveLabels={perspectiveLabels}
        />
        {scoring ? (
          <div className="flex items-center gap-2 py-2 mt-2">
            <Spinner />
            <span className="text-sm text-text-secondary">
              {ACTION_SCORING_IN_PROGRESS}
            </span>
          </div>
        ) : null}
        {scoreError ? <p className="text-sm text-error mt-2">{scoreError}</p> : null}
        <div className="mt-3 space-y-2">
          <span className="block text-xs font-medium text-text">
            {LABEL_SCORES_PERSPECTIVES}
          </span>
          <div className="flex flex-col gap-2 max-h-32 overflow-y-auto border border-border rounded-base p-2 bg-bg">
            {activePerspectiveRows.length === 0 ? (
              <span className="text-xs text-text-secondary">
                {SCORES_LOADING_PERSPECTIVES}
              </span>
            ) : (
              activePerspectiveRows.map((p) => (
                <label
                  key={p.slug}
                  className="flex items-center gap-2 text-xs text-text cursor-pointer"
                >
                  <input
                    type="checkbox"
                    checked={selectedPerspectiveSlugs.includes(p.slug)}
                    onChange={() => {
                      setSelectedPerspectiveSlugs((prev) =>
                        prev.includes(p.slug)
                          ? prev.filter((s) => s !== p.slug)
                          : [...prev, p.slug].sort((a, b) => a.localeCompare(b)),
                      )
                    }}
                    className="w-3.5 h-3.5 rounded border-border text-accent focus:ring-accent focus:ring-offset-0"
                  />
                  <span>
                    {p.display_name}{' '}
                    <span className="text-text-secondary">({p.slug})</span>
                  </span>
                </label>
              ))
            )}
          </div>
          <div className="flex items-center gap-2 pt-1">
            <input
              type="checkbox"
              id="catalog-score-force"
              checked={scoreForce}
              onChange={(e) => setScoreForce(e.target.checked)}
              className="w-3.5 h-3.5 rounded border-border text-accent focus:ring-accent focus:ring-offset-0"
            />
            <label
              htmlFor="catalog-score-force"
              className="text-xs text-text cursor-pointer"
            >
              {SCORES_FORCE_SAME_RUBRIC}
            </label>
          </div>
          <div className="flex justify-end pt-1">
            <button
              type="button"
              disabled={scoring}
              onClick={() => {
                void handleRunScoring()
              }}
              className="flex-shrink-0 px-3 py-1 rounded text-xs font-medium transition-colors bg-accent text-white hover:opacity-90 disabled:opacity-50"
            >
              {scoring ? ACTION_SCORING_IN_PROGRESS : ACTION_RUN_SCORING}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

function Spinner() {
  return (
    <svg className="animate-spin h-4 w-4 text-accent" viewBox="0 0 24 24" fill="none">
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
      />
    </svg>
  )
}
