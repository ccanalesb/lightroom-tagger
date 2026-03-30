import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { GenerateButton, DescriptionMeta } from '../description-atoms'

describe('GenerateButton', () => {
  it('shows Generate when no description exists', () => {
    render(<GenerateButton hasDescription={false} generating={false} onClick={vi.fn()} />)
    expect(screen.getByText('Generate')).toBeTruthy()
  })

  it('shows Regenerate when description exists', () => {
    render(<GenerateButton hasDescription={true} generating={false} onClick={vi.fn()} />)
    expect(screen.getByText('Regenerate')).toBeTruthy()
  })

  it('shows Generating... when generating', () => {
    render(<GenerateButton hasDescription={false} generating={true} onClick={vi.fn()} />)
    expect(screen.getByText('Generating...')).toBeTruthy()
  })

  it('is disabled when generating', () => {
    render(<GenerateButton hasDescription={false} generating={true} onClick={vi.fn()} />)
    expect((screen.getByRole('button') as HTMLButtonElement).disabled).toBe(true)
  })

  it('calls onClick and stops event propagation', () => {
    const onClick = vi.fn()
    render(<GenerateButton hasDescription={false} generating={false} onClick={onClick} />)
    fireEvent.click(screen.getByRole('button'))
    expect(onClick).toHaveBeenCalledOnce()
  })

  it('uses primary style when no description', () => {
    const { container } = render(<GenerateButton hasDescription={false} generating={false} onClick={vi.fn()} />)
    expect(container.firstElementChild!.className).toContain('bg-indigo')
  })

  it('uses secondary style when description exists', () => {
    const { container } = render(<GenerateButton hasDescription={true} generating={false} onClick={vi.fn()} />)
    expect(container.firstElementChild!.className).toContain('border')
    expect(container.firstElementChild!.className).not.toContain('bg-indigo')
  })
})

describe('DescriptionMeta', () => {
  it('renders model when provided', () => {
    render(<DescriptionMeta model="qwen3" />)
    expect(screen.getByText(/qwen3/)).toBeTruthy()
  })

  it('renders date when provided', () => {
    render(<DescriptionMeta describedAt="2026-03-15T10:00:00Z" />)
    const text = screen.getByText(/2026/)
    expect(text).toBeTruthy()
  })

  it('renders source label for catalog', () => {
    render(<DescriptionMeta imageType="catalog" hasDescription />)
    expect(screen.getByText(/catalog/i)).toBeTruthy()
  })

  it('renders nothing when all props are empty', () => {
    const { container } = render(<DescriptionMeta />)
    expect(container.textContent).toBe('')
  })
})
