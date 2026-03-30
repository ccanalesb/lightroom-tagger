import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { PageLoading, PageError, EmptyState } from '../page-states'

describe('PageLoading', () => {
  it('should render default loading message', () => {
    render(<PageLoading />)
    expect(screen.getByText('Loading...')).toBeTruthy()
  })

  it('should render custom message', () => {
    render(<PageLoading message="Fetching data..." />)
    expect(screen.getByText('Fetching data...')).toBeTruthy()
  })
})

describe('PageError', () => {
  it('should render error with prefix', () => {
    render(<PageError message="Server down" />)
    expect(screen.getByText(/Error:/)).toBeTruthy()
    expect(screen.getByText(/Server down/)).toBeTruthy()
  })
})

describe('EmptyState', () => {
  it('should render primary message', () => {
    render(<EmptyState message="No jobs found." />)
    expect(screen.getByText('No jobs found.')).toBeTruthy()
  })

  it('should render with optional sub-message', () => {
    render(<EmptyState message="No matches." hint="Run matching first." />)
    expect(screen.getByText('No matches.')).toBeTruthy()
    expect(screen.getByText('Run matching first.')).toBeTruthy()
  })

  it('should render without hint when not provided', () => {
    const { container } = render(<EmptyState message="Empty" />)
    const paragraphs = container.querySelectorAll('p')
    expect(paragraphs.length).toBe(1)
  })
})
