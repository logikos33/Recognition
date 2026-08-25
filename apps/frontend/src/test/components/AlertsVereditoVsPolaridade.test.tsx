/**
 * Polaridade ≠ veredito, e hover ≠ reconhecer.
 *
 * FALHA antes: (a) o EPI não tinha veredito nenhum — a tela só oferecia
 * "Reconhecer", e passar o MOUSE 1s na linha já reconhecia sozinho
 * (`startHoverAck` em AlertsHistoryPage.tsx); (b) `verification_verdict` é
 * escrita tanto pelo humano quanto pela IA ('claude-haiku'), então lê-la sem
 * `verified_by` apresenta decisão de máquina como julgamento de gente.
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { VARIANTE_VEREDITO } from '../../components/shared/VereditoHumano'

const linhas = [
  { id: 'a1', camera_id: 'c', camera_name: 'Canal 8', acknowledged: false,
    created_at: '2026-08-20T14:31:00', event_kind: 'compliance' as const,
    violations: [{ class: 'Protetor auditivo', confidence: 0.76 }],
    verification_verdict: null, verified_by: null },
  { id: 'a2', camera_id: 'c', camera_name: 'Canal 9', acknowledged: false,
    created_at: '2026-08-20T14:32:00', event_kind: 'violation' as const,
    violations: [{ class: 'Sem protetor de ouvido', confidence: 0.44 }],
    verification_verdict: 'reject', verified_by: 'claude-haiku' },
  { id: 'a3', camera_id: 'c', camera_name: 'Canal 10', acknowledged: false,
    created_at: '2026-08-20T14:33:00', event_kind: 'violation' as const,
    violations: [{ class: 'Sem protetor de ouvido', confidence: 0.51 }],
    verification_verdict: 'reject', verified_by: 'user:u-1' },
]

const posts: string[] = []

vi.mock('../../services/api', () => ({
  getToken: () => 't',
  api: {
    get: vi.fn((p: string) => p.startsWith('/alerts/usage-rate')
      ? Promise.resolve({ success: true, data: { areas: [] } })
      : Promise.resolve({ success: true, data: {
        alerts: linhas, total: 3, page: 1, per_page: 20, pages: 1 } })),
    post: vi.fn((p: string) => { posts.push(p); return Promise.resolve({ success: true }) }),
    downloadBlob: vi.fn(),
  },
}))

import { AlertsHistoryPage } from '../../pages/AlertsHistoryPage'

const renderAt = () => render(
  <MemoryRouter initialEntries={['/epi/alerts']}>
    <Routes><Route path="/epi/alerts" element={<AlertsHistoryPage />} /></Routes>
  </MemoryRouter>,
)

beforeEach(() => { posts.length = 0 })

describe('polaridade nunca se passa por veredito', () => {
  it('conformidade SEM revisão humana não é "Falso positivo" — é "Não revisado"', async () => {
    renderAt()
    const linha = (await screen.findByText('Canal 8')).closest('tr')!
    expect(linha.textContent).toContain('Conformidade')   // polaridade
    expect(linha.textContent).toContain('Não revisado')   // veredito
    expect(linha.textContent).not.toContain('Falso positivo — ')
    expect(linha.textContent).not.toContain('Procedente —')
  })

  it('veredito da IA NÃO é veredito humano (verified_by=claude-haiku)', async () => {
    renderAt()
    const linha = (await screen.findByText('Canal 9')).closest('tr')!
    expect(linha.textContent).toContain('Violação')       // polaridade
    // FALHA se a tela ler só o verdict: a IA gravou 'reject' nesta linha.
    expect(linha.textContent).toContain('Não revisado')
  })

  it('veredito de GENTE aparece como "Falso positivo" (verified_by=user:)', async () => {
    renderAt()
    const linha = (await screen.findByText('Canal 10')).closest('tr')!
    expect(linha.textContent).toContain('Violação')
    expect(linha.textContent).toContain('Falso positivo')
    expect(linha.textContent).not.toContain('Não revisado')
  })

  it('as duas escalas de cor são DISJUNTAS — veredito nunca usa success/danger', () => {
    const usadas = Object.values(VARIANTE_VEREDITO)
    expect(usadas).not.toContain('success')  // success é da conformidade
    expect(usadas).not.toContain('danger')   // danger é da violação
  })

  it('as duas escalas de PALAVRA são disjuntas', () => {
    const polaridade = ['Violação', 'Conformidade']
    const vereditos = ['Procedente', 'Falso positivo', 'Não revisado']
    expect(polaridade.some(p => vereditos.includes(p))).toBe(false)
  })
})

describe('reconhecer é ato explícito', () => {
  beforeEach(() => vi.useFakeTimers({ shouldAdvanceTime: true }))
  afterEach(() => vi.useRealTimers())

  it('passar o MOUSE na linha não reconhece nada', async () => {
    renderAt()
    const linha = (await screen.findByText('Canal 8')).closest('tr')!
    fireEvent.mouseEnter(linha)
    await vi.advanceTimersByTimeAsync(5000)
    expect(posts.filter(p => p.includes('/acknowledge'))).toHaveLength(0)
  })

  it('CLICAR na linha (abrir o detalhe) também não reconhece', async () => {
    renderAt()
    const linha = (await screen.findByText('Canal 8')).closest('tr')!
    fireEvent.click(linha)
    await vi.advanceTimersByTimeAsync(5000)
    expect(posts.filter(p => p.includes('/acknowledge'))).toHaveLength(0)
  })

  it('só o botão reconhece', async () => {
    renderAt()
    await screen.findByText('Canal 8')
    fireEvent.click(screen.getAllByText('Reconhecer')[0])
    await waitFor(() => expect(posts.some(p => p.includes('/acknowledge'))).toBe(true))
  })

  it('"Falso positivo" grava VEREDITO, não reconhecimento', async () => {
    renderAt()
    await screen.findByText('Canal 8')
    fireEvent.click(screen.getAllByText('Falso positivo')[0])
    await waitFor(() => expect(posts.some(p => p.includes('/verification/'))).toBe(true))
    expect(posts.filter(p => p.includes('/acknowledge'))).toHaveLength(0)
  })
})
