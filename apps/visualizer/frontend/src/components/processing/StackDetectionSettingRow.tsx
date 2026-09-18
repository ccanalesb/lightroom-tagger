import { useCallback, useEffect, useState } from 'react';
import { ConfigAPI } from '../../services/api';
import { Button } from '../ui/Button/Button';
import { SettingRow } from './SettingRow';

export function StackDetectionSettingRow() {
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

  if (loading) {
    return <SettingRow name="Stack detection" description="Loading…" control={null} />;
  }

  const changed = draftMs !== String(savedMs);

  return (
    <SettingRow
      name="Stack detection"
      description={
        <>
          Shots within {savedMs} ms are treated as one burst by{' '}
          <code className="text-text">batch_stack_detect</code>
        </>
      }
      control={
        <>
          <input
            type="number"
            min={1}
            step={1}
            value={draftMs}
            onChange={(e) => setDraftMs(e.target.value)}
            aria-label="Burst time window (milliseconds)"
            className="w-24 rounded-base border border-border bg-bg px-3 py-1.5 text-sm text-text transition-all duration-150 hover:border-border-strong focus:border-transparent focus:outline-none focus:ring-2 focus:ring-accent"
          />
          <span className="text-sm text-text-secondary">ms</span>
          <Button
            type="button"
            size="sm"
            variant="primary"
            onClick={handleSave}
            disabled={saving || !changed}
          >
            {saving ? 'Saving…' : 'Save'}
          </Button>
        </>
      }
      under={error && <p className="text-sm text-error">{error}</p>}
    />
  );
}
