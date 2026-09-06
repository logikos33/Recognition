/**
 * Issues #799/#800 — a tela do cliente não mostra SQL cru nem o nome interno
 * do schema do tenant.
 *
 * MEDIDO no DEV, numa janela de deploy: qualquer uma das 8 telas do EPI
 * imprimia o SELECT que falhou e `rvb_isolantes`, além de um
 * `503 connection pool exhausted` cru. O `api.ts` monta `ApiError.message` a
 * partir do corpo do servidor e ~40 telas jogam esse texto na tela via
 * `e.message`; o `ErrorBoundary` (estado de erro do front novo, montado por
 * rota em `app/shell/Shell.tsx`) fazia o mesmo com o erro de render.
 *
 * PROVA POR MUTAÇÃO (reintroduzindo o defeito):
 *   - `mensagemHumana` virar `return rawMessage || ...`, ou
 *   - o `ErrorBoundary` voltar a renderizar `{this.state.error?.message}`,
 *   deixa este arquivo VERMELHO. Rodado antes de commitar.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { mensagemHumana, translateError, showErrorToast } from '../../utils/errorTranslator'
import { ErrorBoundary, inicioDaAplicacaoAtual } from '../../components/shared/ErrorBoundary'
import { PREFIXO_NOVO } from '../../app/RotasNovas'
import { useToastStore } from '../../components/ui/Toast/useToast'

/** Tripa que não pode aparecer em texto de tela. */
const PROIBIDO =
  /select\s|insert\s+into|delete\s+from|relation\s+"|column\s+"|psycopg|traceback|connection\s+pool|search_path|postgres(?:ql)?:\/\/|rvb_isolantes/i

// Textos reais colhidos no DEV.
const SQL_CRU =
  'ERRO: relation "rvb_isolantes.alerts" does not exist\nLINE 1: SELECT id FROM rvb_isolantes.alerts WHERE tenant_id = $1'
const POOL_CRU = 'psycopg2.OperationalError: connection pool exhausted'
const CONNSTR_CRU = 'could not connect to server: postgresql://recognition:s3nh4@db.internal:5432/rec'
const SCHEMA_CRU = 'Schema inválido: rvb_isolantes'

const CRUS = [SQL_CRU, POOL_CRU, CONNSTR_CRU, SCHEMA_CRU]

describe('mensagemHumana — a segunda tranca do front', () => {
  it.each(CRUS)('troca texto com tripa: %s', (cru) => {
    const saida = mensagemHumana(cru, 500)
    expect(saida).not.toBe(cru)
    expect(PROIBIDO.test(saida)).toBe(false)
  })

  it.each([
    'Câmera não encontrada (abc-123)',
    'Maria já avaliou este alerta há 2 minutos',
    'Arquivo excede o limite de 25MB',
    'Sessão expirada',
    'Sem permissão para esta ação.',
  ])('não mexe em mensagem de gente: %s', (boa) => {
    expect(mensagemHumana(boa, 400)).toBe(boa)
  })

  it('não engole o erro — sempre devolve alguma frase', () => {
    expect(mensagemHumana('', 500).length).toBeGreaterThan(0)
    expect(mensagemHumana(SQL_CRU, 500).length).toBeGreaterThan(0)
  })

  it('não põe número de HTTP na tela', () => {
    for (const status of [400, 403, 404, 500, 502, 503]) {
      expect(mensagemHumana('', status)).not.toMatch(/\b[45]\d\d\b/)
      expect(translateError(status, '/alerts', SQL_CRU)).not.toMatch(/\b[45]\d\d\b/)
    }
  })
})

describe('translateError — o que vira toast', () => {
  it.each(CRUS)('nunca ecoa o texto cru do servidor: %s', (cru) => {
    expect(PROIBIDO.test(translateError(500, '/alerts', cru))).toBe(false)
  })

  it('sem mensagem do servidor não cai em "Erro 500"', () => {
    expect(translateError(500, '/alerts', '')).not.toMatch(/\d{3}/)
  })
})

describe('toast automático do api.ts', () => {
  beforeEach(() => useToastStore.setState({ toasts: [] }))

  it('avisa que falhou, mas sem o SQL junto', () => {
    showErrorToast(500, '/alerts', SQL_CRU)
    const t = useToastStore.getState().toasts
    expect(t).toHaveLength(1)
    expect(t[0].variant).toBe('error')
    expect(PROIBIDO.test(t[0].title)).toBe(false)
  })
})

