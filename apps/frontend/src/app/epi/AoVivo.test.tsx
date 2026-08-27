/**
 * EPI Ao Vivo — o que esta tela não pode perder.
 *
 * Três coisas custaram caro e são protegidas aqui:
 *
 *  1. **A URL do HLS vem do backend, tokenizada.** Desde os PRs 255/256,
 *     `m3u8` sem token dá 404 igual a stream inexistente. Se alguém "otimizar"
 *     montando `${API}/api/cameras/${id}/stream/stream.m3u8` no front, a tela
 *     fica preta e o backend não acusa nada. O teste exige que a URL entregue
 *     ao player seja EXATAMENTE a que `POST /stream/start` devolveu, e que ela
 *     tenha o token no path.
 *
 *  2. **Sessão única de playback por câmera.** Ladrilho e gaveta cada um monta
 *     seu `useLiveView` + player; com os dois vivos, dois tokens baixam o mesmo
 *     `.ts` (visto em produção).
 *
 *  3. **Bounding box não é alvo de clique** (CLAUDE.md). Caixa clicável rouba o
 *     clique do ladrilho e se move sozinha.
 *
 * Mais o contrato de tela: dado real ou vazio honesto — nunca mocado.
 */
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { AoVivo } from './AoVivo'
import { api } from '../../services/api'
import { cameraService } from '../../services/cameraService'
import { __resetLiveViewCache } from '../../hooks/useLiveView'
import type { Camera } from '../../types'
import type { Detection } from '../../hooks/useMonitoringSocket'

// ── Dublês ──────────────────────────────────────────────────────────────────

vi.mock('../../services/api', () => ({
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn() },
  getToken: vi.fn(() => 'jwt-de-teste'),
  setToken: vi.fn(),
  removeToken: vi.fn(),
}))

vi.mock('../../services/cameraService', () => ({
  cameraService: { start: vi.fn() },
}))

let permissoes = ['cameras:read']
vi.mock('../../hooks/useAuth', () => ({
  useAuth: () => ({ can: (p: string) => permissoes.includes(p) }),
}))

// socket.io real abriria conexão de verdade; o que interessa aqui é o payload.
let deteccoesWs: Record<string, Detection[]> = {}
vi.mock('../../hooks/useMonitoringSocket', () => ({
  useMonitoringSocket: () => ({
    connected: false,
    detections: deteccoesWs,
    alerts: [],
    subscribeCamera: vi.fn(),
    unsubscribeCamera: vi.fn(),
    clearAlerts: vi.fn(),
  }),
}))

// hls.js não faz parte do que se verifica aqui — mas a URL que chega ao player
// faz, e é por isso que o dublê a expõe no DOM.
vi.mock('../../components/monitoring/CameraPlayer', () => ({
  CameraPlayer: ({ cameraId, hlsUrl }: { cameraId: string; hlsUrl: string }) => (
    <div data-testid="player" data-camera={cameraId} data-url={hlsUrl} />
  ),
}))

// ── Dados ───────────────────────────────────────────────────────────────────

const camera = (id: string, name: string, is_active = true): Camera => ({
  id,
  name,
  manufacturer: 'intelbras',
  host: '10.0.0.9',
  port: 554,
  channel: 1,
  is_active,
  created_at: '2026-08-01T00:00:00Z',
  location: 'DOCA NORTE',
  fps_target: 12,
})

const CAMS = [camera('cam-1', 'CAM-01 DOCA NORTE'), camera('cam-2', 'CAM-02 PORTARIA')]

const tokenizada = (id: string) => `/api/cameras/${id}/stream/s/1799999999.assinatura/stream.m3u8`

function respondeCameras(lista: Camera[] = CAMS) {
  vi.mocked(api.get).mockImplementation((path: string) => {
    if (path.startsWith('/cameras')) return Promise.resolve({ data: { cameras: lista } } as never)
    if (path.startsWith('/alerts')) return Promise.resolve({ data: { alerts: [] } } as never)
    return Promise.reject(new Error(`rota não esperada: ${path}`))
  })
}

const montar = () => render(<MemoryRouter><AoVivo /></MemoryRouter>)

const playersDe = (id: string) =>
  screen.queryAllByTestId('player').filter((e) => e.getAttribute('data-camera') === id)

beforeEach(() => {
  vi.clearAllMocks()
  __resetLiveViewCache()
  permissoes = ['cameras:read']
  deteccoesWs = {}
  vi.mocked(cameraService.start).mockImplementation((id: string) =>
    Promise.resolve({ camera_id: id, hls_url: tokenizada(id), status: 'started' } as never),
  )
  respondeCameras()
})

// ── 1. A URL tokenizada ─────────────────────────────────────────────────────

