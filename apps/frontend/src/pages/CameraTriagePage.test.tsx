/**
 * CameraTriagePage — triagem dos 29 canais do gravador da RVB.
 *
 * Cobre as regras duras do produto:
 *   1. tabela ordenada por canal, com badge de posição não confirmada e
 *      status (ativa/não ativada) corretos;
 *   2. arquivar em lote passa por ConfirmDialog e só chama update() para as
 *      câmeras selecionadas, com {is_active:false} — nunca DELETE;
 *   3. abrir preview de uma câmera draft ativa temporariamente
 *      (update({is_active:true})); fechar restaura o draft
 *      (update({is_active:false}));
 *   4. invariante "preview um por vez": abrir o preview de uma segunda
 *      câmera enquanto a primeira está aberta restaura a primeira antes de
 *      abrir a segunda;
 *   5. totalizador de consequência calcula upload/egress a partir das
 *      câmeras ativas e nunca inventa número de carga do Orin.
 *
 * cameraService é mockado por inteiro (vi.mock) — não depende de rede.
 * CameraPlayer/useLiveView são dublês simples — não depende de hls.js.
 */
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { CameraTriagePage } from './CameraTriagePage'
import { cameraService } from '../services/cameraService'
import type { Camera } from '../types'

vi.mock('../services/cameraService', () => ({
  cameraService: {
    list: vi.fn(),
    update: vi.fn(),
  },
}))

vi.mock('../hooks/useLiveView', () => ({
  useLiveView: (cameraId: string | undefined) => ({
    hlsUrl: cameraId ? `https://fake/${cameraId}/stream.m3u8` : null,
    loading: false,
    error: null,
    refresh: vi.fn(),
  }),
}))

vi.mock('../components/monitoring/CameraPlayer', () => ({
  CameraPlayer: ({ cameraId }: { cameraId: string }) => (
    <div data-testid={`player-${cameraId}`} />
  ),
}))

// ── Fixtures ──────────────────────────────────────────────────────────────
// 2 ativas (ch1, ch2) — ambas em SUBSTREAM (live_view_subtype: 1) de propósito:
// o teste do totalizador precisa de um cenário sem stream principal para
// validar a fórmula altaOp=0 (2 × 0.75 Mbps = 1.5 Mbps).
// 3 drafts (ch9-11). Ordem de entrada embaralhada de propósito — prova que a
// tabela ordena por canal, não pela ordem da resposta do backend.

