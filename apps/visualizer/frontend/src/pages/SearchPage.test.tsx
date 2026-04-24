import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { SearchPage } from './SearchPage'
import { ImagesAPI, type CatalogImage } from '../services/api'

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

describe('SearchPage', () => {
  beforeEach(() => {
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
      await screen.findByText(/Found 1 result\(s\) \(nl_filter\)\./i),
    ).toBeInTheDocument()
    expect(await screen.findByText('sample.jpg')).toBeInTheDocument()
  })
})
