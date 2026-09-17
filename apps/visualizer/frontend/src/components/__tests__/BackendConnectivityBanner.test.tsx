import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, act } from '@testing-library/react'
import { BackendConnectivityBanner } from '../BackendConnectivityBanner'
import { useBackendHealthStore } from '../../stores/backendHealthStore'
import { useSocketStore } from '../../stores/socketStore'

describe('BackendConnectivityBanner', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    useSocketStore.setState({ socket: null, connected: false })
    useBackendHealthStore.setState({ httpBusy: false })
  })

  afterEach(() => {
    vi.useRealTimers()
    useSocketStore.setState({ socket: null, connected: false })
    useBackendHealthStore.setState({ httpBusy: false })
  })

  it('renders nothing while connected', () => {
    useSocketStore.setState({ socket: {} as never, connected: true })

    const { container } = render(<BackendConnectivityBanner />)

    expect(container.textContent).toBe('')
  })

  it('renders nothing before the disconnect grace period elapses', () => {
    useSocketStore.setState({ socket: {} as never, connected: false })

    const { container } = render(<BackendConnectivityBanner />)

    act(() => {
      vi.advanceTimersByTime(1_999)
    })

    expect(container.textContent).toBe('')
  })

  it('renders the alert after the socket stays disconnected', async () => {
    useSocketStore.setState({ socket: {} as never, connected: false })

    render(<BackendConnectivityBanner />)

    await act(async () => {
      vi.advanceTimersByTime(2_000)
    })

    expect(screen.getByTestId('backend-connectivity-banner')).toBeTruthy()
    expect(screen.getByText('Backend unreachable')).toBeTruthy()
  })

  it('renders the busy banner when HTTP requests time out', () => {
    useSocketStore.setState({ socket: {} as never, connected: true })
    useBackendHealthStore.setState({ httpBusy: true })

    render(<BackendConnectivityBanner />)

    expect(screen.getByTestId('backend-busy-banner')).toBeTruthy()
    expect(screen.getByText('Backend busy')).toBeTruthy()
  })
})