function makeCamera(overrides: Partial<Camera> & Pick<Camera, 'id' | 'name' | 'channel'>): Camera {
  return {
    manufacturer: 'intelbras',
    host: '192.168.1.1',
    port: 554,
    module_code: 'epi',
    is_active: false,
    position_confirmed: false,
    codec_detected: null,
    created_at: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

const CAM_1 = makeCamera({
  id: 'cam-1', name: 'Portaria', channel: 1, is_active: true,
  live_view_subtype: 1, codec_detected: 'H264',
})
const CAM_2 = makeCamera({
  id: 'cam-2', name: 'Recepção', channel: 2, is_active: true,
  live_view_subtype: 1, codec_detected: 'H265',
})
const CAM_9 = makeCamera({ id: 'cam-9', name: 'Canal 9', channel: 9 })
const CAM_10 = makeCamera({ id: 'cam-10', name: 'Canal 10', channel: 10 })
const CAM_11 = makeCamera({ id: 'cam-11', name: 'Canal 11', channel: 11 })

const ALL_CAMERAS = [CAM_2, CAM_11, CAM_1, CAM_10, CAM_9]

function mockList(cameras: Camera[]) {
  vi.mocked(cameraService.list).mockResolvedValue(cameras)
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(cameraService.update).mockResolvedValue({} as Camera)
})

describe('CameraTriagePage', () => {
  it('renderiza linhas ordenadas por canal, com badge de posição não confirmada e status certo', async () => {
    mockList(ALL_CAMERAS)
    render(<CameraTriagePage />)

    await screen.findByTestId('camera-row-1')

    // Ordem de canal no DOM: 1, 2, 9, 10, 11 — não a ordem de chegada (2,11,1,10,9).
    const rows = screen.getAllByRole('row').slice(1) // remove header
    const channels = rows.map((r) => within(r).getAllByRole('cell')[1].textContent)
    expect(channels).toEqual(['1', '2', '9', '10', '11'])

    // Todas nascem com posição não confirmada (D-85) — inclusive as originais.
    expect(screen.getAllByText('posição não confirmada')).toHaveLength(5)

    // Status: ativas (ch1, ch2) vs não ativadas (ch9-11).
    expect(within(screen.getByTestId('camera-row-1')).getByText('Ativa')).toBeDefined()
    expect(within(screen.getByTestId('camera-row-2')).getByText('Ativa')).toBeDefined()
    expect(within(screen.getByTestId('camera-row-9')).getByText('Não ativada')).toBeDefined()
    expect(within(screen.getByTestId('camera-row-10')).getByText('Não ativada')).toBeDefined()
    expect(within(screen.getByTestId('camera-row-11')).getByText('Não ativada')).toBeDefined()

    // Cabeçalho de contagem.
    expect(screen.getByText('5 canais · 2 ativas · 3 não ativadas')).toBeDefined()
    expect(screen.getByText('3 canais livres no gravador (30–32)')).toBeDefined()
  })

  it('selecionar 2 drafts e Arquivar passa por ConfirmDialog e só atualiza as selecionadas com is_active:false', async () => {
    mockList(ALL_CAMERAS)
    render(<CameraTriagePage />)

    await screen.findByTestId('camera-row-1')

    fireEvent.click(within(screen.getByTestId('camera-row-9')).getByRole('checkbox'))
    fireEvent.click(within(screen.getByTestId('camera-row-10')).getByRole('checkbox'))

    fireEvent.click(screen.getByRole('button', { name: 'Arquivar (2)' }))

    // ConfirmDialog aparece — nenhum update ainda.
    expect(await screen.findByText(/Arquivar tira a câmera da operação/)).toBeDefined()
    expect(cameraService.update).not.toHaveBeenCalled()

    fireEvent.click(screen.getByRole('button', { name: 'Arquivar' }))

    await waitFor(() => {
      expect(cameraService.update).toHaveBeenCalledTimes(2)
    })
    expect(cameraService.update).toHaveBeenCalledWith('cam-9', { is_active: false })
    expect(cameraService.update).toHaveBeenCalledWith('cam-10', { is_active: false })
    expect(cameraService.update).not.toHaveBeenCalledWith('cam-11', expect.anything())
  })

  it('abrir preview de draft ativa temporariamente; fechar restaura o draft', async () => {
    mockList(ALL_CAMERAS)
    render(<CameraTriagePage />)

    await screen.findByTestId('camera-row-9')

    fireEvent.click(within(screen.getByTestId('camera-row-9')).getByRole('button', { name: 'Ver imagem' }))

    await waitFor(() => {
      expect(cameraService.update).toHaveBeenCalledWith('cam-9', { is_active: true })
    })
    await screen.findByTestId('player-cam-9')
    expect(screen.getByText(/Ativada temporariamente para preview/)).toBeDefined()

    fireEvent.click(screen.getByRole('button', { name: 'Fechar' }))

    await waitFor(() => {
      expect(cameraService.update).toHaveBeenCalledWith('cam-9', { is_active: false })
    })
  })

  it('invariante um-por-vez: abrir preview de outra câmera primeiro restaura a anterior', async () => {
    mockList(ALL_CAMERAS)
    render(<CameraTriagePage />)

    await screen.findByTestId('camera-row-9')

    // Abre preview do canal 9 (draft).
    fireEvent.click(within(screen.getByTestId('camera-row-9')).getByRole('button', { name: 'Ver imagem' }))
    await screen.findByTestId('player-cam-9')
    await waitFor(() => {
      expect(cameraService.update).toHaveBeenCalledWith('cam-9', { is_active: true })
    })

    // Abre preview do canal 10 (outro draft) sem fechar o do 9 manualmente.
    fireEvent.click(within(screen.getByTestId('camera-row-10')).getByRole('button', { name: 'Ver imagem' }))

    // A troca restaura o canal 9 antes de ativar o 10 — nunca dois previews juntos.
    await waitFor(() => {
      expect(cameraService.update).toHaveBeenCalledWith('cam-9', { is_active: false })
    })
    await waitFor(() => {
      expect(cameraService.update).toHaveBeenCalledWith('cam-10', { is_active: true })
    })
    await screen.findByTestId('player-cam-10')
    expect(screen.queryByTestId('player-cam-9')).toBeNull()

    // Nunca mais de um player montado ao mesmo tempo.
    expect(screen.getAllByTestId(/^player-/)).toHaveLength(1)
  })

  it('totalizador: 2 ativas em substream mostram 1.5 Mbps e a linha do Orin é sempre o aviso literal', async () => {
    mockList(ALL_CAMERAS)
    render(<CameraTriagePage />)

    await screen.findByTestId('camera-row-1')

    expect(screen.getByText('2 câmeras ativas · 0 em alta na operação')).toBeDefined()
    expect(screen.getByText(/1\.5 Mbps de 400 disponíveis/)).toBeDefined()
    expect(screen.getByText('⚠️ não medida acima de 8 streams')).toBeDefined()
  })
})
