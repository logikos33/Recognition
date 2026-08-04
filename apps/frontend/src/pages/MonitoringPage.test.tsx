/**
 * MonitoringPage — sessão única de playback por câmera (item 6 da rodada).
 *
 * Bug: card da grade (`VmsCameraCard`) e drawer (`CameraDrawerContent`) cada um
 * monta seu próprio `useLiveView(camera.id)` + `<CameraPlayer>`. Abrir o drawer
 * NÃO desmontava o card atrás — os dois ficavam vivos para a MESMA câmera, cada
 * um mintando um token de playback próprio via `POST /stream/start`
 * (`cameraService.start`) sem se coordenar. Produção viu dois tokens vivos
 * baixando o MESMO segmento `.ts`, nascidos ~457s um do outro.
 *
 * Fix: `MonitoringPage` sabe qual câmera está no drawer (`selectedCamera` +
 * `drawerOpen`) e passa isso para o card da grade via prop `suppressed`. O card
 * usa `suppressed` para desabilitar `useLiveView` (não bate em /stream/start) e
 * não montar `<CameraPlayer>` enquanto o drawer da MESMA câmera está aberto.
 *
 * Este teste prova, via card+drawer reais (só `CameraPlayer` e `AppDrawer` são
 * dublês — hls.js e Radix não fazem parte do que está sendo verificado):
 *   1. câmera visível na grade sobe UM player e chama cameraService.start 1x;
 *   2. abrir o drawer da mesma câmera deixa exatamente UM player montado (o do
 *      drawer) e NÃO dispara um novo /stream/start (reaproveita o cache do
 *      useLiveView — nenhum segundo token é mintado);
 *   3. fechar o drawer restaura o player do card (grid volta ao normal).
 */
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MonitoringPage } from './MonitoringPage'
import { api, getToken } from '../services/api'
import { cameraService } from '../services/cameraService'
import { __resetLiveViewCache } from '../hooks/useLiveView'
import type { Camera } from '../types'

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock('../services/api', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
  getToken: vi.fn(() => 'fake-token'),
  setToken: vi.fn(),
  removeToken: vi.fn(),
}))

// useAuth real lê `user` do localStorage — evitado de propósito: neste
// ambiente de teste o global `localStorage` colide com o Web Storage nativo
// do Node (>=22, sem `--localstorage-file`) e `setItem`/`getItem` quebram
// fora do controle deste arquivo. O hook não é o que está sob teste aqui
// (é só a origem de `user.modules` para o toolbar) — dublê evita a colisão.
vi.mock('../hooks/useAuth', () => ({
  useAuth: () => ({
    user: {
      id: 'u1',
      email: 'op@rvb.com',
      name: 'Operador',
      role: 'operator',
      modules: ['epi'],
    },
    isAuthenticated: true,
    isSuperAdmin: false,
    isAdmin: false,
    modules: ['epi'],
    hasModule: () => true,
    can: () => true,
    login: vi.fn(),
    logout: vi.fn(),
    register: vi.fn(),
  }),
}))

// WebSocket real dispararia socket.io de verdade — fora do escopo deste teste
// (que é sobre coordenação card↔drawer, não sobre detecções ao vivo).
vi.mock('../hooks/useMonitoringSocket', () => ({
  useMonitoringSocket: () => ({
    connected: false,
    detections: {},
    alerts: [],
    subscribeCamera: vi.fn(),
  }),
}))

// CameraPlayer real depende de hls.js/<video> — não é o que está sob teste
// aqui (composição da página). Dublê expõe um testid por câmera para contar
// quantos players estão de fato montados no DOM a qualquer momento.
vi.mock('../components/monitoring/CameraPlayer', () => ({
  CameraPlayer: ({ cameraId }: { cameraId: string }) => (
    <div data-testid={`player-${cameraId}`} />
  ),
}))

// AppDrawer real usa Radix Dialog (portal, focus trap) — irrelevante para a
// pergunta "o conteúdo do drawer está montado ou não". Dublê replica o único
// comportamento do qual a página depende: `isOpen=false` não monta `children`
// (mesmo efeito do Radix ao fechar, sem forceMount).
vi.mock('../components/ui/AppDrawer/AppDrawer', () => ({
  AppDrawer: ({
    isOpen,
    onClose,
    children,
  }: {
    isOpen: boolean
    onClose: () => void
    children: React.ReactNode
  }) =>
    isOpen ? (
      <div data-testid="drawer">
        <button onClick={onClose}>Fechar</button>
        {children}
      </div>
    ) : null,
}))

