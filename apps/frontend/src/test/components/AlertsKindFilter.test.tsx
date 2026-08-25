/**
 * Semântica do evento (ADR-0063): presença = conformidade, ausência = violação.
 *
 * FALHA antes do fix: a tela pedia `/alerts?...` sem recorte e rotulava a coluna
 * "Violação" — um trabalhador USANDO protetor auricular aparecia como violação,
 * e o sino tocava por causa dele.
 * PASSA depois: a tela abre em `kind=violation`, o operador pode trocar para
 * conformidade (que traz o painel de taxa de uso), e o que é conformidade sai
 * marcado.
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { describe, expect, it, vi, beforeEach } from 'vitest'

const violacao = {
  id: 'v1', camera_id: 'cam-1', camera_name: 'Canal 8',
  violations: [{ class: 'Sem protetor de ouvido', confidence: 0.44 }],
  acknowledged: true, created_at: '2026-08-20T14:31:00',
  event_kind: 'violation' as const,
}
const conformidade = {
  id: 'c1', camera_id: 'cam-1', camera_name: 'Canal 9',
  violations: [{ class: 'Protetor auditivo', confidence: 0.76 }],
  acknowledged: true, created_at: '2026-08-20T14:32:00',
  event_kind: 'compliance' as const,
}

const pedidos: string[] = []

vi.mock('../../services/api', () => ({
  getToken: () => 't',
  api: {
    get: vi.fn((path: string) => {
      pedidos.push(path)
      if (path.startsWith('/alerts/usage-rate')) {
        return Promise.resolve({
          success: true,
          data: { areas: [{ area: 'Expedição', compliance: 3, violation: 1 }] },
        })
      }
      const alerts = path.includes('kind=compliance') ? [conformidade] : [violacao]
      return Promise.resolve({
        success: true,
        data: { alerts, total: 1, page: 1, per_page: 20, pages: 1 },
      })
    }),
    post: vi.fn(() => Promise.resolve({ success: true })),
    downloadBlob: vi.fn(),
  },
}))

import { AlertsHistoryPage } from '../../pages/AlertsHistoryPage'

function renderAt(path = '/epi/alerts') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes><Route path="/epi/alerts" element={<AlertsHistoryPage />} /></Routes>
    </MemoryRouter>,
  )
}

const pedidosDeAlerta = () => pedidos.filter(p => p.startsWith('/alerts?'))

describe('semântica do evento no histórico', () => {
  beforeEach(() => { pedidos.length = 0 })

  it('abre em VIOLAÇÕES — EPI em uso não é o padrão da tela', async () => {
    renderAt()
    await screen.findByText('Canal 8')
    expect(pedidosDeAlerta()[0]).toContain('kind=violation')
    expect(screen.getByText('Violações de EPI')).toBeTruthy()
  })

  it('deep-link do sino manda o mesmo recorte que o sino mostrou', async () => {
    renderAt('/epi/alerts?acknowledged=false&kind=violation')
    await screen.findByText('Canal 8')
    expect(pedidosDeAlerta()[0]).toContain('kind=violation')
  })

  it('conformidade é aba própria, com taxa de uso por área', async () => {
    renderAt()
    await screen.findByText('Canal 8')
    fireEvent.change(screen.getByLabelText('Tipo de evento'), {
      target: { value: 'compliance' },
    })
    await screen.findByText('Conformidade — EPI em uso')
    await waitFor(() => expect(screen.getByText('Expedição')).toBeTruthy())
    // 3 conformidades de 4 eventos = 75% de uso.
    expect(screen.getByText('75%')).toBeTruthy()
    expect(pedidos.some(p => p.startsWith('/alerts/usage-rate'))).toBe(true)
  })

  it('a linha de conformidade não se passa por violação', async () => {
    renderAt('/epi/alerts?kind=compliance')
    await screen.findByText('Canal 9')
    // Cabeçalho neutro: a coluna também mostra conformidade.
    expect(screen.getByText('Evento')).toBeTruthy()
    expect(screen.queryByText('Violação')).toBeNull()
    expect(screen.getByTitle('EPI em uso — conformidade, não violação')).toBeTruthy()
  })

  it('"Todos os eventos" não filtra nada', async () => {
    renderAt()
    await screen.findByText('Canal 8')
    fireEvent.change(screen.getByLabelText('Tipo de evento'), { target: { value: '' } })
    await waitFor(() =>
      expect(pedidosDeAlerta().at(-1)).not.toContain('kind='),
    )
  })
})
