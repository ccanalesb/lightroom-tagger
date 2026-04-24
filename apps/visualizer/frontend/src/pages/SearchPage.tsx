import { FormEvent, useState } from 'react'
import { ImageDetailModal, ImageTile, fromCatalogListRow } from '../components/image-view'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { TileGrid } from '../components/ui/TileGrid'
import { SkeletonGrid } from '../components/ui/page-states'
import { ImagesAPI, type CatalogImage } from '../services/api'

type Message = {
  role: 'user' | 'assistant'
  content: string
  images?: CatalogImage[]
  search_mode?: string
}

type SelectedImage = { key: string; initial?: CatalogImage }

export function SearchPage() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [status, setStatus] = useState<'idle' | 'loading' | 'error'>('idle')
  const [errorText, setErrorText] = useState<string | null>(null)
  const [currentImages, setCurrentImages] = useState<CatalogImage[]>([])
  const [selectedImage, setSelectedImage] = useState<SelectedImage | null>(null)

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
      const data = await ImagesAPI.chatSearch({ message: trimmed, messages: prior, limit: 50 })
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
