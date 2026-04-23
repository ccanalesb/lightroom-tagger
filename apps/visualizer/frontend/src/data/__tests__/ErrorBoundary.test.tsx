import { useState } from 'react'
import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ErrorBoundary } from '../ErrorBoundary'

function Throwing({ shouldThrow }: { shouldThrow: boolean }) {
  if (shouldThrow) throw new Error('boom')
  return <div>ok</div>
}

describe('ErrorBoundary', () => {
  it('catches render error and shows fallback', () => {
    render(
      <ErrorBoundary fallback={({ error }) => <div data-testid="fb">{error.message}</div>}>
        <Throwing shouldThrow />
      </ErrorBoundary>,
    )
    expect(screen.getByTestId('fb')).toHaveTextContent('boom')
  })

  it('reset clears error', () => {
    function ResetCase() {
      const [fail, setFail] = useState(true)
      return (
        <ErrorBoundary
          fallback={({ error, reset }) => (
            <div>
              <span data-testid="em">{error.message}</span>
              <button
                type="button"
                onClick={() => {
                  setFail(false)
                  reset()
                }}
              >
                recover
              </button>
            </div>
          )}
        >
          <Throwing shouldThrow={fail} />
        </ErrorBoundary>
      )
    }
    render(<ResetCase />)
    expect(screen.getByTestId('em')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'recover' }))
    expect(screen.getByText('ok')).toBeTruthy()
  })

  it('resetKeys change auto-resets', () => {
    function KeysCase() {
      const [id, setId] = useState(1)
      return (
        <div>
          <button type="button" onClick={() => setId(2)}>
            bump
          </button>
          <ErrorBoundary
            resetKeys={[id]}
            fallback={({ error }) => <div data-testid="fb2">{error.message}</div>}
          >
            <Throwing shouldThrow={id === 1} />
          </ErrorBoundary>
        </div>
      )
    }
    render(<KeysCase />)
    expect(screen.getByTestId('fb2')).toHaveTextContent('boom')
    fireEvent.click(screen.getByRole('button', { name: 'bump' }))
    expect(screen.getByText('ok')).toBeTruthy()
  })
})
