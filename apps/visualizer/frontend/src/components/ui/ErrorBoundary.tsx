import { Component, type ErrorInfo, type ReactNode } from 'react'
import { PageError } from './page-states'

interface State {
  error: Error | null
}

class ErrorCatcher extends Component<{ children: ReactNode; fallback: (error: Error) => ReactNode }, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('[ErrorBoundary]', error, info.componentStack)
  }

  render() {
    if (this.state.error) return this.props.fallback(this.state.error)
    return this.props.children
  }
}

export function ErrorBoundary({ children, fallbackMessage }: { children: ReactNode; fallbackMessage?: string }) {
  return (
    <ErrorCatcher fallback={(error) => <PageError message={fallbackMessage ?? error.message} />}>
      {children}
    </ErrorCatcher>
  )
}
