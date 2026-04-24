import { useCallback, useEffect, useState } from 'react';
import { ConfigAPI } from '../../services/api';
import { Button } from '../ui/Button/Button';
import { Input } from '../ui/Input/Input';

export function StackDetectionSettingsPanel() {
  const [savedMs, setSavedMs] = useState(2000);
  const [draftMs, setDraftMs] = useState('2000');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setError(null);
    try {
      const data = await ConfigAPI.getStackDetection();
      const n = data.stack_burst_delta_ms;
      setSavedMs(n);
      setDraftMs(String(n));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const handleSave = async () => {
    const parsed = parseInt(draftMs, 10);
    if (Number.isNaN(parsed) || parsed < 1) {
      setError('Enter a whole number of milliseconds, at least 1.');
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await ConfigAPI.putStackDetection(parsed);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="rounded-base border border-border bg-bg p-4 space-y-4">
      <h3 className="text-sm font-medium text-text">Stack detection</h3>
      {loading ? (
        <p className="text-sm text-text-secondary">Loading stack detection settings…</p>
      ) : (
        <>
          <Input
            label="Saved burst window (ms, on server)"
            readOnly
            value={String(savedMs)}
            fullWidth
            className="text-text-secondary"
          />
          <Input
            label="Burst time window (milliseconds)"
            type="number"
            min={1}
            step={1}
            value={draftMs}
            onChange={(e) => setDraftMs(e.target.value)}
            fullWidth
          />
          <p className="text-sm text-text-secondary">
            Default time between shots treated as the same burst for <code className="text-text">batch_stack_detect</code>
            . Increase for slower sequences; decrease for fast bursts.
          </p>
          <Button type="button" onClick={handleSave} disabled={saving}>
            Save burst window
          </Button>
          {error && <p className="text-sm text-error">{error}</p>}
        </>
      )}
    </div>
  );
}