// IntersectionObserver não existe em jsdom. Dublê reporta "visível" assim que
// o card é observado — suficiente pro `useIntersection` da página liberar o
// player (o que está sob teste é a suspensão via `suppressed`, não o lazy-load
// por viewport em si, que já tem cobertura própria em outro lugar).
type FakeObserverCallback = (
  entries: Array<{ isIntersecting: boolean; target: Element }>,
) => void

class FakeIntersectionObserver {
  private callback: FakeObserverCallback
  constructor(callback: FakeObserverCallback) {
    this.callback = callback
  }
  observe(target: Element) {
    this.callback([{ isIntersecting: true, target }])
  }
  unobserve() {}
  disconnect() {}
  takeRecords() {
    return []
  }
}

const CAM_1: Camera = {
  id: 'cam-1',
  name: 'Portaria',
  location: 'Entrada principal',
  manufacturer: 'intelbras',
  host: '192.168.1.10',
  port: 554,
  channel: 1,
  module_code: 'epi',
  is_active: true,
  created_at: '2026-01-01T00:00:00Z',
}

function mockCamerasList(cameras: Camera[]) {
  vi.mocked(api.get).mockResolvedValue({ data: cameras } as never)
}

beforeEach(() => {
  vi.clearAllMocks()
  __resetLiveViewCache()
  vi.stubGlobal(
    'IntersectionObserver',
    FakeIntersectionObserver as unknown as typeof IntersectionObserver,
  )
  vi.mocked(getToken).mockReturnValue('fake-token')
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('MonitoringPage — sessão única de playback por câmera', () => {
  it('card sobe UM player e UM /stream/start; abrir o drawer da mesma câmera deixa só o player do drawer vivo (sem novo token); fechar restaura o card', async () => {
    mockCamerasList([CAM_1])
    const startSpy = vi
      .spyOn(cameraService, 'start')
      .mockResolvedValue({
        camera_id: CAM_1.id,
        hls_url: `/api/cameras/${CAM_1.id}/stream/s/tok1/stream.m3u8`,
        status: 'ok',
      } as never)

    render(<MonitoringPage />)

    // 1. Grid carrega, câmera fica visível (IntersectionObserver dublê) e o
    //    card sobe seu player — UMA sessão via /stream/start.
    await screen.findByTestId(`player-${CAM_1.id}`)
    expect(startSpy).toHaveBeenCalledTimes(1)
    expect(startSpy).toHaveBeenCalledWith(CAM_1.id)

    // 2. Abre o drawer clicando no card.
    const card = screen.getByRole('button', { name: `Abrir câmera ${CAM_1.name}` })
    fireEvent.click(card)

    const drawer = await screen.findByTestId('drawer')
    await within(drawer).findByTestId(`player-${CAM_1.id}`)

    // Sessão única: só o player do DRAWER está no DOM — o card suprimiu o seu.
    await waitFor(() => {
      expect(screen.getAllByTestId(`player-${CAM_1.id}`)).toHaveLength(1)
    })
    expect(within(drawer).getByTestId(`player-${CAM_1.id}`)).toBeDefined()

    // Card mostra o placeholder de suprimido — não "carregando..." (que
    // indicaria uma segunda sessão em voo).
    expect(screen.getByText('aberto no painel')).toBeDefined()

    // E o mais importante: nenhum SEGUNDO /stream/start foi disparado — o
    // hook do drawer reaproveitou o cache do useLiveView (mesma câmera, token
    // ainda fresco). Prova que não existe um segundo token de playback vivo.
    expect(startSpy).toHaveBeenCalledTimes(1)

    // 3. Fecha o drawer.
    fireEvent.click(within(drawer).getByText('Fechar'))

    await waitFor(() => {
      expect(screen.queryByTestId('drawer')).toBeNull()
    })

    // Grid volta ao normal: o player do card reaparece.
    await waitFor(() => {
      expect(screen.getAllByTestId(`player-${CAM_1.id}`)).toHaveLength(1)
    })
    expect(screen.queryByText('aberto no painel')).toBeNull()

    // Reaquisição do card ao fechar também não mintou token novo (cache
    // ainda fresco — comportamento documentado em useLiveView.ts).
    expect(startSpy).toHaveBeenCalledTimes(1)
  })

  it('sem drawer aberto, o card funciona normalmente (regressão simples)', async () => {
    mockCamerasList([CAM_1])
    vi.spyOn(cameraService, 'start').mockResolvedValue({
      camera_id: CAM_1.id,
      hls_url: `/api/cameras/${CAM_1.id}/stream/s/tok1/stream.m3u8`,
      status: 'ok',
    } as never)

    render(<MonitoringPage />)

    await screen.findByTestId(`player-${CAM_1.id}`)
    expect(screen.queryByTestId('drawer')).toBeNull()
    expect(screen.queryByText('aberto no painel')).toBeNull()
  })
})
