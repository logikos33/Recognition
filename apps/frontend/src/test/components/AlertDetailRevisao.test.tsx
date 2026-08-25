/**
 * Revisão do alerta na tela de detalhe: VEREDITO e CORREÇÃO DE CAIXA.
 *
 * FALHA antes: a única ação da tela era "Reconhecer" — e no histórico ela era
 * disparada por HOVER. O operador não tinha como dizer "isto é falso positivo",
 * `alerts.verification_verdict` estava NULL nos 334 alertas do shadow, e a
 * caixa errada do modelo não tinha como ser reposicionada.
 *
 * PASSA depois: dois estados SEPARADOS na tela (reconhecimento × veredito), o
 * veredito vai por POST /verification/:id/review e NUNCA por /acknowledge, e a
 * caixa é redesenhada com arrasto gravado em PIXELS do frame ORIGINAL.
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { describe, expect, it, vi, beforeEach } from 'vitest'

const PIXELS = 'pixels_xywh_frame_original'

// jsdom não implementa PointerEvent: sem isto o fireEvent cai num Event cru e
// clientX/clientY chegam undefined — a conversão daria NaN e o teste passaria a
// medir nada. Herdar de MouseEvent é o mínimo que preserva as coordenadas.
if (!('PointerEvent' in window)) {
  class PointerEventStub extends MouseEvent {
    pointerId: number
    constructor(tipo: string, init: PointerEventInit = {}) {
      super(tipo, init)
      this.pointerId = init.pointerId ?? 1
    }
  }
  Object.defineProperty(window, 'PointerEvent', { value: PointerEventStub, configurable: true })
}

const detail = {
  id: 'a1',
  camera_id: 'cam-1',
  camera_name: 'Canal 8',
  violations: [
    { class: 'Sem protetor de ouvido', confidence: 0.76, bbox: [10, 20, 30, 40], bbox_unidade: PIXELS },
  ],
  acknowledged: true,
  captured_at: '2026-08-20T14:30:00',
  created_at: '2026-08-20T14:31:00',
  evidence_url: 'https://r2/signed' as string | null,
  verification_verdict: null as string | null,
  verified_at: null as string | null,
  correcao_ultima: null as { por: string | null; em: string | null } | null,
}

// vi.mock é içado para o topo do arquivo: as funções precisam existir antes de
// qualquer const deste módulo — daí o vi.hoisted.
const { apiGet, apiPost, apiPatch } = vi.hoisted(() => ({
  apiGet: vi.fn(), apiPost: vi.fn(), apiPatch: vi.fn(),
}))

vi.mock('../../services/api', () => ({
  getToken: () => 't',
  api: { get: apiGet, post: apiPost, patch: apiPatch, downloadBlob: vi.fn() },
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

/**
 * jsdom não baixa a imagem nem faz layout: forjamos naturalWidth/Height (frame
 * ORIGINAL) e o rect EXIBIDO. Fator 2 exato de propósito — é o que pega quem
 * confundir `getBoundingClientRect()` com `naturalWidth` na conversão.
 */
async function montarFrame(nat: [number, number], rect: [number, number]) {
  const img = (await screen.findByAltText('Frame da evidência')) as HTMLImageElement
  Object.defineProperty(img, 'naturalWidth', { value: nat[0], configurable: true })
  Object.defineProperty(img, 'naturalHeight', { value: nat[1], configurable: true })
  img.getBoundingClientRect = () => ({
    left: 0, top: 0, right: rect[0], bottom: rect[1],
    width: rect[0], height: rect[1], x: 0, y: 0, toJSON: () => ({}),
  }) as DOMRect
  fireEvent.load(img)
  return img
}

beforeEach(() => {
  apiGet.mockReset().mockImplementation(
    () => Promise.resolve({ success: true, data: { alert: detail } }))
  apiPost.mockReset().mockResolvedValue({ success: true })
  apiPatch.mockReset().mockResolvedValue({
    success: true,
    data: {
      violations: [{ class: 'Sem protetor de ouvido', confidence: 0.76, bbox: [200, 100, 400, 200], bbox_unidade: PIXELS }],
      correcao_ultima: { por: 'u-1', em: '2026-08-24T10:00:00Z' },
    },
  })
  detail.verification_verdict = null
  detail.verified_at = null
  detail.correcao_ultima = null
  detail.violations = [
    { class: 'Sem protetor de ouvido', confidence: 0.76, bbox: [10, 20, 30, 40], bbox_unidade: PIXELS },
  ]
})

