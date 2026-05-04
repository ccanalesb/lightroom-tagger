import { FormEvent, useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { ImageDetailModal, ImageTile, fromCatalogListRow } from '../components/image-view'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { TileGrid } from '../components/ui/TileGrid'
import { SkeletonGrid } from '../components/ui/page-states'
import {
  PROCESSING_CATALOG_CACHE_ROUTE,
  PROCESSING_JOB_QUEUE_ROUTE,
  PROCESSING_OPEN_JOB_QUEUE,
  SEARCH_PIN_HELP_EMBED,
  SEARCH_PIN_INACTIVE_PREFIX,
  SEARCH_PIN_INACTIVE_SUFFIX,
  SEARCH_PIN_LINK_CACHE,
  SEARCH_PIN_WARN_NO_CLIP,
} from '../constants/strings'
import {
  ImagesAPI,
  ProvidersAPI,
  type CatalogImage,
  type ChatSearchMessage,
  type ChatSearchResultImage,
  type DescriptionModel,
} from '../services/api'

const PROVIDER_STORAGE_KEY = 'search:selected_provider'
const MODEL_STORAGE_KEY = 'search:selected_model'

function resolveChatModelSelection(
  models: DescriptionModel[],
  defaultProvider: string | null,
  defaultModel: string | null,
): { provider: string; model: string } {
  const chat = models.filter((m) => m.tool_calling)
  if (chat.length === 0) {
    return { provider: '', model: '' }
  }
  const prevP = localStorage.getItem(PROVIDER_STORAGE_KEY) ?? ''
  const prevM = localStorage.getItem(MODEL_STORAGE_KEY) ?? ''
  let provider =
    prevP && chat.some((m) => m.provider_id === prevP)
      ? prevP
      : defaultProvider && chat.some((m) => m.provider_id === defaultProvider)
        ? defaultProvider
        : (chat[0]?.provider_id ?? '')
  let forProvider = chat.filter((m) => m.provider_id === provider)
  if (forProvider.length === 0) {
    provider = chat[0]!.provider_id
    forProvider = chat.filter((m) => m.provider_id === provider)
  }
  const model =
    prevM && forProvider.some((m) => m.model_id === prevM)
      ? prevM
      : defaultModel && forProvider.some((m) => m.model_id === defaultModel)
        ? defaultModel
        : (forProvider[0]?.model_id ?? '')
  return { provider, model }
}

type Message = {
  role: 'user' | 'assistant'
  content: string
  images?: ChatSearchResultImage[]
  search_mode?: 'nl_filter' | 'semantic' | 'tool_calling'
}

type SelectedImage = { key: string; initial?: CatalogImage }

type ChatSearchMode = Message['search_mode']

export function SearchPage() {
  const [messages, setMessages] = useState<Message[]>([])
  const [apiHistory, setApiHistory] = useState<ChatSearchMessage[]>([])
  const [lastSearchMode, setLastSearchMode] = useState<ChatSearchMode | null>(null)
  const [input, setInput] = useState('')
  const [status, setStatus] = useState<'idle' | 'loading' | 'error'>('idle')
  const [errorText, setErrorText] = useState<string | null>(null)
  const [currentImages, setCurrentImages] = useState<ChatSearchResultImage[]>([])
  const [selectedImage, setSelectedImage] = useState<SelectedImage | null>(null)
  const [pinnedImageKey, setPinnedImageKey] = useState<string | null>(null)
  const [pinSimilarityWarning, setPinSimilarityWarning] = useState<string | null>(null)
  const [pinInactiveReason, setPinInactiveReason] = useState<string | null>(null)
  const threadRef = useRef<HTMLDivElement>(null)

  const [allModels, setAllModels] = useState<DescriptionModel[]>([])
  const [descriptionModelsLoadFinished, setDescriptionModelsLoadFinished] = useState(false)
  const [selectedProvider, setSelectedProvider] = useState<string>(
    () => localStorage.getItem(PROVIDER_STORAGE_KEY) ?? '',
  )
  const [selectedModelId, setSelectedModelId] = useState<string>(
    () => localStorage.getItem(MODEL_STORAGE_KEY) ?? '',
  )

  const chatModels = useMemo(
    () => allModels.filter((m) => m.tool_calling),
    [allModels],
  )
  const chatProviders = useMemo(
    () =>
      Array.from(new Map(chatModels.map((m) => [m.provider_id, m.provider_name])).entries()).map(
        ([id, name]) => ({ id, name }),
      ),
    [chatModels],
  )

  useEffect(() => {
    let cancelled = false
    ProvidersAPI.listDescriptionModels()
      .then(({ models, default_provider, default_model }) => {
        if (cancelled) return
        setAllModels(models)
        const { provider, model } = resolveChatModelSelection(models, default_provider, default_model)
        setSelectedProvider(provider)
        setSelectedModelId(model)
        if (provider) localStorage.setItem(PROVIDER_STORAGE_KEY, provider)
        if (model) localStorage.setItem(MODEL_STORAGE_KEY, model)
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setErrorText(err instanceof Error ? err.message : 'Failed to load AI models')
        }
      })
      .finally(() => {
        if (!cancelled) setDescriptionModelsLoadFinished(true)
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (!descriptionModelsLoadFinished) return
    if (chatModels.length === 0) return
    if (chatProviders.some((p) => p.id === selectedProvider)) return
    const first = chatProviders[0]
    if (!first) return
    setSelectedProvider(first.id)
    localStorage.setItem(PROVIDER_STORAGE_KEY, first.id)
    const m = chatModels.find((c) => c.provider_id === first.id)
    if (m) {
      setSelectedModelId(m.model_id)
      localStorage.setItem(MODEL_STORAGE_KEY, m.model_id)
    }
  }, [
    descriptionModelsLoadFinished,
    chatModels,
    chatProviders,
    selectedProvider,
  ])

  // Scroll thread to bottom on new messages
  useEffect(() => {
    if (threadRef.current) {
      threadRef.current.scrollTop = threadRef.current.scrollHeight
    }
  }, [messages])

  const modelsForProvider = chatModels.filter((m) => m.provider_id === selectedProvider)

  const resolvedModel = chatModels.find(
    (m) => m.provider_id === selectedProvider && m.model_id === selectedModelId,
  )

  const noToolCapableModels =
    descriptionModelsLoadFinished && chatModels.length === 0

  const handleProviderChange = (pid: string) => {
    setSelectedProvider(pid)
    localStorage.setItem(PROVIDER_STORAGE_KEY, pid)
    const first = chatModels.find((m) => m.provider_id === pid)
    if (first) {
      setSelectedModelId(first.model_id)
      localStorage.setItem(MODEL_STORAGE_KEY, first.model_id)
    }
  }

  const handleModelChange = (mid: string) => {
    setSelectedModelId(mid)
    localStorage.setItem(MODEL_STORAGE_KEY, mid)
  }

  const handleClear = () => {
    setMessages([])
    setApiHistory([])
    setLastSearchMode(null)
    setCurrentImages([])
    setErrorText(null)
    setStatus('idle')
    setInput('')
    setPinnedImageKey(null)
    setPinSimilarityWarning(null)
    setPinInactiveReason(null)
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (noToolCapableModels) return
    const trimmed = input.trim()
    if (!trimmed || status === 'loading') return

    setErrorText(null)
    setStatus('loading')
    setMessages((prev) => [...prev, { role: 'user', content: trimmed }])

    try {
      const data = await ImagesAPI.chatSearch({
        message: trimmed,
        messages: apiHistory,
        limit: 50,
        provider_id: resolvedModel?.provider_id,
        model: resolvedModel?.model_id,
        ...(pinnedImageKey ? { pinned_image_key: pinnedImageKey } : {}),
      })
      const assistantText =
        data.assistant_message ||
        (data.total === 0
          ? "I couldn't find any photos matching that. Try rephrasing or a broader query."
          : `Found ${data.total} result(s).`)
      setCurrentImages(data.images)
      const meta = data.metadata as
        | { pin_state?: string; fallback_reason?: string }
        | null
        | undefined
      if (meta?.pin_state === 'inactive' && meta.fallback_reason) {
        const fr = meta.fallback_reason
        setPinInactiveReason(fr)
        setPinSimilarityWarning(
          fr === 'no_clip_embedding'
            ? SEARCH_PIN_WARN_NO_CLIP
            : fr === 'invalid_pin_key'
              ? 'Pinned image is no longer in the catalog'
              : fr,
        )
      } else {
        setPinSimilarityWarning(null)
        setPinInactiveReason(null)
      }
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: assistantText,
          search_mode: data.search_mode,
        },
      ])
      const fullHistory: ChatSearchMessage[] =
        data.messages ?? [
          ...apiHistory,
          { role: 'user', content: trimmed },
          { role: 'assistant', content: assistantText },
        ]
      setApiHistory(fullHistory)
      setLastSearchMode(data.search_mode)
      setInput('')
      setStatus('idle')
    } catch (err) {
      setErrorText(err instanceof Error ? err.message : String(err))
      setStatus('error')
    }
  }

  const selectClass =
    'min-w-0 w-full rounded border border-border bg-surface px-2 py-1 text-xs text-text focus:outline-none focus:ring-1 focus:ring-primary truncate'

  return (
    <div>
      <div className="mb-3">
        <h1 className="text-section text-text mb-1">Search</h1>
        <p className="text-text-secondary text-sm">Ask questions in natural language; results update on each message.</p>
      </div>

      <div className="flex flex-col md:flex-row gap-4 min-h-[70vh]">
        {/* Chat column */}
        <div className="w-full md:w-2/5 flex flex-col min-h-[280px] md:min-h-0">

          {/* Thread header: clear action */}
          {messages.length > 0 && (
            <div className="flex justify-end mb-1">
              <button
                type="button"
                onClick={handleClear}
                className="text-xs text-text-secondary hover:text-text transition-colors"
              >
                Clear
              </button>
            </div>
          )}

          {/* Thread */}
          <div ref={threadRef} className="flex-1 overflow-y-auto space-y-1.5 min-h-0">
            {messages.length === 0 && (
              <p className="text-xs text-text-secondary text-center mt-6">Your conversation will appear here.</p>
            )}
            {messages.map((m, i) => (
              <div
                key={i}
                className={m.role === 'user' ? 'flex justify-end' : 'flex justify-start'}
              >
                <div
                  className={
                    m.role === 'user'
                      ? 'max-w-[85%] rounded-lg border border-border bg-surface px-3 py-1.5 text-sm text-right text-text'
                      : 'max-w-[85%] rounded-lg border border-border bg-surface px-3 py-1.5 text-sm text-left text-text-secondary'
                  }
                >
                  {m.content}
                </div>
              </div>
            ))}
          </div>

          {/* Form */}
          <form
            onSubmit={handleSubmit}
            className="mt-2 flex flex-col gap-1.5 pt-2 border-t border-border shrink-0"
          >
            {/* Provider + Model selectors — wrap on narrow containers */}
            {noToolCapableModels ? (
              <div role="status" aria-live="polite" className="text-xs text-text-secondary">
                No tool-capable models configured
              </div>
            ) : null}
            {chatProviders.length > 0 && !noToolCapableModels ? (
              <div className="flex flex-wrap gap-1.5">
                <div className="flex items-center gap-1 min-w-[120px] flex-1">
                  <label htmlFor="provider-select" className="text-xs text-text-secondary whitespace-nowrap shrink-0">
                    Provider
                  </label>
                  <select
                    id="provider-select"
                    value={selectedProvider}
                    onChange={(e) => handleProviderChange(e.target.value)}
                    title={chatProviders.find((p) => p.id === selectedProvider)?.name ?? ''}
                    className={selectClass}
                  >
                    {chatProviders.map((p) => (
                      <option key={p.id} value={p.id} title={p.name}>
                        {p.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="flex items-center gap-1 min-w-[140px] flex-1">
                  <label htmlFor="model-select" className="text-xs text-text-secondary whitespace-nowrap shrink-0">
                    Model
                  </label>
                  <select
                    id="model-select"
                    value={selectedModelId}
                    onChange={(e) => handleModelChange(e.target.value)}
                    title={resolvedModel?.model_name ?? selectedModelId}
                    className={selectClass}
                  >
                    {modelsForProvider.map((m) => (
                      <option key={m.model_id} value={m.model_id} title={m.model_name}>
                        {m.model_name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            ) : null}
            {lastSearchMode === 'tool_calling' ? (
              <div role="status" aria-live="polite" className="text-xs text-text-secondary">
                ⚡ Tool calling
              </div>
            ) : null}

            <label htmlFor="search-chat-input" className="sr-only">Message</label>
            <div className="flex gap-2 items-center">
              <Input
                id="search-chat-input"
                name="message"
                value={input}
                onChange={(ev) => setInput(ev.target.value)}
                fullWidth
                className="flex-1 min-w-0"
                autoComplete="off"
                disabled={status === 'loading' || noToolCapableModels}
                title={noToolCapableModels ? 'No tool-capable models configured' : undefined}
                placeholder={
                  noToolCapableModels
                    ? 'No tool-capable models configured'
                    : 'Ask about your library…'
                }
              />
              <Button
                type="submit"
                variant="primary"
                size="md"
                disabled={status === 'loading' || noToolCapableModels}
                title={noToolCapableModels ? 'No tool-capable models configured' : undefined}
              >
                {status === 'loading' ? '…' : 'Send'}
              </Button>
            </div>

            {status === 'error' && errorText != null && errorText !== '' ? (
              <p role="alert" className="text-red-500 text-xs mt-1">
                {errorText}
              </p>
            ) : null}
          </form>
        </div>

        {/* Results column */}
        <div className="w-full md:w-3/5">
          {status === 'loading' ? (
            <SkeletonGrid count={12} />
          ) : currentImages.length === 0 && messages.length === 0 ? (
            <div className="flex items-center justify-center h-full min-h-[200px]">
              <p className="text-text-secondary text-sm">Ask about your photos to see results here.</p>
            </div>
          ) : status === 'idle' && messages.length > 0 && currentImages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full min-h-[200px] gap-2 px-1">
              {pinnedImageKey ? (
                <p className="text-xs text-text-secondary self-stretch">
                  Pinned to{' '}
                  <span className="font-medium text-text">{pinnedImageKey}</span>
                </p>
              ) : null}
              {pinSimilarityWarning ? (
                <div role="status" aria-live="polite" className="text-xs text-amber-600 dark:text-amber-400 self-stretch space-y-1">
                  <p className="m-0">
                    {SEARCH_PIN_INACTIVE_PREFIX} {pinSimilarityWarning}. {SEARCH_PIN_INACTIVE_SUFFIX}
                  </p>
                  {pinInactiveReason === 'no_clip_embedding' ? (
                    <div className="space-y-1">
                      <p className="m-0">{SEARCH_PIN_HELP_EMBED}</p>
                      <div className="flex flex-wrap gap-x-3 gap-y-1">
                        <Link
                          to={PROCESSING_CATALOG_CACHE_ROUTE}
                          className="font-medium text-accent underline"
                        >
                          {SEARCH_PIN_LINK_CACHE}
                        </Link>
                        <Link
                          to={PROCESSING_JOB_QUEUE_ROUTE}
                          className="font-medium text-accent underline"
                        >
                          {PROCESSING_OPEN_JOB_QUEUE}
                        </Link>
                      </div>
                    </div>
                  ) : null}
                </div>
              ) : null}
              <p className="text-gray-500 text-sm">No matches found. Try a different query.</p>
            </div>
          ) : (
            <div className="transition-opacity duration-150">
              {pinnedImageKey ? (
                <p className="text-xs text-text-secondary mb-2">
                  Pinned to{' '}
                  <span className="font-medium text-text">
                    {currentImages.find((i) => i.key === pinnedImageKey)?.filename ??
                      pinnedImageKey}
                  </span>
                </p>
              ) : null}
              {pinSimilarityWarning ? (
                <div role="status" aria-live="polite" className="text-xs text-amber-600 dark:text-amber-400 mb-2 space-y-1">
                  <p className="m-0">
                    {SEARCH_PIN_INACTIVE_PREFIX} {pinSimilarityWarning}. {SEARCH_PIN_INACTIVE_SUFFIX}
                  </p>
                  {pinInactiveReason === 'no_clip_embedding' ? (
                    <div className="space-y-1">
                      <p className="m-0">{SEARCH_PIN_HELP_EMBED}</p>
                      <div className="flex flex-wrap gap-x-3 gap-y-1">
                        <Link
                          to={PROCESSING_CATALOG_CACHE_ROUTE}
                          className="font-medium text-accent underline"
                        >
                          {SEARCH_PIN_LINK_CACHE}
                        </Link>
                        <Link
                          to={PROCESSING_JOB_QUEUE_ROUTE}
                          className="font-medium text-accent underline"
                        >
                          {PROCESSING_OPEN_JOB_QUEUE}
                        </Link>
                      </div>
                    </div>
                  ) : null}
                </div>
              ) : null}
              <TileGrid>
                {currentImages.map((image) => (
                  <div
                    key={image.id != null ? String(image.id) : image.key}
                    className="relative"
                  >
                    <button
                      type="button"
                      aria-pressed={pinnedImageKey === image.key}
                      aria-label={
                        pinnedImageKey === image.key
                          ? 'Unpin image'
                          : 'Pin image for similarity search'
                      }
                      className={
                        'absolute top-1 right-1 z-10 rounded border px-1.5 py-0.5 text-[10px] font-medium shadow-sm ' +
                        (pinnedImageKey === image.key
                          ? 'border-primary bg-primary/15 text-primary'
                          : 'border-border bg-surface/95 text-text-secondary hover:text-text')
                      }
                      onClick={(e) => {
                        e.stopPropagation()
                        setPinnedImageKey((prev) => (prev === image.key ? null : image.key))
                      }}
                    >
                      {pinnedImageKey === image.key ? 'Pinned' : 'Pin'}
                    </button>
                    <ImageTile
                      image={fromCatalogListRow(image)}
                      variant="grid"
                      primaryScoreSource="catalog"
                      onClick={() => setSelectedImage({ key: image.key, initial: image })}
                    />
                  </div>
                ))}
              </TileGrid>
            </div>
          )}
        </div>
      </div>

      {selectedImage ? (
        <ImageDetailModal
          imageType="catalog"
          imageKey={selectedImage.key}
          initialImage={
            selectedImage.initial ? fromCatalogListRow(selectedImage.initial) : undefined
          }
          primaryScoreSource="catalog"
          onClose={() => setSelectedImage(null)}
        />
      ) : null}
    </div>
  )
}
