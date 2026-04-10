import { useCallback, useEffect, useState } from 'react';
import { ConfigAPI } from '../../services/api';
import { Button } from '../ui/Button/Button';
import { Input } from '../ui/Input/Input';

export function CatalogSettingsPanel() {
  const [catalogPath, setCatalogPath] = useState('');
  const [draftPath, setDraftPath] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setError(null);
    try {
      const data = await ConfigAPI.getCatalog();
      setCatalogPath(data.catalog_path);
      setDraftPath(data.catalog_path);
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
    try {
      await ConfigAPI.putCatalog(draftPath);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="rounded-base border border-border bg-bg p-4 space-y-4">
      <h3 className="text-sm font-medium text-text">Lightroom catalog</h3>
      {loading ? (
        <p className="text-sm text-text-secondary">Loading catalog settings…</p>
      ) : (
        <>
          <Input
            label="Active catalog path"
            readOnly
            value={catalogPath}
            fullWidth
            className="text-text-secondary"
          />
          <Input
            label="Catalog path (.lrcat)"
            value={draftPath}
            onChange={(e) => setDraftPath(e.target.value)}
            fullWidth
          />
          <Button type="button" onClick={handleSave} disabled={saving}>
            Save catalog path
          </Button>
          {error && <p className="text-sm text-error">{error}</p>}
          <p className="text-sm text-text-secondary">
            Run a catalog scan from the CLI after changing the path so the library database stays in sync.
          </p>
        </>
      )}
    </div>
  );
}