describe('fluxo tokenizado de playback', () => {
  it('entrega ao player a URL que o backend assinou — nunca uma montada aqui', async () => {
    montar()
    await waitFor(() => expect(playersDe('cam-1')).toHaveLength(1))

    const player = playersDe('cam-1')[0]!
    // `useLiveView` só prefixa a origem da API — o caminho assinado é o do backend.
    expect(player.getAttribute('data-url')?.endsWith(tokenizada('cam-1'))).toBe(true)
    // O token no PATH é o que faz os .ts relativos herdarem a autorização.
    expect(player.getAttribute('data-url')).toContain('/stream/s/')
    expect(cameraService.start).toHaveBeenCalledWith('cam-1')
  })

  it('câmera arquivada não minta token nenhum', async () => {
    respondeCameras([camera('cam-3', 'CAM-03 ARQUIVADA', false)])
    montar()
    await screen.findByText('CAM-03 ARQUIVADA')
    expect(cameraService.start).not.toHaveBeenCalled()
    expect(screen.getByTitle('✕ OFFLINE')).toBeTruthy()
  })
})

// ── 2. Sessão única por câmera ──────────────────────────────────────────────

describe('sessão única de playback', () => {
  it('abrir a gaveta não deixa dois players vivos para a mesma câmera', async () => {
    montar()
    await waitFor(() => expect(playersDe('cam-1')).toHaveLength(1))

    fireEvent.click(screen.getByLabelText('Abrir CAM-01 DOCA NORTE'))
    await screen.findByLabelText('Detalhes de CAM-01 DOCA NORTE')

    await waitFor(() => expect(playersDe('cam-1')).toHaveLength(1))
    // A outra câmera segue tocando na grade — a gaveta não para a operação.
    expect(playersDe('cam-2')).toHaveLength(1)

    fireEvent.click(screen.getByLabelText('Fechar painel'))
    await waitFor(() => expect(playersDe('cam-1')).toHaveLength(1))
  })
})

// ── 3. Bounding box não é alvo de clique ────────────────────────────────────

describe('overlay de detecção', () => {
  const DET: Detection[] = [
    { class: 'sem_capacete', confidence: 0.91, bbox: [64, 36, 128, 180], is_violation: true },
  ]

  it('a camada de caixas tem pointerEvents none e zero onClick', async () => {
    deteccoesWs = { 'cam-1': DET }
    montar()
    await screen.findByText('CAM-01 DOCA NORTE')

    const camada = screen.getAllByTestId('camada-caixas')[0]!
    expect(camada.style.pointerEvents).toBe('none')
    for (const cx of screen.getAllByTestId('caixa-deteccao')) {
      expect(cx.onclick).toBeNull()
    }
  })

  it('converte a bbox para % do ladrilho — o ladrilho é responsivo', async () => {
    deteccoesWs = { 'cam-1': DET }
    montar()
    await screen.findByText('CAM-01 DOCA NORTE')

    const cx = screen.getAllByTestId('caixa-deteccao')[0]!
    expect(cx.style.left).toBe('10%') // 64 / 640
    expect(cx.style.top).toBe('10%') //  36 / 360
    expect(cx.style.width).toBe('20%') // 128 / 640
  })

  it('desligar o toggle apaga as caixas', async () => {
    deteccoesWs = { 'cam-1': DET }
    montar()
    await screen.findByText('CAM-01 DOCA NORTE')
    expect(screen.queryAllByTestId('caixa-deteccao').length).toBeGreaterThan(0)

    fireEvent.click(screen.getByRole('button', { name: /Overlay de detecção/ }))
    expect(screen.queryAllByTestId('caixa-deteccao')).toHaveLength(0)
  })
})

// ── Layout: presets, colunas, destaque ──────────────────────────────────────

