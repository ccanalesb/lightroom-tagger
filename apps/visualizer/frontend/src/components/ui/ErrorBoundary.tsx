import { Component, type ErrorInfo, type ReactNode } from 'react'
import { PageError } from './page-states'

interface Props {
  children: ReactNode
  fallbackMessage?: string
}

interface State {
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('[ErrorBoundary]', error, info.componentStack)
  }

  render() {
    if (this.state.error) {
      return (
        <PageError
          message={this.props.fallbackMessage ?? this.state.error.message}
        />
      )
    }
    return this.props.children
  }
}
