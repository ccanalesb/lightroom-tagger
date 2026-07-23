import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { IdentityPage } from './IdentityPage'
import { IdentityAPI } from '../services/api'
import { invalidateAll } from '../data'
import {
  EMPTY_MIRROR_RESPONSE,
  EMPTY_POST_NEXT_META,
} from '../__test-utils__/identityFixtures'
import {
  IDENTITY_ADVISOR_EMPTY_FALLBACK,
  IDENTITY_DIVIDER_BACKWARD,
  IDENTITY_DIVIDER_FORWARD,
  IDENTITY_MIRROR_EMPTY,
  IDENTITY_PAGE_TITLE,
  IDENTITY_SECTION_ADVISOR,
  IDENTITY_MIRROR_SECTION,
} from '../constants/strings'

describe('IdentityPage', () => {
  beforeEach(() => {
    invalidateAll(['identity'])
    vi.spyOn(IdentityAPI, 'getMirror').mockResolvedValue(EMPTY_MIRROR_RESPONSE)
    vi.spyOn(IdentityAPI, 'getSuggestions').mockResolvedValue({
      candidates: [],
      total: 0,
      meta: EMPTY_POST_NEXT_META,
      empty_state: null,
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders page title and section headings in narrative order', async () => {
    render(
      <MemoryRouter>
        <IdentityPage />
      </MemoryRouter>,
    )

    expect(screen.getByRole('heading', { level: 1, name: IDENTITY_PAGE_TITLE })).toBeInTheDocument()
    expect(
      await screen.findByRole('heading', { level: 2, name: IDENTITY_MIRROR_SECTION }),
    ).toBeInTheDocument()
    expect(
      await screen.findByRole('heading', { level: 2, name: IDENTITY_SECTION_ADVISOR }),
    ).toBeInTheDocument()

    const body = document.body.innerHTML
    expect(body.indexOf(IDENTITY_MIRROR_SECTION) < body.indexOf(IDENTITY_SECTION_ADVISOR)).toBe(
      true,
    )
    expect(screen.getByText(IDENTITY_DIVIDER_BACKWARD)).toBeInTheDocument()
    expect(screen.getByText(IDENTITY_DIVIDER_FORWARD)).toBeInTheDocument()
  })

  it('shows empty-state copy when APIs return no data', async () => {
    render(
      <MemoryRouter>
        <IdentityPage />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText(IDENTITY_MIRROR_EMPTY)).toBeInTheDocument()
    })
    await waitFor(() => {
      expect(screen.getByText(IDENTITY_ADVISOR_EMPTY_FALLBACK)).toBeInTheDocument()
    })
  })
})
