import { CatalogSettingsPanel } from '../images/CatalogSettingsPanel';

export function SettingsTab() {
  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-card-title text-text mb-2">General Settings</h3>
        <p className="text-sm text-text-secondary">
          Configure catalog path and application preferences
        </p>
      </div>

      <CatalogSettingsPanel />
    </div>
  );
}
