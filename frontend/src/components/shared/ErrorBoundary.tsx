/** Error boundary for graceful error handling. */
import { Component, type ReactNode } from 'react'
import * as styles from './ErrorBoundary.css'

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
        <div className={styles.container}>
          <h3 className={styles.heading}>Erro inesperado</h3>
          <p className={styles.message}>
            {this.state.error?.message || 'Algo deu errado'}
          </p>
          <button
            onClick={() => this.setState({ hasError: false })}
            className={styles.retryButton}
          >
            Tentar novamente
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
