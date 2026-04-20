import { describe, it, expect } from 'vitest'
import { render, fireEvent } from '@testing-library/react'
import { useRef } from 'react'
import { useFocusTrap } from '../useFocusTrap'

function Harness({ active }: { active: boolean }) {
  const ref = useRef<HTMLDivElement>(null)
  useFocusTrap(ref, active)
  return (
    <div>
      <button type="button" data-testid="outside">
        outside
      </button>
      <div ref={ref} tabIndex={-1} data-testid="trap">
        <button type="button" data-testid="first">
          first
        </button>
        <button type="button" data-testid="middle">
          middle
        </button>
        <button type="button" data-testid="last">
          last
        </button>
      </div>
    </div>
  )
}

describe('useFocusTrap', () => {
  it('focuses the first focusable element when activated', () => {
    const { getByTestId } = render(<Harness active />)
    expect(document.activeElement).toBe(getByTestId('first'))
  })

  it('Tab on the last element wraps to the first', () => {
    const { getByTestId } = render(<Harness active />)
    const last = getByTestId('last')
    last.focus()
    fireEvent.keyDown(getByTestId('trap'), { key: 'Tab' })
    expect(document.activeElement).toBe(getByTestId('first'))
  })

  it('Shift+Tab on the first element wraps to the last', () => {
    const { getByTestId } = render(<Harness active />)
    fireEvent.keyDown(getByTestId('trap'), { key: 'Tab', shiftKey: true })
    expect(document.activeElement).toBe(getByTestId('last'))
  })

  it('does nothing when inactive', () => {
    render(<Harness active={false} />)
    expect(document.activeElement).toBe(document.body)
  })

  it('restores previously focused element on unmount', () => {
    const outside = document.createElement('button')
    document.body.appendChild(outside)
    outside.focus()
    expect(document.activeElement).toBe(outside)

    const { unmount, getByTestId } = render(<Harness active />)
    expect(document.activeElement).toBe(getByTestId('first'))
    unmount()
    expect(document.activeElement).toBe(outside)
    outside.remove()
  })
})
