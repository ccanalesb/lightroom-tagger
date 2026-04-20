import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'
import { useBodyScrollLock } from '../useBodyScrollLock'

function Harness({ active }: { active: boolean }) {
  useBodyScrollLock(active)
  return null
}

describe('useBodyScrollLock', () => {
  it('sets body overflow hidden while active and restores prior value', () => {
    document.body.style.overflow = 'auto'
    const { unmount } = render(<Harness active />)
    expect(document.body.style.overflow).toBe('hidden')
    unmount()
    expect(document.body.style.overflow).toBe('auto')
  })

  it('preserves the original empty overflow on unmount', () => {
    document.body.style.overflow = ''
    const { unmount } = render(<Harness active />)
    expect(document.body.style.overflow).toBe('hidden')
    unmount()
    expect(document.body.style.overflow).toBe('')
  })

  it('is a no-op while inactive', () => {
    document.body.style.overflow = 'scroll'
    const { unmount } = render(<Harness active={false} />)
    expect(document.body.style.overflow).toBe('scroll')
    unmount()
    expect(document.body.style.overflow).toBe('scroll')
  })
})
