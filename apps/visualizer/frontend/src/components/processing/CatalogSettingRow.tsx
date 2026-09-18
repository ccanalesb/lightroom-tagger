import { useState } from 'react';
import { useCatalogPicker } from '../../hooks';
import { Button } from '../ui/Button/Button';
import { Input } from '../ui/Input/Input';
import { PathSummary, SettingRow } from './SettingRow';

export function CatalogSettingRow() {
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
  const [typing, setTyping] = useState(false);

  if (loading || !status) {
    return <SettingRow name="Lightroom catalog" description="Loading…" control={null} />;
  }

  // The panel is not only the manual escape hatch: a path that is picked but not
  // yet saved needs somewhere to sit and something to commit it.
  const panelOpen = typing || changesCatalog || !status.path;

  const cancel = () => {
    setDraftPath(status.path);
    setTyping(false);
  };

  return (
    <SettingRow
      name="Lightroom catalog"
      description={
        status.exists ? (
          <PathSummary path={status.resolvedPath} />
        ) : (
          <span className="text-error">
            {status.path ? 'No file at this path — catalog sync will fail' : 'Not set'}
          </span>
        )
      }
      control={
        <>
          {status.pickerAvailable && (
            <Button
              type="button"
              size="sm"
              variant={status.exists ? 'secondary' : 'primary'}
              onClick={pick}
              disabled={picking || saving}
            >
              {picking ? 'Choosing…' : 'Choose…'}
            </Button>
          )}
          {!panelOpen && (
            <Button type="button" size="sm" variant="ghost" onClick={() => setTyping(true)}>
              Type a path
            </Button>
          )}
        </>
      }
      panel={
        panelOpen && (
          <>
            <Input
              label="Catalog path (.lrcat)"
              value={draftPath}
              onChange={(e) => setDraftPath(e.target.value)}
              fullWidth
            />
            <p className="text-sm text-text-secondary">
              {status.pickerAvailable
                ? 'The dialog opens on the machine running the backend. From another device, paste a path here — Finder’s ⌥⌘C copies one.'
                : 'This backend cannot open a file dialog, so type or paste the path.'}
            </p>
            {changesCatalog && (
              <p className="text-sm text-warning">
                This points at a different catalog than the library database was built from. Run a
                catalog sync afterwards, or what you see stays out of date.
              </p>
            )}
            {error && <p className="text-sm text-error">{error}</p>}
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                size="sm"
                variant="primary"
                onClick={save}
                disabled={saving || picking || !changesCatalog}
              >
                {saving ? 'Saving…' : 'Save'}
              </Button>
              <Button type="button" size="sm" variant="ghost" onClick={cancel} disabled={saving}>
                Cancel
              </Button>
            </div>
          </>
        )
      }
    />
  );
}
