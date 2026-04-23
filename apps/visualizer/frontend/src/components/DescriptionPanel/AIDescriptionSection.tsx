import { Suspense, useCallback, useEffect, useState } from 'react'
import type { ImageDescription } from '../../services/api'
import { DescriptionsAPI, JobsAPI, ProvidersAPI } from '../../services/api'
import type { Job } from '../../types/job'
import { useJobSocket } from '../../hooks/useJobSocket'
import { DescriptionPanel } from './DescriptionPanel'
import { GenerateButton } from '../ui/description-atoms/GenerateButton'
import { ProviderModelSelect } from '../ui/ProviderModelSelect'
import { Spinner } from '../ui/Spinner'
import { IMAGE_DETAILS_AI_DESCRIPTION } from '../../constants/strings'
import { invalidate, useQuery } from '../../data'

interface AIDescriptionSectionProps {
  imageKey: string
  imageType: 'catalog' | 'instagram'
  /** Optional label prefix used inside the match modal to disambiguate
   *  the IG vs catalog panels, e.g. "Instagram — AI description". */
  titleOverride?: string
  /** Called after a generation job completes so the parent modal can
   *  refetch header metadata (scores, etc.). */
  onDataChanged?: () => void
}

function AIDescriptionSectionLoaded({
  imageKey,
  imageType,
  titleOverride,
  onDataChanged,
}: AIDescriptionSectionProps) {
  const defaults = useQuery(['providers.defaults'] as const, () => ProvidersAPI.getDefaults())
  const descPayload = useQuery(['descriptions', imageKey] as const, () =>
    DescriptionsAPI.get(imageKey),
  )
  const initialDescription = descPayload.description

  const [description, setDescription] = useState<ImageDescription | null>(initialDescription)
  const [error, setError] = useState<string | null>(null)
  const [generating, setGenerating] = useState(false)
  const [pendingJobId, setPendingJobId] = useState<string | null>(null)
  const [providerId, setProviderId] = useState<string | null>(null)
  const [modelId, setModelId] = useState<string | null>(null)
  const [showModelOptions, setShowModelOptions] = useState(false)
  const [, bump] = useState(0)

  useEffect(() => {
    setDescription(initialDescription)
  }, [initialDescription])

  useEffect(() => {
    const d = defaults.description
    if (d?.provider) setProviderId((p) => p ?? d.provider)
    if (d?.model) setModelId((m) => m ?? d.model)
  }, [defaults])

  const refreshDescription = useCallback(() => {
    invalidate(['descriptions', imageKey])
    bump((n) => n + 1)
  }, [imageKey])

  useJobSocket({
    onJobUpdated: useCallback(
      (job: Job) => {
        if (!pendingJobId || job.id !== pendingJobId) return
        if (job.status === 'completed') {
          setPendingJobId(null)
          setGenerating(false)
          refreshDescription()
          onDataChanged?.()
        } else if (job.status === 'failed') {
          setPendingJobId(null)
          setGenerating(false)
          setError(job.error ?? 'Description generation failed')
        } else if (job.status === 'cancelled') {
          setPendingJobId(null)
          setGenerating(false)
        }
      },
      [pendingJobId, refreshDescription, onDataChanged],
    ),
  })

  const handleGenerate = useCallback(async () => {
    setGenerating(true)
    setError(null)
    try {
      const job = await JobsAPI.create('single_describe', {
        image_key: imageKey,
        image_type: imageType,
        force: false,
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
      <h3 className="text-sm font-medium text-text mb-2">
        {titleOverride ?? IMAGE_DETAILS_AI_DESCRIPTION}
      </h3>
      {error ? <p className="text-sm text-error">{error}</p> : null}
      {generating ? (
        <div className="flex items-center gap-2 py-2">
          <Spinner />
          <span className="text-sm text-text-secondary">Generating description…</span>
        </div>
      ) : null}
      <DescriptionPanel description={description} />
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
 * Single source of truth for "AI description" rendering inside every
 * image modal (catalog, instagram, match sides, identity/best, unposted,
 * top-scored, post-next). Renders the full `DescriptionPanel` plus the
 * Generate button + optional model options.
 */
export function AIDescriptionSection(props: AIDescriptionSectionProps) {
  return (
    <Suspense
      fallback={
        <div className="p-4 bg-surface rounded-base border border-border">
          <h3 className="text-sm font-medium text-text mb-2">
            {props.titleOverride ?? IMAGE_DETAILS_AI_DESCRIPTION}
          </h3>
          <p className="text-sm text-text-tertiary">Loading description…</p>
        </div>
      }
    >
      <AIDescriptionSectionLoaded {...props} />
    </Suspense>
  )
}
