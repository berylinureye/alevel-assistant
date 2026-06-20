import { Component, type ErrorInfo, type ReactNode } from 'react'
import { trackEvent } from '../api/client'

interface Props {
  children: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('ErrorBoundary caught:', error, info.componentStack)
    trackEvent('ui_error', {
      kind: 'react_boundary',
      message: String(error.message || '').slice(0, 300),
      stack: String(error.stack || '').slice(0, 500),
    })
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-gray-50 px-4 py-16 text-center">
          <h1 className="text-xl font-bold text-red-700">页面出现异常</h1>
          <p className="mt-3 text-sm text-gray-600">
            {this.state.error?.message ?? '未知错误'}
          </p>
          <button
            onClick={() => {
              this.setState({ hasError: false, error: null })
            }}
            className="mt-6 rounded-md bg-blue-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-blue-700"
          >
            重试
          </button>
        </div>
      )
    }

    return this.props.children
  }
}
