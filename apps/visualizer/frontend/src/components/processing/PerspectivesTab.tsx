import CodeMirror from '@uiw/react-codemirror'
import { markdown } from '@codemirror/lang-markdown'
import { useCallback, useEffect, useState } from 'react'
import { Modal } from '../modal/Modal'
import { Badge } from '../ui/badges'
import { Button } from '../ui/Button'
import { Card, CardContent, CardHeader, CardTitle } from '../ui/Card'
import { NAV_PERSPECTIVES_HELP } from '../../constants/strings'
import {
  PerspectivesAPI,
  type PerspectiveDetail,
  type PerspectiveSummary,
} from '../../services/api'

const NEW_TEMPLATE = `# Perspective

Add instructions for this critique lens. Include theory basis and scoring anchors as needed.
`

function slugifyDisplay(slug: string): string {
  return slug
    .split('_')
    .map((w) => (w ? w[0].toUpperCase() + w.slice(1) : ''))
    .join(' ')
}

export function PerspectivesTab() {
  const [rows, setRows] = useState<PerspectiveSummary[]>([])
  const [selectedSlug, setSelectedSlug] = useState<string | null>(null)
  const [detail, setDetail] = useState<PerspectiveDetail | null>(null)
  const [displayName, setDisplayName] = useState('')
  const [description, setDescription] = useState('')
  const [promptMarkdown, setPromptMarkdown] = useState('')
  const [loadingList, setLoadingList] = useState(true)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [addOpen, setAddOpen] = useState(false)
  const [newSlug, setNewSlug] = useState('')
  const [newDisplayName, setNewDisplayName] = useState('')
  const [newBody, setNewBody] = useState(NEW_TEMPLATE)

  const loadList = useCallback(async () => {
    setLoadingList(true)
    setError(null)
    try {
      const list = await PerspectivesAPI.list()
      setRows(list)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load perspectives')
    } finally {
      setLoadingList(false)
    }
  }, [])

  useEffect(() => {
    void loadList()
  }, [loadList])

  const loadDetail = useCallback(async (slug: string) => {
    setLoadingDetail(true)
    setError(null)
    try {
      const d = await PerspectivesAPI.get(slug)
      setDetail(d)
      setDisplayName(d.display_name)
      setDescription(d.description)
      setPromptMarkdown(d.prompt_markdown)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load perspective')
      setDetail(null)
    } finally {
      setLoadingDetail(false)
    }
  }, [])

  useEffect(() => {
    if (selectedSlug) void loadDetail(selectedSlug)
    else {
      setDetail(null)
      setDisplayName('')
      setDescription('')
      setPromptMarkdown('')
    }
  }, [selectedSlug, loadDetail])

  async function handleToggleActive(row: PerspectiveSummary, next: boolean) {
    setError(null)
    try {
      await PerspectivesAPI.update(row.slug, { active: next })
      await loadList()
      if (selectedSlug === row.slug && detail) {
        setDetail({ ...detail, active: next })
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to update active flag')
    }
  }

  async function handleSave() {
    if (!selectedSlug) return
    setSaving(true)
    setError(null)
    try {
      const updated = await PerspectivesAPI.update(selectedSlug, {
        display_name: displayName,
        description,
        prompt_markdown: promptMarkdown,
      })
      setDetail(updated)
      await loadList()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  async function handleResetDefault() {
    if (!selectedSlug) return
    if (!window.confirm('Replace editor content from the default markdown file on disk?')) return
    setSaving(true)
    setError(null)
    try {
      const updated = await PerspectivesAPI.resetDefault(selectedSlug)
      setDetail(updated)
      setPromptMarkdown(updated.prompt_markdown)
      await loadList()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Reset failed')
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete() {
    if (!selectedSlug || !detail) return
    if (!window.confirm(`Delete perspective "${selectedSlug}"? This cannot be undone.`)) return
    setSaving(true)
    setError(null)
    try {
      await PerspectivesAPI.remove(selectedSlug)
      setSelectedSlug(null)
      await loadList()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Delete failed')
    } finally {
      setSaving(false)
    }
  }

  async function handleCreatePerspective() {
    const slugRe = /^[a-z][a-z0-9_]{0,63}$/
    if (!slugRe.test(newSlug.trim())) {
      setError('Slug must match [a-z][a-z0-9_]{0,63}')
      return
    }
    const slug = newSlug.trim()
    const dn = newDisplayName.trim() || slugifyDisplay(slug)
    setSaving(true)
    setError(null)
    try {
      await PerspectivesAPI.create({
        slug,
        display_name: dn,
        prompt_markdown: newBody,
        active: true,
      })
      setAddOpen(false)
      setNewSlug('')
      setNewDisplayName('')
      setNewBody(NEW_TEMPLATE)
      await loadList()
      setSelectedSlug(slug)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Create failed')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div>
      <Card padding="lg">
        <CardHeader>
          <CardTitle>Perspective rubrics</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-text-secondary mb-4">{NAV_PERSPECTIVES_HELP}</p>
          {error && (
            <div className="mb-4 text-sm text-error" role="alert">
              {error}
            </div>
          )}
          <div className="flex flex-col lg:flex-row gap-6">
            <div className="w-full lg:w-72 shrink-0 space-y-3">
              <div className="flex gap-2">
                <Button type="button" variant="primary" size="sm" onClick={() => setAddOpen(true)}>
                  Add perspective
                </Button>
                <Button type="button" variant="secondary" size="sm" onClick={() => void loadList()}>
                  Refresh
                </Button>
              </div>
              <div className="border border-border rounded-base divide-y divide-border max-h-[480px] overflow-y-auto bg-bg">
                {loadingList ? (
                  <p className="p-3 text-sm text-text-secondary">Loading…</p>
                ) : rows.length === 0 ? (
                  <p className="p-3 text-sm text-text-secondary">No perspectives</p>
                ) : (
                  rows.map((row) => (
                    <div
                      key={row.slug}
                      className={`p-3 cursor-pointer hover:bg-surface transition-colors ${
                        selectedSlug === row.slug ? 'bg-surface border-l-2 border-l-accent' : ''
                      }`}
                      onClick={() => setSelectedSlug(row.slug)}
                      onKeyDown={(ev) => {
                        if (ev.key === 'Enter' || ev.key === ' ') {
                          ev.preventDefault()
                          setSelectedSlug(row.slug)
                        }
                      }}
                      role="button"
                      tabIndex={0}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <div className="font-medium text-text">{row.slug}</div>
                          <div className="text-xs text-text-secondary mt-0.5">{row.display_name}</div>
                        </div>
                        <Badge variant={row.active ? 'success' : 'default'}>
                          {row.active ? 'Active' : 'Inactive'}
                        </Badge>
                      </div>
                      <label
                        className="mt-2 flex items-center gap-2 text-sm text-text cursor-pointer"
                        onClick={(ev) => ev.stopPropagation()}
                      >
                        <input
                          type="checkbox"
                          checked={row.active}
                          onChange={(ev) => void handleToggleActive(row, ev.target.checked)}
                          className="w-4 h-4 rounded border-border text-accent focus:ring-accent focus:ring-offset-0"
                        />
                        <span>Active</span>
                      </label>
                    </div>
                  ))
                )}
              </div>
            </div>

            <div className="flex-1 min-w-0 space-y-4">
              {!selectedSlug ? (
                <p className="text-sm text-text-secondary">Select a perspective to edit.</p>
              ) : loadingDetail ? (
                <p className="text-sm text-text-secondary">Loading editor…</p>
              ) : (
                <>
                  <div className="grid gap-4 sm:grid-cols-2">
                    <div>
                      <label className="block text-sm font-medium text-text mb-1">Display name</label>
                      <input
                        type="text"
                        value={displayName}
                        onChange={(e) => setDisplayName(e.target.value)}
                        className="w-full px-3 py-2 rounded-base border border-border bg-bg text-text focus:outline-none focus:ring-2 focus:ring-accent"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-text mb-1">Description</label>
                      <input
                        type="text"
                        value={description}
                        onChange={(e) => setDescription(e.target.value)}
                        className="w-full px-3 py-2 rounded-base border border-border bg-bg text-text focus:outline-none focus:ring-2 focus:ring-accent"
                      />
                    </div>
                  </div>
                  <div>
                    <span className="block text-sm font-medium text-text mb-1">Prompt (markdown)</span>
                    <CodeMirror
                      value={promptMarkdown}
                      height="min(50vh, 420px)"
                      className="w-full border border-border rounded-base overflow-hidden text-sm"
                      extensions={[markdown()]}
                      onChange={(v) => setPromptMarkdown(v)}
                    />
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button type="button" variant="primary" onClick={() => void handleSave()} disabled={saving}>
                      {saving ? 'Saving…' : 'Save'}
                    </Button>
                    <Button
                      type="button"
                      variant="secondary"
                      onClick={() => void handleResetDefault()}
                      disabled={saving}
                    >
                      Reset to default
                    </Button>
                    <Button type="button" variant="danger" onClick={() => void handleDelete()} disabled={saving}>
                      Delete
                    </Button>
                  </div>
                </>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {addOpen && (
        <Modal onClose={() => setAddOpen(false)} maxWidth="lg">
          <div className="p-6 flex flex-col gap-4 bg-bg max-h-[90vh] overflow-y-auto">
            <h2 className="text-lg font-semibold text-text">Add perspective</h2>
            <div>
              <label className="block text-sm font-medium text-text mb-1">Slug</label>
              <input
                type="text"
                value={newSlug}
                onChange={(e) => setNewSlug(e.target.value)}
                placeholder="e.g. color_theory"
                className="w-full px-3 py-2 rounded-base border border-border bg-bg text-text focus:outline-none focus:ring-2 focus:ring-accent"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-text mb-1">Display name (optional)</label>
              <input
                type="text"
                value={newDisplayName}
                onChange={(e) => setNewDisplayName(e.target.value)}
                className="w-full px-3 py-2 rounded-base border border-border bg-bg text-text focus:outline-none focus:ring-2 focus:ring-accent"
              />
            </div>
            <div>
              <span className="block text-sm font-medium text-text mb-1">Template body</span>
              <CodeMirror
                value={newBody}
                height="220px"
                className="w-full border border-border rounded-base overflow-hidden text-sm"
                extensions={[markdown()]}
                onChange={(v) => setNewBody(v)}
              />
            </div>
            <div className="flex gap-2 justify-end">
              <Button type="button" variant="ghost" onClick={() => setAddOpen(false)}>
                Cancel
              </Button>
              <Button type="button" variant="primary" onClick={() => void handleCreatePerspective()} disabled={saving}>
                Create
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  )
}
