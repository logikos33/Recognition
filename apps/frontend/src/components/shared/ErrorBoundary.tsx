/**
 * Error boundary — o estado de erro do front novo (`app/shell/Shell.tsx` o
 * monta por rota) e do antigo (`AppRoutes.tsx`).
 *
 * Issues #799/#800: este componente imprimia `error.message` CRU. Numa janela
 * de deploy no DEV isso pôs na tela do cliente o SELECT que falhou e o nome
 * interno do schema do tenant (`rvb_isolantes`). O detalhe agora vai para o
 * console (onde o time precisa dele) e a tela leva linguagem de gente.
 *
 * O erro NÃO é engolido: o usuário continua sabendo que falhou, e ganha dois
 * caminhos de saída — tentar de novo (remonta a tela) e voltar ao início (para
 * quando o retry só repete o erro).
 */
import { Component, type ReactNode } from 'react'
import { mensagemHumana } from '../../utils/errorTranslator'
import * as styles from './ErrorBoundary.css'

/**
 * Início da aplicação em que este boundary está montado — o front NOVO tem
 * `/novo` por raiz, o ANTIGO tem `/`, e o mesmo componente serve os dois
 * (`app/shell/Shell.tsx` e `AppRoutes.tsx`).
 *
 * Mandar `/` fixo é o "quinto furo" que `app/coexistencia.test.tsx` documenta:
 * troca de APLICAÇÃO calada — a pessoa clica para escapar do erro e cai no
 * produto velho, sem Shell e sem a identidade visual. A varredura daquele
 * teste só olha `src/app`, e este arquivo mora em `components/shared`; por
 * isso a guarda deste caso está em `test/utils/erroNaoVazaTripa.test.tsx`,
 * amarrada a `PREFIXO_NOVO`.
 */
export function inicioDaAplicacaoAtual(): string {
  const p = window.location.pathname
  return p === '/novo' || p.startsWith('/novo/') ? '/novo' : '/'
}

interface Props { children: ReactNode; fallback?: ReactNode }
interface State { hasError: boolean; error?: Error }

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, info: { componentStack?: string | null }): void {
    // Detalhe técnico: console, não tela.
    console.error('[ErrorBoundary]', error, info?.componentStack)
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback || (
        <div className={styles.container} role="alert">
          <h3 className={styles.heading}>Erro inesperado</h3>
          <p className={styles.message}>
            {mensagemHumana(this.state.error?.message ?? '')}
          </p>
          <button
            onClick={() => this.setState({ hasError: false, error: undefined })}
            className={styles.retryButton}
          >
            Tentar novamente
          </button>
          <button
            onClick={() => window.location.assign(inicioDaAplicacaoAtual())}
            className={styles.retryButton}
            style={{ marginLeft: 8 }}
          >
            Voltar ao início
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
