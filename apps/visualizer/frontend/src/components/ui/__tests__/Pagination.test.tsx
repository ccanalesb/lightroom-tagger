import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { Pagination } from '../Pagination'

describe('Pagination', () => {
  it('renders current page and total pages', () => {
    render(<Pagination currentPage={2} totalPages={5} onPageChange={vi.fn()} />)
    expect(screen.getByText(/Page 2 of 5/)).toBeTruthy()
  })

  it('calls onPageChange with previous page', () => {
    const onChange = vi.fn()
    render(<Pagination currentPage={3} totalPages={5} onPageChange={onChange} />)
    fireEvent.click(screen.getByText('← Previous'))
    expect(onChange).toHaveBeenCalledWith(2)
  })

  it('calls onPageChange with next page', () => {
    const onChange = vi.fn()
    render(<Pagination currentPage={3} totalPages={5} onPageChange={onChange} />)
    fireEvent.click(screen.getByText('Next →'))
    expect(onChange).toHaveBeenCalledWith(4)
  })

  it('disables previous on first page', () => {
    render(<Pagination currentPage={1} totalPages={5} onPageChange={vi.fn()} />)
    const prev = screen.getByText('← Previous')
    expect((prev as HTMLButtonElement).disabled).toBe(true)
  })

  it('disables next on last page', () => {
    render(<Pagination currentPage={5} totalPages={5} onPageChange={vi.fn()} />)
    const next = screen.getByText('Next →')
    expect((next as HTMLButtonElement).disabled).toBe(true)
  })

  it('does not render when totalPages <= 1', () => {
    const { container } = render(<Pagination currentPage={1} totalPages={1} onPageChange={vi.fn()} />)
    expect(container.firstElementChild).toBeNull()
  })
})
