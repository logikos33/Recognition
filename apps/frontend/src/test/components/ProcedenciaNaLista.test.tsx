/**
 * As três superfícies do front ANTIGO que também apresentavam anotação humana
 * como detecção do modelo — e o 409 do veredito no histórico.
 *
 * ── Procedência (issue #670) ────────────────────────────────────────────────
 * MEDIDO em 05/09: 4.609 dos 5.174 eventos do DEV têm `violations[].origem =
 * 'anotacao_humana'` (semeados por `scripts/ops/eventos_acervo_rvb.py`), e o
 * script grava `created_at == timestamp`. O critério TEMPORAL de procedência
 * (`ProcedenciaBadge`, atraso ≥ 5 min) nunca acende nesses eventos, então
 * `AlertsHistoryPage`, `RecentAlertsWidget` e `EventLogWidget` ficavam MUDOS
 * justamente onde tinham mais o que dizer. Declaração vence indício.
 *
 * ── 409 (issue #675) ────────────────────────────────────────────────────────
 * Quando outra pessoa julga primeiro, o backend recusa o segundo veredito e
 * responde 409 com QUEM julgou e QUANDO. O histórico caía num `catch` cego e
 * dizia "Não foi possível registrar o veredito" — vermelho, sobre um veredito
 * que FOI registrado. O operador clica de novo no que já está resolvido.
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const h = vi.hoisted(() => ({
  /** Erro do POST /verification/<id>/review — `null` = sucesso. */
  erroDoVeredito: null as Error | null,
  gets: [] as string[],
}))

vi.mock('../../services/api', async () => {
  // `ApiError` REAL: as telas separam 409 de qualquer outro status por
  // `instanceof` + `.status`, e um dublê apagaria a distinção sob teste.
  const real = await vi.importActual<Record<string, unknown>>('../../services/api')
  return {
    ...real,
    getToken: () => 't',
    api: {
      get: vi.fn((p: string) => {
        h.gets.push(p)
        if (p.startsWith('/alerts/usage-rate')) {
          return Promise.resolve({ success: true, data: { areas: [] } })
        }
        return Promise.resolve({
          success: true,
          data: { alerts: LINHAS, total: LINHAS.length, page: 1, per_page: 20, pages: 1 },
        })
      }),
      post: vi.fn(() =>
        h.erroDoVeredito ? Promise.reject(h.erroDoVeredito) : Promise.resolve({ success: true })),
      downloadBlob: vi.fn(),
    },
  }
})

import { ApiError } from '../../services/api'
import { useToastStore } from '../../components/ui/Toast/useToast'
import { AlertsHistoryPage } from '../../pages/AlertsHistoryPage'
import { RecentAlertsWidget } from '../../components/dashboard/widgets/RecentAlertsWidget'
import { EventLogWidget } from '../../components/dashboard/widgets/EventLogWidget'

/**
 * Como o acervo do DEV está no banco de verdade: caixa desenhada por PESSOA,
 * marca de lote, e `created_at == timestamp` (o par que faz o critério
 * temporal calar). A terceira linha é o contraste — sem origem declarada e
 * com 12 min de atraso, é onde o critério temporal AINDA tem de falar.
 */
const LINHAS = [
  {
    id: 'a1', camera_id: 'c1', camera_name: 'Canal 8', acknowledged: false,
    created_at: '2026-08-20T14:32:00', timestamp: '2026-08-20T14:32:00',
    event_kind: 'violation' as const,
    violations: [{
      class: 'no_helmet', confidence: 0.87,
      origem: 'anotacao_humana', lote: 'acervo_rvb_2026_08',
    }],
    verification_verdict: null, verified_by: null,
  },
  {
    id: 'a2', camera_id: 'c2', camera_name: 'Canal 9', acknowledged: false,
    created_at: '2026-08-20T14:33:00', timestamp: '2026-08-20T14:33:00',
    event_kind: 'violation' as const,
    violations: [{ class: 'no_helmet', confidence: 0.61, origem: 'modelo_onnx' }],
    verification_verdict: null, verified_by: null,
  },
  {
    id: 'a3', camera_id: 'c3', camera_name: 'Canal 10', acknowledged: false,
    created_at: '2026-08-20T14:32:00', timestamp: '2026-08-20T14:20:00',
    event_kind: 'violation' as const,
    violations: [{ class: 'no_helmet', confidence: 0.44 }],
    verification_verdict: null, verified_by: null,
  },
]

