/**
 * Procedência na tela de DETALHE (defeito 3, parte que faltava).
 *
 * O badge já estava no histórico, no EventLogWidget, no RecentAlertsWidget e no
 * sino — e NÃO na única tela que existe para responder "o que aconteceu".
 * Ali o dano é maior: o detalhe mostra a hora de CAPTURA em destaque, então uma
 * captura de dias atrás aparecia sem nada dizendo que o evento é de coleta
 * retroativa. Com `alerts.timestamp` carregando a hora real do frame, a
 * distância captura↔gravação é dado, não estimativa.
 *
 * FALHA antes: nenhum "coleta retroativa" no DOM do detalhe.
 */
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { describe, expect, it, vi, beforeEach } from 'vitest'

const detail = {
  id: 'a1',
  camera_id: 'cam-1',
  camera_name: 'Canal 8',
  violations: [{ class: 'Sem protetor de ouvido', confidence: 0.76 }],
  acknowledged: false,
  captured_at: '2026-08-20T14:30:00',
  created_at: '2026-08-20T14:31:00',
  evidence_url: null as string | null,
}

vi.mock('../../services/api', () => ({
  getToken: () => 't',
  api: {
    get: vi.fn(() => Promise.resolve({ success: true, data: { alert: detail } })),
    post: vi.fn(() => Promise.resolve({ success: true })),
    downloadBlob: vi.fn(),
  },
}))

import { AlertDetailPage } from '../../pages/epi/AlertDetailPage'

function renderDetalhe() {
  return render(
    <MemoryRouter initialEntries={['/epi/alerts/a1']}>
      <Routes>
        <Route path="/epi/alerts/:alertId" element={<AlertDetailPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  detail.captured_at = '2026-08-20T14:30:00'
  detail.created_at = '2026-08-20T14:31:00'
})

describe('procedência no detalhe do alerta', () => {
  it('frame capturado dias antes da gravação é marcado como coleta retroativa', async () => {
    detail.created_at = '2026-08-23T09:31:00'
    renderDetalhe()
    expect(await screen.findByText(/coleta retroativa/i)).toBeTruthy()
  })

  it('captura contemporânea NÃO ganha carimbo — a tela não afirma "ao vivo"', async () => {
    renderDetalhe()
    await screen.findByText(/Canal 8/)
    expect(screen.queryByText(/coleta retroativa/i)).toBeNull()
    expect(screen.queryByText(/ao vivo/i)).toBeNull()
  })

  it('sem hora de gravação não afirma nada', async () => {
    detail.created_at = null as unknown as string
    renderDetalhe()
    await screen.findByText(/Canal 8/)
    expect(screen.queryByText(/coleta retroativa/i)).toBeNull()
  })
})