describe('ErrorBoundary — o estado de erro do front novo', () => {
  beforeEach(() => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
  })

  const TelaQueEstoura = ({ msg }: { msg: string }) => {
    throw new Error(msg)
  }

  it.each([...CRUS, "Cannot read properties of undefined (reading 'map')"])(
    'não imprime a tripa do erro: %s',
    (cru) => {
      const { container } = render(
        <ErrorBoundary>
          <TelaQueEstoura msg={cru} />
        </ErrorBoundary>,
      )
      expect(PROIBIDO.test(container.textContent ?? '')).toBe(false)
      expect(container.textContent).not.toContain(cru)
    },
  )

  it('diz que falhou e dá dois caminhos de saída', () => {
    render(
      <ErrorBoundary>
        <TelaQueEstoura msg={SQL_CRU} />
      </ErrorBoundary>,
    )
    expect(screen.getByText(/erro inesperado/i)).toBeTruthy()
    expect(screen.getByRole('button', { name: /tentar novamente/i })).toBeTruthy()
    expect(screen.getByRole('button', { name: /voltar ao início/i })).toBeTruthy()
  })

  it('"tentar novamente" remonta a tela — não é beco sem saída', () => {
    let estoura = true
    const Tela = () => {
      if (estoura) throw new Error(SQL_CRU)
      return <p>conteúdo de volta</p>
    }
    render(
      <ErrorBoundary>
        <Tela />
      </ErrorBoundary>,
    )
    estoura = false
    fireEvent.click(screen.getByRole('button', { name: /tentar novamente/i }))
    expect(screen.getByText('conteúdo de volta')).toBeTruthy()
  })

  it('o detalhe técnico vai para o console — some da tela, não do time', () => {
    render(
      <ErrorBoundary>
        <TelaQueEstoura msg={SQL_CRU} />
      </ErrorBoundary>,
    )
    const chamadas = (console.error as unknown as { mock: { calls: unknown[][] } }).mock.calls
    expect(
      chamadas.some((c) => c.some((a) => a instanceof Error && a.message === SQL_CRU)),
    ).toBe(true)
  })
})

/**
 * A saída de emergência não pode trocar de APLICAÇÃO (achado do cético, 06/09).
 *
 * O `ErrorBoundary` serve os DOIS fronts, e `app/coexistencia.test.tsx` já
 * reprova `window.location.assign('/')` — mas a varredura dele só olha
 * `src/app`, e este componente mora em `components/shared`. Resultado: o botão
 * "Voltar ao início" nasceu mandando `/` fixo, o que despeja quem está em
 * `/novo/epi/eventos` no front ANTIGO, calado. É o "quinto furo" de 05/09
 * reaberto pela porta que a guarda não vigia.
 *
 * MUTAÇÃO: `inicioDaAplicacaoAtual` voltar a `return '/'` deixa este bloco
 * vermelho.
 */
describe('ErrorBoundary — a saída de emergência fica na mesma aplicação', () => {
  const comPathname = <T,>(pathname: string, f: (assign: ReturnType<typeof vi.fn>) => T): T => {
    const original = window.location
    const assign = vi.fn()
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: { ...original, pathname, assign },
    })
    try {
      return f(assign)
    } finally {
      Object.defineProperty(window, 'location', { configurable: true, value: original })
    }
  }

  it.each([
    [`${PREFIXO_NOVO}/epi/eventos`, PREFIXO_NOVO],
    [`${PREFIXO_NOVO}/estudio/dados`, PREFIXO_NOVO],
    [PREFIXO_NOVO, PREFIXO_NOVO],
    ['/epi/eventos', '/'],
    ['/', '/'],
    // não pode casar por prefixo bobo: `/novoteste` é do front antigo
    ['/novoteste', '/'],
  ])('de %s o início é %s', (pathname, esperado) => {
    comPathname(pathname, () => {
      expect(inicioDaAplicacaoAtual()).toBe(esperado)
    })
  })

  it('o botão leva para o início do front NOVO quando o erro é no front novo', () => {
    comPathname(`${PREFIXO_NOVO}/epi/eventos`, (assign) => {
      const Estoura = () => {
        throw new Error(SQL_CRU)
      }
      render(
        <ErrorBoundary>
          <Estoura />
        </ErrorBoundary>,
      )
      fireEvent.click(screen.getByRole('button', { name: /voltar ao início/i }))
      expect(assign).toHaveBeenCalledWith(PREFIXO_NOVO)
      expect(assign).not.toHaveBeenCalledWith('/')
    })
  })
})
