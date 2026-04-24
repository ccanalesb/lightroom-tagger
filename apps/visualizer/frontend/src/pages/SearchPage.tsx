import { FormEvent, useEffect, useState } from 'react'
import { ImageDetailModal, ImageTile, fromCatalogListRow } from '../components/image-view'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { TileGrid } from '../components/ui/TileGrid'
import { SkeletonGrid } from '../components/ui/page-states'
import {
  ImagesAPI,
  ProvidersAPI,
  type CatalogImage,
  type ChatSearchResultImage,
  type DescriptionModel,
} from '../services/api'

const PROVIDER_STORAGE_KEY = 'search:selected_provider'
const MODEL_STORAGE_KEY = 'search:selected_model'

type Message = {
  role: 'user' | 'assistant'
  content: string
  images?: ChatSearchResultImage[]
  search_mode?: 'nl_filter' | 'semantic'
}

type SelectedImage = { key: string; initial?: CatalogImage }

export function SearchPage() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [status, setStatus] = useState<'idle' | 'loading' | 'error'>('idle')
  const [errorText, setErrorText] = useState<string | null>(null)
  const [currentImages, setCurrentImages] = useState<ChatSearchResultImage[]>([])
  const [selectedImage, setSelectedImage] = useState<SelectedImage | null>(null)

  const [allModels, setAllModels] = useState<DescriptionModel[]>([])
  const [selectedProvider, setSelectedProvider] = useState<string>(
    () => localStorage.getItem(PROVIDER_STORAGE_KEY) ?? '',
  )
  const [selectedModelId, setSelectedModelId] = useState<string>(
    () => localStorage.getItem(MODEL_STORAGE_KEY) ?? '',
  )

  useEffect(() => {
    ProvidersAPI.listDescriptionModels()
      .then(({ models, default_provider, default_model }) => {
        setAllModels(models)

        setSelectedProvider((prev) => {
          if (prev && models.some((m) => m.provider_id === prev)) return prev
          return default_provider ?? models[0]?.provider_id ?? ''
        })

        setSelectedModelId((prev) => {
          if (prev && models.some((m) => m.model_id === prev)) return prev
          return default_model ?? models[0]?.model_id ?? ''
        })
      })
      .catch(() => {
        // non-fatal — selectors stay empty, backend uses its own default
      })
  }, [])

  const providers = Array.from(
    new Map(allModels.map((m) => [m.provider_id, m.provider_name])).entries(),
  ).map(([id, name]) => ({ id, name }))

  const modelsForProvider = allModels.filter((m) => m.provider_id === selectedProvider)

  const handleProviderChange = (pid: string) => {
    setSelectedProvider(pid)
    localStorage.setItem(PROVIDER_STORAGE_KEY, pid)
    const first = allModels.find((m) => m.provider_id === pid)
    if (first) {
      setSelectedModelId(first.model_id)
      localStorage.setItem(MODEL_STORAGE_KEY, first.model_id)
    }
  }

  const handleModelChange = (mid: string) => {
    setSelectedModelId(mid)
    localStorage.setItem(MODEL_STORAGE_KEY, mid)
  }

  const resolvedModel = allModels.find(
    (m) => m.provider_id === selectedProvider && m.model_id === selectedModelId,
  )

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    const trimmed = input.trim()
    if (!trimmed || status === 'loading') return

    const prior = messages
      .filter((m): m is Message & { role: 'user' | 'assistant' } =>
        m.role === 'user' || m.role === 'assistant',
      )
      .map((m) => ({ role: m.role, content: m.content }))

    setErrorText(null)
    setStatus('loading')
    setMessages((prev) => [...prev, { role: 'user', content: trimmed }])

    try {
      const data = await ImagesAPI.chatSearch({
        message: trimmed,
        messages: prior,
        limit: 50,
        model: resolvedModel?.model_id,
      })
      setCurrentImages(data.images)
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: `Found ${data.total} result(s) (${data.search_mode}).`,
          search_mode: data.search_mode,
        },
      ])
      setInput('')
      setStatus('idle')
    } catch (err) {
      setErrorText(err instanceof Error ? err.message : String(err))
      setStatus('error')
    }
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-section text-text mb-2">Search</h1>
        <p className="text-text-secondary">Ask questions in natural language; results update on each message.</p>
      </div>

      <div className="flex flex-col md:flex-row gap-6 h-full min-h-[60vh]">
        <div className="w-full md:w-2/5 flex flex-col min-h-[320px]">
            <div className="flex-1 overflow-y-auto space-y-3 min-h-0">
              {messages.map((m, i) => (
                <div
                  key={i}
                  className={m.role === 'user' ? 'flex justify-end' : 'flex justify-start'}
                >
                  <div
                    className={
                      m.role === 'user'
                        ? 'max-w-[85%] rounded-lg border border-border bg-surface px-3 py-2 text-sm text-right text-text'
                        : 'max-w-[85%] rounded-lg border border-border bg-surface px-3 py-2 text-sm text-left text-text'
                    }
                  >
                    {m.content}
                  </div>
                </div>
              ))}
            </div>
            <form
              onSubmit={handleSubmit}
              className="mt-auto flex flex-col gap-2 pt-2 border-t border-border shrink-0"
            >
              {providers.length > 0 && (
                <div className="flex gap-2">
                  <div className="flex items-center gap-1.5 flex-1 min-w-0">
                    <label htmlFor="provider-select" className="text-xs text-text-secondary whitespace-nowrap">
                      Provider
                    </label>
                    <select
                      id="provider-select"
                      value={selectedProvider}
                      onChange={(e) => handleProviderChange(e.target.value)}
                      className="flex-1 min-w-0 rounded border border-border bg-surface px-2 py-1 text-xs text-text focus:outline-none focus:ring-1 focus:ring-primary"
                    >
                      {providers.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.name}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="flex items-center gap-1.5 flex-1 min-w-0">
                    <label htmlFor="model-select" className="text-xs text-text-secondary whitespace-nowrap">
                      Model
                    </label>
                    <select
                      id="model-select"
                      value={selectedModelId}
                      onChange={(e) => handleModelChange(e.target.value)}
                      className="flex-1 min-w-0 rounded border border-border bg-surface px-2 py-1 text-xs text-text focus:outline-none focus:ring-1 focus:ring-primary"
                    >
                      {modelsForProvider.map((m) => (
                        <option key={m.model_id} value={m.model_id}>
                          {m.model_name}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
              )}
              <label htmlFor="search-chat-input" className="sr-only">
                Message
              </label>
              <div className="flex gap-2 items-end">
                <Input
                  id="search-chat-input"
                  name="message"
                  value={input}
                  onChange={(ev) => setInput(ev.target.value)}
                  fullWidth
                  className="flex-1"
                  autoComplete="off"
                  disabled={status === 'loading'}
                  placeholder="Ask about your library…"
                />
                <Button
                  type="submit"
                  variant="primary"
                  size="md"
                  disabled={status === 'loading'}
                >
                  Send
                </Button>
              </div>
              {status === 'error' && errorText != null && errorText !== '' ? (
                <p role="alert" className="text-red-500 text-sm mt-2">
                  {errorText}
                </p>
              ) : null}
            </form>
          </div>

          <div className="w-full md:w-3/5">
            {status === 'loading' ? (
              <SkeletonGrid count={12} />
            ) : currentImages.length === 0 && messages.length === 0 ? (
              <p className="text-center text-text-secondary mt-8">Ask about your photos...</p>
            ) : status === 'idle' && messages.length > 0 && currentImages.length === 0 ? (
              <p className="text-center text-gray-500 mt-8">No matches found. Try a different query.</p>
            ) : (
              <div className="relative transition-opacity duration-150">
                <TileGrid>
                  {currentImages.map((image) => (
                    <ImageTile
                      key={image.id != null ? String(image.id) : image.key}
                      image={fromCatalogListRow(image)}
                      variant="grid"
                      primaryScoreSource="catalog"
                      onClick={() => setSelectedImage({ key: image.key, initial: image })}
                    />
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
