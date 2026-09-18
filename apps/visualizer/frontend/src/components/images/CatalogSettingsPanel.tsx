import { useCatalogPicker } from '../../hooks';
import { Button } from '../ui/Button/Button';
import { Input } from '../ui/Input/Input';

export function CatalogSettingsPanel() {
  const { status, draftPath, setDraftPath, changesCatalog, loading, saving, error, save } =
    useCatalogPicker();

  return (
    <div className="rounded-base border border-border bg-bg p-4 space-y-4">
      <h3 className="text-sm font-medium text-text">Lightroom catalog</h3>
      {loading || !status ? (
        <p className="text-sm text-text-secondary">Loading catalog settings…</p>
      ) : (
        <>
          <Input
            label="Active catalog path"
            readOnly
            value={status.path}
            fullWidth
            className="text-text-secondary"
          />
          {status.exists ? (
            <p className="text-sm text-success">Found at {status.resolvedPath}</p>
          ) : (
            <p className="text-sm text-error">
              No file at {status.resolvedPath}. Catalog sync will fail until this is fixed.
            </p>
          )}
          <Input
            label="Catalog path (.lrcat)"
            value={draftPath}
            onChange={(e) => setDraftPath(e.target.value)}
            fullWidth
          />
          <p className="text-sm text-text-secondary">
            To get the path: find the .lrcat in Finder, hold Option and right-click it, then
            choose “Copy as Pathname” — or press ⌥⌘C — and paste it above.
          </p>
          <Button type="button" onClick={save} disabled={saving}>
            Save catalog path
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
