import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { GenerateButton, DescriptionMeta } from '../description-atoms'

describe('GenerateButton', () => {
  it('should show Generate when no description exists', () => {
    render(<GenerateButton hasDescription={false} generating={false} onClick={vi.fn()} />)
    expect(screen.getByText('Generate')).toBeTruthy()
  })

  it('should show Regenerate when description exists', () => {
    render(<GenerateButton hasDescription={true} generating={false} onClick={vi.fn()} />)
    expect(screen.getByText('Regenerate')).toBeTruthy()
  })

  it('should show Generating... when generating', () => {
    render(<GenerateButton hasDescription={false} generating={true} onClick={vi.fn()} />)
    expect(screen.getByText('Generating...')).toBeTruthy()
  })

  it('should be disabled when generating', () => {
    render(<GenerateButton hasDescription={false} generating={true} onClick={vi.fn()} />)
    expect((screen.getByRole('button') as HTMLButtonElement).disabled).toBe(true)
  })

  it('should call onClick and stop event propagation', () => {
    const onClick = vi.fn()
    render(<GenerateButton hasDescription={false} generating={false} onClick={onClick} />)
    fireEvent.click(screen.getByRole('button'))
    expect(onClick).toHaveBeenCalledOnce()
  })

  it('should use primary style when no description', () => {
    const { container } = render(<GenerateButton hasDescription={false} generating={false} onClick={vi.fn()} />)
    expect(container.firstElementChild!.className).toContain('bg-indigo')
  })

  it('should use secondary style when description exists', () => {
    const { container } = render(<GenerateButton hasDescription={true} generating={false} onClick={vi.fn()} />)
    expect(container.firstElementChild!.className).toContain('border')
    expect(container.firstElementChild!.className).not.toContain('bg-indigo')
  })
})

describe('DescriptionMeta', () => {
  it('should render model when provided', () => {
    render(<DescriptionMeta model="qwen3" />)
    expect(screen.getByText(/qwen3/)).toBeTruthy()
  })

  it('should render date when provided', () => {
    render(<DescriptionMeta describedAt="2026-03-15T10:00:00Z" />)
    const text = screen.getByText(/2026/)
    expect(text).toBeTruthy()
  })

  it('should render source label for catalog', () => {
    render(<DescriptionMeta imageType="catalog" hasDescription />)
    expect(screen.getByText(/catalog/i)).toBeTruthy()
  })

  it('should render nothing when all props are empty', () => {
    const { container } = render(<DescriptionMeta />)
    expect(container.textContent).toBe('')
  })
})
