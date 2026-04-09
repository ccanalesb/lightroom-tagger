import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { Pagination } from '../Pagination'

describe('Pagination', () => {
  it('should render current page as selected among page numbers', () => {
    render(<Pagination currentPage={2} totalPages={5} onPageChange={vi.fn()} />)
    const current = screen.getByRole('button', { name: '2' })
    expect(current.className).toContain('border-accent')
  })

  it('should call onPageChange with previous page', () => {
    const onChange = vi.fn()
    render(<Pagination currentPage={3} totalPages={5} onPageChange={onChange} />)
    fireEvent.click(screen.getByRole('button', { name: 'Previous page' }))
    expect(onChange).toHaveBeenCalledWith(2)
  })

  it('should call onPageChange with next page', () => {
    const onChange = vi.fn()
    render(<Pagination currentPage={3} totalPages={5} onPageChange={onChange} />)
    fireEvent.click(screen.getByRole('button', { name: 'Next page' }))
    expect(onChange).toHaveBeenCalledWith(4)
  })

  it('should disable previous on first page', () => {
    render(<Pagination currentPage={1} totalPages={5} onPageChange={vi.fn()} />)
    expect(screen.getByRole('button', { name: 'Previous page' })).toBeDisabled()
  })

  it('should disable next on last page', () => {
    render(<Pagination currentPage={5} totalPages={5} onPageChange={vi.fn()} />)
    expect(screen.getByRole('button', { name: 'Next page' })).toBeDisabled()
  })

  it('should not render when totalPages <= 1', () => {
    const { container } = render(<Pagination currentPage={1} totalPages={1} onPageChange={vi.fn()} />)
    expect(container.firstElementChild).toBeNull()
  })

  it('should disable all controls when disabled', () => {
    render(<Pagination currentPage={2} totalPages={5} onPageChange={vi.fn()} disabled />)
    expect(screen.getByRole('button', { name: 'Previous page' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Next page' })).toBeDisabled()
    expect(screen.getByRole('button', { name: '1' })).toBeDisabled()
    expect(screen.getByRole('button', { name: '2' })).toBeDisabled()
  })
})
