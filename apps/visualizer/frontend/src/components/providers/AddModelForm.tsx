import { useState, type FormEvent } from 'react'
import {
  PROVIDER_ADD_MODEL_ID_LABEL,
  PROVIDER_ADD_MODEL_NAME_LABEL,
  PROVIDER_ADD_MODEL_VISION_LABEL,
  PROVIDER_ADD_MODEL_SUBMIT,
  PROVIDER_ADD_MODEL_SUBMITTING,
  PROVIDER_ADD_MODEL_ERROR,
} from '../../constants/strings'

interface AddModelFormProps {
  onAdd: (model: { id: string; name: string; vision: boolean }) => Promise<void>
}

export function AddModelForm({ onAdd }: AddModelFormProps) {
  const [modelId, setModelId] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [supportsVision, setSupportsVision] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const trimmedId = modelId.trim()
    const trimmedName = displayName.trim()
    if (!trimmedId || !trimmedName || submitting) return
    setSubmitting(true)
    setSubmitError(null)
    try {
      await onAdd({ id: trimmedId, name: trimmedName, vision: supportsVision })
      setModelId('')
      setDisplayName('')
      setSupportsVision(true)
    } catch {
      setSubmitError(PROVIDER_ADD_MODEL_ERROR)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={event => handleSubmit(event).catch(console.error)} className="mt-4 pt-4 border-t border-gray-100 space-y-3">
      {submitError ? (
        <p className="text-sm text-red-600" role="alert">
          {submitError}
        </p>
      ) : null}
      <div className="grid gap-2 sm:grid-cols-2">
        <label className="block text-xs text-gray-600">
          <span className="block mb-0.5">{PROVIDER_ADD_MODEL_ID_LABEL}</span>
          <input
            type="text"
            value={modelId}
            onChange={event => setModelId(event.target.value)}
            className="w-full border border-gray-200 rounded px-2 py-1.5 text-sm font-mono"
            autoComplete="off"
            disabled={submitting}
          />
        </label>
        <label className="block text-xs text-gray-600">
          <span className="block mb-0.5">{PROVIDER_ADD_MODEL_NAME_LABEL}</span>
          <input
            type="text"
            value={displayName}
            onChange={event => setDisplayName(event.target.value)}
            className="w-full border border-gray-200 rounded px-2 py-1.5 text-sm"
            autoComplete="off"
            disabled={submitting}
          />
        </label>
      </div>
      <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
        <input
          type="checkbox"
          checked={supportsVision}
          onChange={event => setSupportsVision(event.target.checked)}
          className="rounded border-gray-300"
          disabled={submitting}
        />
        {PROVIDER_ADD_MODEL_VISION_LABEL}
      </label>
      <button
        type="submit"
        disabled={submitting}
        className="px-3 py-1.5 text-sm font-medium rounded-md bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {submitting ? PROVIDER_ADD_MODEL_SUBMITTING : PROVIDER_ADD_MODEL_SUBMIT}
      </button>
    </form>
  )
}