describe('layout da grade', () => {
  it('preset define as colunas', async () => {
    montar()
    await screen.findByText('CAM-01 DOCA NORTE')

    expect(screen.getByTestId('grade').style.gridTemplateColumns).toBe('repeat(2, 1fr)')
    fireEvent.click(screen.getByRole('button', { name: '3×3' }))
    expect(screen.getByTestId('grade').style.gridTemplateColumns).toBe('repeat(3, 1fr)')
  })

  it('o passo de colunas anda entre 2 e 6', async () => {
    montar()
    await screen.findByText('CAM-01 DOCA NORTE')

    fireEvent.click(screen.getByLabelText('Mais colunas'))
    expect(screen.getByTestId('colunas-valor').textContent).toBe('5')
    fireEvent.click(screen.getByLabelText('Mais colunas'))
    expect(screen.getByTestId('colunas-valor').textContent).toBe('6')
    expect(screen.getByLabelText('Mais colunas')).toHaveProperty('disabled', true)
  })

  it('em >=5 colunas o estado vira só o ícone e o rótulo da bbox some', async () => {
    deteccoesWs = { 'cam-1': [{ class: 'capacete', confidence: 0.9, bbox: [0, 0, 10, 10] }] }
    montar()
    await screen.findByText('CAM-01 DOCA NORTE')
    expect(screen.getAllByText(/ONLINE/).length).toBeGreaterThan(0)

    fireEvent.click(screen.getByLabelText('Mais colunas')) // 5 colunas
    expect(screen.queryByText('● ONLINE')).toBeNull()
    expect(screen.getAllByTitle('● ONLINE').length).toBeGreaterThan(0)
    expect(screen.queryByText(/capacete 90%/)).toBeNull()
  })

  it('DESTAQUE mostra uma grande e as vizinhas no trilho', async () => {
    montar()
    await screen.findByText('CAM-01 DOCA NORTE')

    fireEvent.click(screen.getByRole('button', { name: 'Destacar CAM-02 PORTARIA' }))
    expect(screen.queryByTestId('grade')).toBeNull()
    // As duas seguem na tela: uma em foco, a outra no trilho.
    expect(screen.getByText('CAM-02 PORTARIA')).toBeTruthy()
    expect(screen.getByText('CAM-01 DOCA NORTE')).toBeTruthy()
  })
})

// ── Estados honestos ────────────────────────────────────────────────────────

describe('estados da tela', () => {
  it('sem câmera: vazio honesto com o caminho de cadastro', async () => {
    respondeCameras([])
    montar()
    await screen.findByText('Nenhuma câmera neste site')
    expect(screen.getByText('Adicionar câmera').getAttribute('href')).toBe('/epi/cameras')
    expect(screen.queryByTestId('player')).toBeNull()
  })

  it('erro: mostra a falha real e o retry refaz a chamada', async () => {
    vi.mocked(api.get).mockRejectedValueOnce(new Error('Conexão recusada'))
    montar()
    await screen.findByText('Falha ao conectar ao gateway de vídeo')
    expect(screen.getByText(/CONEXÃO RECUSADA/)).toBeTruthy()

    respondeCameras()
    fireEvent.click(screen.getByRole('button', { name: 'Tentar novamente' }))
    await screen.findByText('CAM-01 DOCA NORTE')
  })

  it('sem cameras:read não busca câmera nenhuma', async () => {
    permissoes = []
    montar()
    await screen.findByText('Sem permissão para ver câmeras')
    expect(api.get).not.toHaveBeenCalled()
  })

  it('o cabeçalho conta o que o backend afirma, não o que o player parece', async () => {
    respondeCameras([...CAMS, camera('cam-9', 'CAM-09 ARQUIVADA', false)])
    montar()
    await screen.findByText('3 CÂMERAS · 2 ATIVAS')
  })
})

// ── Gaveta ──────────────────────────────────────────────────────────────────

describe('gaveta da câmera', () => {
  it('mostra só dado que a API devolve e lista eventos reais da câmera', async () => {
    vi.mocked(api.get).mockImplementation((path: string) => {
      if (path.startsWith('/cameras')) return Promise.resolve({ data: { cameras: CAMS } } as never)
      if (path === '/alerts?camera_id=cam-1&per_page=5') {
        return Promise.resolve({
          data: {
            alerts: [
              { id: 'a1', class_name: 'Sem capacete', captured_at: '2026-08-27T17:32:00Z' },
            ],
          },
        } as never)
      }
      return Promise.reject(new Error(`rota não esperada: ${path}`))
    })

    montar()
    await screen.findByText('CAM-01 DOCA NORTE')
    fireEvent.click(screen.getByLabelText('Abrir CAM-01 DOCA NORTE'))

    const gaveta = await screen.findByLabelText('Detalhes de CAM-01 DOCA NORTE')
    expect(within(gaveta).getByText('12 FPS')).toBeTruthy()
    expect(within(gaveta).getByText('DOCA NORTE')).toBeTruthy()

    const evento = await within(gaveta).findByText('Sem capacete')
    expect(evento.closest('a')?.getAttribute('href')).toBe('/epi/eventos/a1')
  })

  it('câmera sem evento: vazio honesto, não lista inventada', async () => {
    montar()
    await screen.findByText('CAM-01 DOCA NORTE')
    fireEvent.click(screen.getByLabelText('Abrir CAM-01 DOCA NORTE'))

    const gaveta = await screen.findByLabelText('Detalhes de CAM-01 DOCA NORTE')
    await within(gaveta).findByText('Nenhum evento nesta câmera')
  })
})
