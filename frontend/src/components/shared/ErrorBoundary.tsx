/** Error boundary for graceful error handling. */
import { Component, type ReactNode } from 'react'

interface Props { children: ReactNode; fallback?: ReactNode }
interface State { hasError: boolean; error?: Error }

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback || (
        <div style={{
          padding: 32, textAlign: 'center', color: '#dc2626',
          background: '#fef2f2', borderRadius: 12, margin: 16,
        }}>
          <h3 style={{ margin: '0 0 8px' }}>Erro inesperado</h3>
          <p style={{ fontSize: 13, color: '#64748b' }}>
            {this.state.error?.message || 'Algo deu errado'}
          </p>
          <button
            onClick={() => this.setState({ hasError: false })}
            style={{
              marginTop: 12, padding: '8px 16px', borderRadius: 8,
              border: '1px solid #dc2626', background: 'white',
              color: '#dc2626', cursor: 'pointer', fontSize: 13,
            }}
          >
            Tentar novamente
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
