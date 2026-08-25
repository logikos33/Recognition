/**
 * Deep-link do evento (defeito 2): o evento LEVA AO ACONTECIDO.
 *
 * FALHA antes do fix: a AlertsHistoryPage abria um modal sem URL cuja caixa era
 * `left:20% top:15% width:25% height:50%` HARDCODED — idêntica para toda
 * violação, ignorando `violations[].bbox` — e mostrava `created_at` (hora de
 * gravação) no lugar de `timestamp` (hora real da captura).
 * PASSA depois: a linha navega para /epi/alerts/:alertId, e a página projeta o
 * bbox em PIXELS do frame original no lugar exato.
 *
 * Contrato de bbox = `services/api/app/domain/detectors/base.py`:
 * [x, y, w, h] em PIXELS do frame ORIGINAL, canto superior-esquerdo. Cada
 * violação carrega `bbox_unidade: "pixels_xywh_frame_original"`. Os testes
 * abaixo provam a DIFERENÇA em relação à convenção normalizada [cx,cy,w,h]:
 * quem voltar a ela quebra aqui.
 */
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { describe, expect, it, vi, beforeEach } from 'vitest'

const PIXELS = 'pixels_xywh_frame_original'

const pixelViolation = {
  class: 'Sem protetor de ouvido',
  confidence: 0.76,
  bbox: [100, 50, 40, 30],
  bbox_unidade: PIXELS,
}

const detail: {
  id: string
  camera_id: string
  camera_name: string
  violations: unknown[]
  acknowledged: boolean
  captured_at: string
  created_at: string
  evidence_url: string
} = {
  id: 'a1',
  camera_id: 'cam-1',
  camera_name: 'Canal 8',
  violations: [pixelViolation],
  acknowledged: false,
  captured_at: '2026-08-20T14:30:00',
  created_at: '2026-08-20T14:31:00',
  evidence_url: 'https://r2/signed',
}

const listRow = {
  id: 'a1',
  camera_id: 'cam-1',
  camera_name: 'Canal 8',
  violations: [{ class: 'Sem protetor de ouvido', confidence: 0.76 }],
  acknowledged: true,
  created_at: '2026-08-20T14:31:00',
}

vi.mock('../../services/api', () => ({
  getToken: () => 't',
  api: {
    get: vi.fn((path: string) =>
      path.startsWith('/alerts/a1')
        ? Promise.resolve({ success: true, data: { alert: detail } })
        : Promise.resolve({
            success: true,
            data: { alerts: [listRow], total: 1, page: 1, per_page: 20, pages: 1 },
          }),
    ),
    post: vi.fn(() => Promise.resolve({ success: true })),
    downloadBlob: vi.fn(),
  },
}))

