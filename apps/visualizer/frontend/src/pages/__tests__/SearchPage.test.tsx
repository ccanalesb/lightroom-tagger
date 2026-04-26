import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { SearchPage } from '../SearchPage'
import { ImagesAPI, ProvidersAPI, type CatalogImage } from '../../services/api'

const sampleImage: CatalogImage = {
  id: 1,
  key: '2024-01-15_sample.jpg',
  filename: 'sample.jpg',
  filepath: '/tmp/sample.jpg',
  date_taken: '2024-01-15',
  rating: 4,
  pick: false,
  color_label: '',
  keywords: [],
  title: '',
  caption: '',
  copyright: '',
  width: 800,
  height: 600,
  instagram_posted: false,
}

const sampleImageB: CatalogImage = {
  ...sampleImage,
  id: 2,
  key: '2024-01-16_other.jpg',
  filename: 'other.jpg',
}

const descriptionModelsOk = {
  models: [
    {
      provider_id: 'p1',
      provider_name: 'Provider',
      model_id: 'm1',
      model_name: 'Model',
      tool_calling: true,
    },
  ],
  default_provider: 'p1',
  default_model: 'm1',
}

describe('SearchPage', () => {
  beforeEach(() => {
    vi.spyOn(ProvidersAPI, 'listDescriptionModels').mockResolvedValue(descriptionModelsOk)
    vi.spyOn(ImagesAPI, 'chatSearch').mockResolvedValue({
      search_mode: 'nl_filter',
      total: 1,
      images: [sampleImage],
      filters: { keyword: 'test' },
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('submits the chat form and shows results from chatSearch', async () => {
    render(
      <MemoryRouter>
        <SearchPage />
      </MemoryRouter>,
    )

    const input = screen.getByPlaceholderText(/Ask about your library/i)
    fireEvent.change(input, { target: { value: 'my test search' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))

    await waitFor(() => {
      expect(ImagesAPI.chatSearch).toHaveBeenCalled()
    })
    const call = vi.mocked(ImagesAPI.chatSearch).mock.calls[0][0]
    expect(call).toEqual(
      expect.objectContaining({
        message: 'my test search',
        messages: [],
        limit: 50,
      }),
    )

    expect(
      await screen.findByText(/Found 1 result\(s\)\./i),
    ).toBeInTheDocument()
    expect(await screen.findByText('sample.jpg')).toBeInTheDocument()
  })

  it('sends pinned_image_key after pinning a result', async () => {
    vi.mocked(ImagesAPI.chatSearch).mockResolvedValue({
      search_mode: 'nl_filter',
      total: 2,
      images: [sampleImage, sampleImageB],
      filters: {},
      metadata: { pin_state: 'active' },
    })

    render(
      <MemoryRouter>
        <SearchPage />
      </MemoryRouter>,
    )

    const input = screen.getByPlaceholderText(/Ask about your library/i)
    fireEvent.change(input, { target: { value: 'first' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))

    await screen.findByText('other.jpg')
    const pinOther = screen.getAllByRole('button', {
      name: 'Pin image for similarity search',
    })[1]!
    fireEvent.click(pinOther)

    fireEvent.change(input, { target: { value: 'second' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))

    await waitFor(() => {
      expect(vi.mocked(ImagesAPI.chatSearch).mock.calls.length).toBeGreaterThanOrEqual(2)
    })
    const last = vi.mocked(ImagesAPI.chatSearch).mock.calls.at(-1)![0]
    expect(last).toEqual(
      expect.objectContaining({
        message: 'second',
        pinned_image_key: sampleImageB.key,
      }),
    )
  })

  it('replacing pin updates which key is sent on the next search', async () => {
    vi.mocked(ImagesAPI.chatSearch).mockResolvedValue({
      search_mode: 'nl_filter',
      total: 2,
      images: [sampleImage, sampleImageB],
      filters: {},
    })

    render(
      <MemoryRouter>
        <SearchPage />
      </MemoryRouter>,
    )

    const input = screen.getByPlaceholderText(/Ask about your library/i)
    fireEvent.change(input, { target: { value: 'q' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))

    await screen.findByText('other.jpg')
    const [pinA, pinB] = screen.getAllByRole('button', {
      name: 'Pin image for similarity search',
    })
    fireEvent.click(pinA!)
    expect(await screen.findByText(/Pinned to/)).toHaveTextContent('sample.jpg')

    fireEvent.click(pinB!)
    expect(screen.getByText(/Pinned to/)).toHaveTextContent('other.jpg')

    fireEvent.change(input, { target: { value: 'q2' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))

    await waitFor(() => {
      expect(vi.mocked(ImagesAPI.chatSearch).mock.calls.length).toBeGreaterThanOrEqual(2)
    })
    const last = vi.mocked(ImagesAPI.chatSearch).mock.calls.at(-1)![0]
    expect(last).toEqual(
      expect.objectContaining({ pinned_image_key: sampleImageB.key }),
    )
  })

  it('shows inactive pin warning when backend marks pin inactive after similarity failure', async () => {
    vi.mocked(ImagesAPI.chatSearch)
      .mockResolvedValueOnce({
        search_mode: 'nl_filter',
        total: 1,
        images: [sampleImage],
        filters: {},
      })
      .mockResolvedValueOnce({
        search_mode: 'semantic',
        total: 0,
        images: [],
        filters: null,
        metadata: { pin_state: 'inactive', fallback_reason: 'no_clip_embedding' },
      })

    render(
      <MemoryRouter>
        <SearchPage />
      </MemoryRouter>,
    )

    const input = screen.getByPlaceholderText(/Ask about your library/i)
    fireEvent.change(input, { target: { value: 'one' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))

    await screen.findByText('sample.jpg')
    fireEvent.click(
      screen.getByRole('button', { name: 'Pin image for similarity search' }),
    )

    fireEvent.change(input, { target: { value: 'two' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))

    const warn = await screen.findByRole('status')
    expect(warn).toHaveTextContent(/Similarity pin inactive/)
    expect(warn).toHaveTextContent(/CLIP embedding missing/)
  })

  it('end-to-end: replaced pin is the key sent when the next turn returns inactive pin', async () => {
    vi.mocked(ImagesAPI.chatSearch)
      .mockResolvedValueOnce({
        search_mode: 'nl_filter',
        total: 2,
        images: [sampleImage, sampleImageB],
        filters: {},
      })
      .mockResolvedValueOnce({
        search_mode: 'nl_filter',
        total: 2,
        images: [sampleImage, sampleImageB],
        filters: {},
        metadata: { pin_state: 'active' },
      })
      .mockResolvedValueOnce({
        search_mode: 'nl_filter',
        total: 2,
        images: [sampleImage, sampleImageB],
        filters: {},
        metadata: { pin_state: 'active' },
      })
      .mockResolvedValueOnce({
        search_mode: 'semantic',
        total: 0,
        images: [],
        filters: null,
        metadata: { pin_state: 'inactive', fallback_reason: 'no_clip_embedding' },
      })

    render(
      <MemoryRouter>
        <SearchPage />
      </MemoryRouter>,
    )

    const input = screen.getByPlaceholderText(/Ask about your library/i)
    fireEvent.change(input, { target: { value: 'open' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))

    await screen.findByText('other.jpg')
    const [pinFirst] = screen.getAllByRole('button', {
      name: 'Pin image for similarity search',
    })
    fireEvent.click(pinFirst!)
    fireEvent.change(input, { target: { value: 'with A' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))

    await waitFor(() => {
      expect(vi.mocked(ImagesAPI.chatSearch).mock.calls.length).toBeGreaterThanOrEqual(2)
    })
    expect(vi.mocked(ImagesAPI.chatSearch).mock.calls.at(-1)![0]).toEqual(
      expect.objectContaining({ pinned_image_key: sampleImage.key }),
    )

    fireEvent.click(
      screen.getByRole('button', { name: 'Pin image for similarity search' }),
    )
    fireEvent.change(input, { target: { value: 'with B' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))

    await waitFor(() => {
      expect(vi.mocked(ImagesAPI.chatSearch).mock.calls.length).toBeGreaterThanOrEqual(3)
    })
    expect(vi.mocked(ImagesAPI.chatSearch).mock.calls.at(-1)![0]).toEqual(
      expect.objectContaining({ pinned_image_key: sampleImageB.key }),
    )

    fireEvent.change(input, { target: { value: 'similarity fail' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))

    const warn = await screen.findByRole('status')
    expect(warn).toHaveTextContent(/Similarity pin inactive/)
  })
})
