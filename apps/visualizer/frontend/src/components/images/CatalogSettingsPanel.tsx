import { useCatalogPicker } from '../../hooks';
import { Button } from '../ui/Button/Button';
import { Input } from '../ui/Input/Input';

export function CatalogSettingsPanel() {
  const {
    status,
    draftPath,
    setDraftPath,
    changesCatalog,
    loading,
    picking,
    saving,
    error,
    pick,
    save,
  } = useCatalogPicker();

  return (
    <div className="rounded-base border border-border bg-bg p-4 space-y-4">
      <h3 className="text-sm font-medium text-text">Lightroom catalog</h3>
      {loading || !status ? (
        <p className="text-sm text-text-secondary">Loading catalog settings…</p>
      ) : (
        <>
          {status.exists ? (
            <p className="text-sm text-success">Using {status.resolvedPath}</p>
          ) : (
            <p className="text-sm text-error">
              No catalog at {status.resolvedPath || 'the configured path'}. Catalog sync will fail
              until this is fixed.
            </p>
          )}

          <div className="flex items-end gap-2">
            <Input
              label="Catalog path (.lrcat)"
              value={draftPath}
              onChange={(e) => setDraftPath(e.target.value)}
              fullWidth
            />
            {status.pickerAvailable && (
              <Button type="button" onClick={pick} disabled={picking || saving}>
                {picking ? 'Choosing…' : 'Choose…'}
              </Button>
            )}
          </div>

          {status.pickerAvailable ? (
            <p className="text-sm text-text-secondary">
              The dialog opens on the machine running the backend. From another device, paste the
              path instead.
            </p>
          ) : (
            <p className="text-sm text-text-secondary">
              This backend cannot open a file dialog, so type or paste the path.
            </p>
          )}

          <Button type="button" onClick={save} disabled={saving || picking || !changesCatalog}>
            {saving ? 'Saving…' : 'Save catalog path'}
          </Button>
          {error && <p className="text-sm text-error">{error}</p>}
          {changesCatalog && (
            <p className="text-sm text-warning">
              This points at a different catalog than the library database was built from. Run a
              catalog sync afterwards, or what you see stays out of date.
            </p>
          )}
        </>
      )}
    </div>
  );
}
