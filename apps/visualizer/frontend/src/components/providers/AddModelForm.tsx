import { useState, type FormEvent } from 'react';
import {
  PROVIDER_ADD_MODEL_ID_LABEL,
  PROVIDER_ADD_MODEL_NAME_LABEL,
  PROVIDER_ADD_MODEL_VISION_LABEL,
  PROVIDER_ADD_MODEL_SUBMIT,
  PROVIDER_ADD_MODEL_SUBMITTING,
  PROVIDER_ADD_MODEL_ERROR,
} from '../../constants/strings';
import { Button } from '../ui/Button';

interface AddModelFormProps {
  onAdd: (model: { id: string; name: string; vision: boolean }) => Promise<void>;
}

export function AddModelForm({ onAdd }: AddModelFormProps) {
  const [modelId, setModelId] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [supportsVision, setSupportsVision] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const trimmedId = modelId.trim();
    const trimmedName = displayName.trim();
    if (!trimmedId || !trimmedName || submitting) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      await onAdd({ id: trimmedId, name: trimmedName, vision: supportsVision });
      setModelId('');
      setDisplayName('');
      setSupportsVision(true);
    } catch (error) {
      const message = error instanceof Error ? error.message : PROVIDER_ADD_MODEL_ERROR;
      setSubmitError(message);
    } finally {
      setSubmitting(false);
    }
  }

  const inputClassName =
    'w-full border border-border rounded-base px-2 py-1.5 text-sm bg-bg text-text focus:outline-none focus:ring-2 focus:ring-accent focus:ring-offset-1';

  return (
    <form
      onSubmit={event => handleSubmit(event).catch(console.error)}
      className="mt-4 pt-4 border-t border-border space-y-3"
    >
      {submitError ? (
        <p className="text-sm text-error" role="alert">
          {submitError}
        </p>
      ) : null}
      <div className="grid gap-2 sm:grid-cols-2">
        <label className="block text-xs text-text-secondary">
          <span className="block mb-0.5">{PROVIDER_ADD_MODEL_ID_LABEL}</span>
          <input
            type="text"
            value={modelId}
            onChange={event => setModelId(event.target.value)}
            className={`${inputClassName} font-mono`}
            autoComplete="off"
            disabled={submitting}
          />
        </label>
        <label className="block text-xs text-text-secondary">
          <span className="block mb-0.5">{PROVIDER_ADD_MODEL_NAME_LABEL}</span>
          <input
            type="text"
            value={displayName}
            onChange={event => setDisplayName(event.target.value)}
            className={inputClassName}
            autoComplete="off"
            disabled={submitting}
          />
        </label>
      </div>
      <label className="flex items-center gap-2 text-sm text-text cursor-pointer">
        <input
          type="checkbox"
          checked={supportsVision}
          onChange={event => setSupportsVision(event.target.checked)}
          className="rounded border-border text-accent focus:ring-accent"
          disabled={submitting}
        />
        {PROVIDER_ADD_MODEL_VISION_LABEL}
      </label>
      <Button type="submit" variant="primary" size="sm" disabled={submitting}>
        {submitting ? PROVIDER_ADD_MODEL_SUBMITTING : PROVIDER_ADD_MODEL_SUBMIT}
      </Button>
    </form>
  );
}
