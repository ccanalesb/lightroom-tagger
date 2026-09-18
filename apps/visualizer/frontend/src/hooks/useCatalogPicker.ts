import { useCallback, useEffect, useState } from 'react'
import { ConfigAPI } from '../services/api'

/**
 * Every way the catalog path is acquired and saved, in one place.
 *
 * A browser cannot hand JavaScript a filesystem path, so the picker is the
 * backend's: it opens a macOS dialog on its own machine and answers with what
 * was chosen. Typing a path stays as the fallback for the machines and browsers
 * that leaves out. An Electron shell would replace the transport
 * ([#328](https://github.com/ccanalesb/lightroom-tagger/issues/328)) without
 * touching anything above this hook.
 */

export interface CatalogStatus {
  /** As stored in `config.yaml`, `~` and all. */
  path: string
  /** What the backend resolves that to. */
  resolvedPath: string
  exists: boolean
  /** Whether the backend's machine can open a native dialog. */
  pickerAvailable: boolean
  /**
   * `library.db` mirrors a catalog other than the configured one, so what the app
   * shows is from the old catalog until a sync runs. Stays true across the save —
   * saving is what causes it, not what settles it.
   */
  needsSync: boolean
}

/**
 * Finder's "Copy as Pathname" (⌥⌘C) wraps paths containing spaces in single
 * quotes on macOS 15+, so a pasted path arrives as `'/Users/me/My Photos/a.lrcat'`.
 */
export function normalizeCatalogPath(raw: string): string {
  const trimmed = raw.trim()
  if (trimmed.length < 2) return trimmed
  const first = trimmed[0]
  const last = trimmed[trimmed.length - 1]
  if ((first === "'" || first === '"') && first === last) {
    return trimmed.slice(1, -1).trim()
  }
  return trimmed
}

export function useCatalogPicker() {
  const [status, setStatus] = useState<CatalogStatus | null>(null)
  const [draftPath, setDraft] = useState('')
  const [loading, setLoading] = useState(true)
  const [picking, setPicking] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    setError(null)
    try {
      const data = await ConfigAPI.getCatalog()
      setStatus({
        path: data.catalog_path,
        resolvedPath: data.resolved_path,
        exists: data.exists,
        pickerAvailable: data.picker_available,
        needsSync: data.needs_catalog_sync,
      })
      setDraft(data.catalog_path)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  const setDraftPath = useCallback((value: string) => {
    setDraft(normalizeCatalogPath(value))
  }, [])

  const pick = useCallback(async () => {
    setPicking(true)
    setError(null)
    try {
      const { catalog_path: chosen } = await ConfigAPI.pickCatalog()
      // `null` is a dismissed dialog: the user changed their mind, not an error.
      if (chosen) setDraft(chosen)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setPicking(false)
    }
  }, [])

  /** Whether the path was written. A caller closing an editor needs to know. */
  const save = useCallback(async () => {
    setSaving(true)
    setError(null)
    try {
      await ConfigAPI.putCatalog(draftPath)
      await refresh()
      return true
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      return false
    } finally {
      setSaving(false)
    }
  }, [draftPath, refresh])

  return {
    status,
    draftPath,
    setDraftPath,
    /** Saving would point the library DB at a different catalog than it mirrors. */
    changesCatalog: status !== null && draftPath !== status.path,
    loading,
    picking,
    saving,
    error,
    pick,
    save,
  }
}
