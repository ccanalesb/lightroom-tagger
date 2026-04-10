# Plan 03-04 — Summary

**Title:** Frontend: configure dump path and Run Import job  
**Phase:** 03 — Instagram sync  
**Requirements:** IG-01  
**Completed:** 2026-04-10

## Outcome

- **ConfigAPI:** `getInstagramDump` and `putInstagramDump` call `GET` / `PUT` `/api/config/instagram-dump` with the same `request` helper and types as catalog config (`instagram_dump_path`, `resolved_path`, `exists` on GET; `ok` on PUT).
- **Strings:** `SETTINGS_INSTAGRAM_DUMP_TITLE` and `SETTINGS_INSTAGRAM_DUMP_HELP` document that the dump path is on the **server**, not a browser upload (IG-01 intent).
- **UI:** `InstagramDumpSettingsPanel` mirrors `CatalogSettingsPanel` layout (`rounded-base border … space-y-4`), loads and saves the dump directory, shows server `exists` hint, optional checkboxes for job metadata `reimport` and `skip_dedup`, and **Run Import** via `JobsAPI.create('instagram_import', { … })`.
- **Integration:** `SettingsTab` renders `InstagramDumpSettingsPanel` immediately below `CatalogSettingsPanel`.

## Commits

| Commit   | Message |
|----------|---------|
| `e5bd275` | `feat(03-04): ConfigAPI methods for instagram-dump endpoint` |
| `b18f3c5` | `feat(03-04): InstagramDumpSettingsPanel and settings strings` |
| `ac66385` | `feat(03-04): mount Instagram dump panel in Settings tab` |

## Verification

- `npm run lint` in `apps/visualizer/frontend` — exit 0.
- `grep -q "getInstagramDump" apps/visualizer/frontend/src/services/api.ts` — exit 0.
- `grep -q "InstagramDumpSettingsPanel" apps/visualizer/frontend/src/components/processing/SettingsTab.tsx` — exit 0.

## Notes

- PUT still requires an existing directory on the server; the panel surfaces GET `exists` so operators know when the saved path is not visible to the backend.