describe('veredito humano no detalhe', () => {
  it('"Falso positivo" grava veredito reject e NÃO reconhece o alerta', async () => {
    renderDetalhe()
    fireEvent.click(await screen.findByText(/Errado \(falso positivo\)/i))
    await waitFor(() => expect(apiPost).toHaveBeenCalled())
    expect(apiPost).toHaveBeenCalledWith('/verification/a1/review', { verdict: 'reject' })
    // A confusão que originou o defeito: reconhecer NÃO é dar veredito.
    for (const chamada of apiPost.mock.calls as unknown as [string, unknown][]) {
      expect(chamada[0]).not.toContain('/acknowledge')
    }
  })

  it('"Confirmar" grava veredito approve', async () => {
    renderDetalhe()
    fireEvent.click(await screen.findByText(/Confirmar \(procedente\)/i))
    await waitFor(() =>
      expect(apiPost).toHaveBeenCalledWith('/verification/a1/review', { verdict: 'approve' }))
  })

  it('separa por escrito reconhecimento de veredito', async () => {
    renderDetalhe()
    expect(await screen.findByText(/só registra que alguém viu o alerta/i)).toBeTruthy()
    // Os dois estados aparecem como linhas distintas, não fundidos num rótulo.
    expect(screen.getByText('Reconhecimento:')).toBeTruthy()
    expect(screen.getByText('Veredito:')).toBeTruthy()
    expect(screen.getByText('Sem veredito')).toBeTruthy()
  })

  it('alerta já julgado mostra o veredito em português', async () => {
    detail.verification_verdict = 'reject'
    renderDetalhe()
    expect(await screen.findByText('Falso positivo')).toBeTruthy()
  })
})

describe('correção da caixa', () => {
  it('arrasto grava bbox em PIXELS do frame ORIGINAL, não do frame exibido', async () => {
    renderDetalhe()
    await montarFrame([1920, 1080], [960, 540])
    fireEvent.click(screen.getByText('Corrigir caixa'))

    const palco = screen.getByRole('group')
    fireEvent.pointerDown(palco, { clientX: 100, clientY: 50, pointerId: 1 })
    fireEvent.pointerMove(palco, { clientX: 300, clientY: 150, pointerId: 1 })
    fireEvent.pointerUp(palco, { clientX: 300, clientY: 150, pointerId: 1 })

    fireEvent.click(screen.getByText('Salvar caixa'))
    await waitFor(() => expect(apiPatch).toHaveBeenCalled())
    // 100→200, 50→100, 200→400, 100→200: fator 2 do rect exibido para o natural.
    // Gravar o rect cru daria [100,50,200,100] e a caixa cairia deslocada.
    expect(apiPatch).toHaveBeenCalledWith('/alerts/a1/violations', {
      correcoes: [{ index: 0, bbox: [200, 100, 400, 200] }],
    })
  })

  it('desenha o rascunho tracejado enquanto arrasta', async () => {
    renderDetalhe()
    await montarFrame([1920, 1080], [960, 540])
    expect(screen.queryByTestId('rascunho-box')).toBeNull()
    fireEvent.click(screen.getByText('Corrigir caixa'))
    const palco = screen.getByRole('group')
    fireEvent.pointerDown(palco, { clientX: 100, clientY: 50, pointerId: 1 })
    fireEvent.pointerMove(palco, { clientX: 300, clientY: 150, pointerId: 1 })
    expect(screen.getByTestId('rascunho-box')).toBeTruthy()
  })

  it('clique sem arrasto NÃO degenera a caixa: volta à gravada', async () => {
    renderDetalhe()
    await montarFrame([1920, 1080], [960, 540])
    fireEvent.click(screen.getByText('Corrigir caixa'))
    const palco = screen.getByRole('group')
    fireEvent.pointerDown(palco, { clientX: 100, clientY: 50, pointerId: 1 })
    fireEvent.pointerUp(palco, { clientX: 101, clientY: 50, pointerId: 1 })
    fireEvent.click(screen.getByText('Salvar caixa'))
    await waitFor(() => expect(apiPatch).toHaveBeenCalled())
    expect(apiPatch).toHaveBeenCalledWith('/alerts/a1/violations', {
      correcoes: [{ index: 0, bbox: [10, 20, 30, 40] }],
    })
  })

  it('caminho de teclado: digitar coordenadas salva o mesmo bbox', async () => {
    renderDetalhe()
    await montarFrame([1920, 1080], [960, 540])
    fireEvent.click(screen.getByText('Corrigir caixa'))
    fireEvent.change(screen.getByLabelText('x'), { target: { value: '77' } })
    fireEvent.click(screen.getByText('Salvar caixa'))
    await waitFor(() => expect(apiPatch).toHaveBeenCalled())
    expect(apiPatch).toHaveBeenCalledWith('/alerts/a1/violations', {
      correcoes: [{ index: 0, bbox: [77, 20, 30, 40] }],
    })
  })

  it('mostra quem corrigiu a caixa e quando', async () => {
    detail.correcao_ultima = { por: 'u-9', em: '2026-08-24T10:00:00Z' }
    renderDetalhe()
    expect(await screen.findByText(/Caixa corrigida por u-9/i)).toBeTruthy()
  })
})