import { AlertsHistoryPage } from '../../pages/AlertsHistoryPage'
import { AlertDetailPage, boxStyle } from '../../pages/epi/AlertDetailPage'

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/epi/alerts" element={<AlertsHistoryPage />} />
        <Route path="/epi/alerts/:alertId" element={<AlertDetailPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

/** jsdom não baixa a imagem: naturalWidth/Height são 0 até forjarmos e disparar o load. */
async function loadFrame(w: number, h: number) {
  const img = (await screen.findByAltText('Frame da evidência')) as HTMLImageElement
  Object.defineProperty(img, 'naturalWidth', { value: w, configurable: true })
  Object.defineProperty(img, 'naturalHeight', { value: h, configurable: true })
  fireEvent.load(img)
  return img
}

beforeEach(() => {
  detail.violations = [pixelViolation]
})

describe('deep-link do evento', () => {
  it('projeta bbox em PIXELS do frame original ([x,y,w,h], canto superior-esquerdo)', () => {
    // 100/800 = 12,5% · 50/600 = 8,3333% · 40/800 = 5% · 30/600 = 5%
    expect(boxStyle([100, 50, 40, 30], 800, 600)).toEqual({
      left: '12.5%', top: '8.3333%', width: '5%', height: '5%',
    })
    // Mesmo bbox num frame 4K projeta MENOR: a projeção depende do frame real.
    expect(boxStyle([100, 50, 40, 30], 3840, 2160)).toEqual({
      left: '2.6042%', top: '2.3148%', width: '1.0417%', height: '1.3889%',
    })
  })

  it('NÃO usa a convenção de centro: [x,y] é canto, não centro', () => {
    // Com [cx,cy,w,h] o left seria (100−40/2)/800 = 10% e o top (50−30/2)/600 = 5,8333%.
    const box = boxStyle([100, 50, 40, 30], 800, 600)
    expect(box.left).not.toBe('10%')
    expect(box.top).not.toBe('5.8333%')
  })

  it('NÃO trata bbox como normalizado 0..1', () => {
    const asIfNormalized = boxStyle([0.5, 0.5, 0.2, 0.4], 800, 600)
    // A convenção antiga produzia exatamente isto — se voltar, este teste quebra.
    expect(asIfNormalized).not.toEqual({
      left: '40%', top: '30%', width: '20%', height: '40%',
    })
    // Números 0..1 lidos como pixels dão caixa degenerada (sub-pixel), não plausível:
    // é a prova de que a unidade importa e não é intercambiável.
    expect(parseFloat(asIfNormalized.width)).toBeLessThan(0.1)
    expect(parseFloat(asIfNormalized.height)).toBeLessThan(0.1)
  })

  it('clique na linha do histórico leva ao detalhe', async () => {
    renderAt('/epi/alerts')
    fireEvent.click(await screen.findByText('Canal 8'))
    expect(await screen.findByText('Detalhe do Alerta')).toBeTruthy()
  })

  it('detalhe mostra frame, caixa no lugar exato, câmera, captura, classe e confiança', async () => {
    renderAt('/epi/alerts/a1')
    const img = await loadFrame(800, 600)
    expect(img.getAttribute('src')).toBe('https://r2/signed')

    const box = (await screen.findByTestId('violation-box')) as HTMLElement
    expect(box.style.left).toBe('12.5%')
    expect(box.style.top).toBe('8.3333%')
    expect(box.style.width).toBe('5%')
    expect(box.style.height).toBe('5%')

    expect(screen.getByText(/Canal 8/)).toBeTruthy()
    // hora de CAPTURA (14:30), não a de gravação (14:31)
    expect(screen.getByText(/14:30/)).toBeTruthy()
    expect(screen.queryByText(/14:31/)).toBeNull()
    expect(screen.getAllByText(/Sem protetor de ouvido — 76%/).length).toBeGreaterThan(0)
  })

  it('não desenha nada antes da imagem carregar (sem dimensão do frame, sem projeção)', async () => {
    renderAt('/epi/alerts/a1')
    await screen.findByAltText('Frame da evidência')
    expect(screen.queryByTestId('violation-box')).toBeNull()
  })

  it('bbox sem bbox_unidade conhecida NÃO vira caixa — avisa origem desconhecida', async () => {
    detail.violations = [
      { class: 'Sem protetor de ouvido', confidence: 0.76, bbox: [0.5, 0.5, 0.2, 0.4] },
    ]
    renderAt('/epi/alerts/a1')
    await loadFrame(800, 600)
    expect(screen.queryByTestId('violation-box')).toBeNull()
    expect(screen.getByText(/origem desconhecida/i)).toBeTruthy()
  })

  it('bbox_unidade estranha também não desenha', async () => {
    detail.violations = [
      { class: 'Sem protetor de ouvido', confidence: 0.76, bbox: [0.5, 0.5, 0.2, 0.4], bbox_unidade: 'cxcywh_normalizado' },
    ]
    renderAt('/epi/alerts/a1')
    await loadFrame(800, 600)
    expect(screen.queryByTestId('violation-box')).toBeNull()
    expect(screen.getByText(/origem desconhecida/i)).toBeTruthy()
  })

  it('evento sem bbox mostra o frame e avisa em vez de desenhar caixa falsa', async () => {
    detail.violations = [{ class: 'Sem protetor de ouvido', confidence: 0.76 }]
    renderAt('/epi/alerts/a1')
    await loadFrame(800, 600)
    expect(screen.queryByTestId('violation-box')).toBeNull()
    expect(screen.getByText(/sem coordenadas gravadas/i)).toBeTruthy()
  })
})