const historico = () => render(
  <MemoryRouter initialEntries={['/epi/alerts']}>
    <Routes><Route path="/epi/alerts" element={<AlertsHistoryPage />} /></Routes>
  </MemoryRouter>,
)

/** Widget isolado: react-query próprio por teste, sem cache entre casos. */
const widget = (no: React.ReactNode) => render(
  <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter>{no}</MemoryRouter>
  </QueryClientProvider>,
)

const linhaDe = (texto: string) => screen.getByText(texto).closest('tr') as HTMLElement
/** `alertRow` do RecentAlertsWidget: nome da câmera → corpo → linha inteira
 *  (o badge de procedência mora na coluna irmã, `alertRowTime`). */
const cartaoDe = (texto: string) =>
  screen.getByText(texto).parentElement!.parentElement as HTMLElement

beforeEach(() => {
  h.erroDoVeredito = null
  h.gets.length = 0
  useToastStore.setState({ toasts: [] })
})

describe('origem declarada chega às listas do front antigo', () => {
  it('histórico: caixa desenhada por PESSOA é anunciada como tal', async () => {
    historico()
    await screen.findByText('Canal 8')
    const linha = linhaDe('Canal 8').textContent ?? ''
    expect(linha).toContain('anotação humana')
    expect(linha).toContain('demonstração')
  })

  it('histórico: caixa do MODELO é dita como do modelo, sem ressalva', async () => {
    historico()
    await screen.findByText('Canal 9')
    const linha = linhaDe('Canal 9').textContent ?? ''
    expect(linha).toContain('detecção do modelo')
    expect(linha).not.toContain('anotação humana')
  })

  it('histórico: sem origem declarada, o critério temporal continua valendo', async () => {
    historico()
    await screen.findByText('Canal 10')
    expect(linhaDe('Canal 10').textContent).toContain('coleta retroativa')
  })

  it('RecentAlertsWidget lê a origem declarada', async () => {
    widget(<RecentAlertsWidget />)
    await screen.findByText('Canal 8')
    expect(cartaoDe('Canal 8').textContent).toContain('anotação humana')
  })

  it('EventLogWidget lê a origem declarada', async () => {
    widget(<EventLogWidget />)
    await screen.findByText('Canal 8')
    expect(linhaDe('Canal 8').textContent).toContain('anotação humana')
  })
})

describe('409 no veredito do histórico', () => {
  const FRASE = 'Maria Silva já avaliou este alerta há 2 minutos'

  const julgar = async (erro: Error) => {
    h.erroDoVeredito = erro
    historico()
    await screen.findByText('Canal 8')
    fireEvent.click(screen.getAllByRole('button', { name: /procedente/i })[0])
  }

  it('informa QUEM julgou e QUANDO, em vez do vermelho genérico', async () => {
    await julgar(new ApiError(FRASE, 409))
    await waitFor(() => {
      const toasts = useToastStore.getState().toasts
      expect(toasts.some((t) => t.variant === 'info' && t.description === FRASE)).toBe(true)
      expect(toasts.some((t) => t.variant === 'error')).toBe(false)
    })
  })

  it('recarrega a lista para a coluna de veredito mostrar a decisão que existe', async () => {
    const antes = h.gets.filter((p) => p.startsWith('/alerts?')).length
    await julgar(new ApiError(FRASE, 409))
    await waitFor(() =>
      expect(h.gets.filter((p) => p.startsWith('/alerts?')).length).toBeGreaterThan(antes + 1))
  })

  it('erro de verdade (500) continua vermelho', async () => {
    await julgar(new ApiError('boom', 500))
    await waitFor(() =>
      expect(useToastStore.getState().toasts.some((t) => t.variant === 'error')).toBe(true))
  })
})
