import { Suspense, useCallback, useEffect, useMemo, useState } from 'react'
import type { Job } from '../../types/job'
import { JobsAPI, PerspectivesAPI, ProvidersAPI, ScoresAPI } from '../../services/api'
import { useJobSocket } from '../../hooks/useJobSocket'
import { GenerateButton } from '../ui/description-atoms/GenerateButton'
import { ProviderModelSelect } from '../ui/ProviderModelSelect'
import { Spinner } from '../ui/Spinner'
import {
  ACTION_SCORING_IN_PROGRESS,
  IMAGE_DETAILS_PERSPECTIVE_ANALYSIS,
} from '../../constants/strings'
import { useQuery } from '../../data'
import ImageScoresPanel from './ImageScoresPanel'

interface AIPerspectiveSectionProps {
  imageKey: string
  imageType: 'catalog' | 'instagram'
  /** Called after a scoring job completes so the parent modal can refetch header metadata. */
  onDataChanged?: () => void
}

function AIPerspectiveSectionLoaded({
  imageKey,
  imageType,
  onDataChanged,
}: AIPerspectiveSectionProps) {
  const defaults = useQuery(['providers.defaults'] as const, () => ProvidersAPI.getDefaults())
  const perspectives = useQuery(['perspectives', 'list', 'active'] as const, () =>
    PerspectivesAPI.list({ active_only: true }),
  )

  const [error, setError] = useState<string | null>(null)
  const [generating, setGenerating] = useState(false)
  const [pendingJobId, setPendingJobId] = useState<string | null>(null)
  const [providerId, setProviderId] = useState<string | null>(null)
  const [modelId, setModelId] = useState<string | null>(null)
  const [showModelOptions, setShowModelOptions] = useState(false)
  const [reloadToken, setReloadToken] = useState(0)

  const scoresPayload = useQuery(
    ['scores', 'current', imageKey, imageType, reloadToken] as const,
    () => ScoresAPI.getCurrent(imageKey, { image_type: imageType }),
  )

  const hasScores = (scoresPayload.current?.length ?? 0) > 0

  const perspectiveLabels = useMemo(() => {
    const map: Record<string, string> = {}
    for (const row of perspectives) {
      map[row.slug] = row.display_name
    }
    return map
  }, [perspectives])

  useEffect(() => {
    const d = defaults.description
    if (d?.provider) setProviderId((p) => p ?? d.provider)
    if (d?.model) setModelId((m) => m ?? d.model)
  }, [defaults])

  const refreshScores = useCallback(() => {
    setReloadToken((n) => n + 1)
  }, [])

  useJobSocket({
    onJobUpdated: useCallback(
      (job: Job) => {
        if (!pendingJobId || job.id !== pendingJobId) return
        if (job.status === 'completed') {
          setPendingJobId(null)
          setGenerating(false)
          refreshScores()
          onDataChanged?.()
        } else if (job.status === 'failed') {
          setPendingJobId(null)
          setGenerating(false)
          setError(job.error ?? 'Scoring failed')
        } else if (job.status === 'cancelled') {
          setPendingJobId(null)
          setGenerating(false)
        }
      },
      [pendingJobId, refreshScores, onDataChanged],
    ),
  })

  const handleGenerate = useCallback(async () => {
    setGenerating(true)
    setError(null)
    try {
      const job = await JobsAPI.create('single_score', {
        image_key: imageKey,
        image_type: imageType,
        force: true,
        ...(providerId && { provider_id: providerId }),
        ...(modelId && { provider_model: modelId }),
      })
      setPendingJobId(job.id)
    } catch (err) {
      setError(String(err))
      setGenerating(false)
    }
  }, [imageKey, imageType, providerId, modelId])

  return (
    <div className="p-4 bg-surface rounded-base border border-border">
      <h3 className="text-sm font-medium text-text mb-2">{IMAGE_DETAILS_PERSPECTIVE_ANALYSIS}</h3>
      {error ? <p className="text-sm text-error">{error}</p> : null}
      {generating ? (
        <div className="flex items-center gap-2 py-2">
          <Spinner />
          <span className="text-sm text-text-secondary">{ACTION_SCORING_IN_PROGRESS}</span>
        </div>
      ) : null}
      <ImageScoresPanel
        imageKey={imageKey}
        imageType={imageType}
        reloadToken={reloadToken}
        perspectiveLabels={perspectiveLabels}
      />
      <div className="mt-3 flex items-center justify-between">
        <button
          type="button"
          onClick={() => setShowModelOptions((v) => !v)}
          className="text-xs text-text-tertiary hover:text-text-secondary transition-colors"
        >
          {showModelOptions ? 'Hide options' : 'Model options'}
        </button>
        <GenerateButton
          hasDescription={hasScores}
          generating={generating}
          onClick={() => {
            void handleGenerate()
          }}
        />
      </div>
      {showModelOptions ? (
        <ProviderModelSelect
          providerId={providerId}
          modelId={modelId}
          onChange={(pid, mid) => {
            setProviderId(pid)
            setModelId(mid)
          }}
          className="mt-3"
        />
      ) : null}
    </div>
  )
}

/**
 * Perspective scoring section for the catalog image detail modal. Renders
 * current scores from `image_scores` plus a per-photo regenerate control.
 */
export function AIPerspectiveSection(props: AIPerspectiveSectionProps) {
  return (
    <Suspense
      fallback={
        <div className="p-4 bg-surface rounded-base border border-border">
          <h3 className="text-sm font-medium text-text mb-2">{IMAGE_DETAILS_PERSPECTIVE_ANALYSIS}</h3>
          <p className="text-sm text-text-tertiary">Loading scores…</p>
        </div>
      }
    >
      <AIPerspectiveSectionLoaded {...props} />
    </Suspense>
  )
}
