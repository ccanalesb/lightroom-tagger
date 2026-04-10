import { useCallback, useEffect, useState } from 'react';
import {
  SETTINGS_INSTAGRAM_DUMP_HELP,
  SETTINGS_INSTAGRAM_DUMP_TITLE,
} from '../../constants/strings';
import { ConfigAPI, JobsAPI } from '../../services/api';
import { Button } from '../ui/Button/Button';
import { Input } from '../ui/Input/Input';

export function InstagramDumpSettingsPanel() {
  const [instagramDumpPath, setInstagramDumpPath] = useState('');
  const [draftPath, setDraftPath] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [exists, setExists] = useState(false);
  const [importQueued, setImportQueued] = useState(false);
  const [reimport, setReimport] = useState(false);
  const [skipDedup, setSkipDedup] = useState(false);

  const refresh = useCallback(async () => {
    setError(null);
    try {
      const data = await ConfigAPI.getInstagramDump();
      setInstagramDumpPath(data.instagram_dump_path);
      setDraftPath(data.instagram_dump_path);
      setExists(data.exists);
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
    setSaving(true);
    setError(null);
    setImportQueued(false);
    try {
      await ConfigAPI.putInstagramDump(draftPath);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  };

  const handleRunImport = async () => {
    setImporting(true);
    setError(null);
    setImportQueued(false);
    try {
      await JobsAPI.create('instagram_import', { reimport, skip_dedup: skipDedup });
      setImportQueued(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setImporting(false);
    }
  };

  return (
    <div className="rounded-base border border-border bg-bg p-4 space-y-4">
      <h3 className="text-sm font-medium text-text">{SETTINGS_INSTAGRAM_DUMP_TITLE}</h3>
      {loading ? (
        <p className="text-sm text-text-secondary">Loading Instagram dump settings…</p>
      ) : (
        <>
          <Input
            label="Saved dump path (on server)"
            readOnly
            value={instagramDumpPath}
            fullWidth
            className="text-text-secondary"
          />
          <Input
            label="Dump directory path"
            value={draftPath}
            onChange={(e) => setDraftPath(e.target.value)}
            fullWidth
          />
          <p className="text-sm text-text-secondary">
            {exists ? 'Server can access this path as a directory.' : 'Path empty or not found on the server.'}
          </p>
          <div className="flex flex-wrap gap-3 items-center">
            <Button type="button" onClick={handleSave} disabled={saving}>
              Save dump path
            </Button>
            <Button type="button" variant="primary" onClick={handleRunImport} disabled={importing}>
              Run Import
            </Button>
          </div>
          <div className="space-y-2 text-sm text-text-secondary">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={reimport}
                onChange={(e) => setReimport(e.target.checked)}
                className="rounded border-border"
              />
              Re-import (reprocess files already in the library)
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={skipDedup}
                onChange={(e) => setSkipDedup(e.target.checked)}
                className="rounded border-border"
              />
              Skip duplicate detection (faster, may add duplicates)
            </label>
          </div>
          {importQueued && (
            <p className="text-sm text-success" role="status">
              Import job queued. Check the Job Queue for progress.
            </p>
          )}
          {error && <p className="text-sm text-error">{error}</p>}
          <p className="text-sm text-text-secondary">{SETTINGS_INSTAGRAM_DUMP_HELP}</p>
        </>
      )}
    </div>
  );
}
