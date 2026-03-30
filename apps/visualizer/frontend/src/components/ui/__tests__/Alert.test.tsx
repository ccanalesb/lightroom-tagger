import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { Alert } from '../Alert'

describe('Alert', () => {
  it('should render message for success tone', () => {
    render(<Alert tone="success" message="Job completed!" />)
    expect(screen.getByText('Job completed!')).toBeTruthy()
  })

  it('should render message for danger tone', () => {
    render(<Alert tone="danger" message="Something failed" />)
    expect(screen.getByText('Something failed')).toBeTruthy()
  })

  it('should render message for info tone', () => {
    render(<Alert tone="info" message="Processing..." />)
    expect(screen.getByText('Processing...')).toBeTruthy()
  })

  it('should render message for warning tone', () => {
    render(<Alert tone="warning" message="Check config" />)
    expect(screen.getByText('Check config')).toBeTruthy()
  })

  it('should apply green classes for success', () => {
    const { container } = render(<Alert tone="success" message="Done" />)
    const alert = container.firstElementChild!
    expect(alert.className).toContain('bg-green')
    expect(alert.className).toContain('border-green')
  })

  it('should apply red classes for danger', () => {
    const { container } = render(<Alert tone="danger" message="Fail" />)
    const alert = container.firstElementChild!
    expect(alert.className).toContain('bg-red')
    expect(alert.className).toContain('border-red')
  })

  it('should render dismiss button when onDismiss provided', () => {
    const onDismiss = vi.fn()
    render(<Alert tone="success" message="Done" onDismiss={onDismiss} />)
    const btn = screen.getByRole('button')
    fireEvent.click(btn)
    expect(onDismiss).toHaveBeenCalledOnce()
  })

  it('should not render dismiss button when onDismiss not provided', () => {
    render(<Alert tone="info" message="Info" />)
    expect(screen.queryByRole('button')).toBeNull()
  })

  it('should render children as secondary content', () => {
    render(
      <Alert tone="info" message="Primary">
        <span>Secondary detail</span>
      </Alert>
    )
    expect(screen.getByText('Secondary detail')).toBeTruthy()
  })
})
