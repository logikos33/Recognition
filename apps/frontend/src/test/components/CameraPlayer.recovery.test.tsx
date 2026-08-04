/**
 * Testes de recuperação de erro fatal de REDE do hls.js (bug liveview-recovery).
 *
 * Contexto: `CameraPlayer` recebia a `hlsUrl` como prop e, em erro fatal do hls.js,
 * recarregava a MESMA url via closure (`loadSource(hlsUrl)`). Nenhum consumidor do
 * `useLiveView` chamava `refresh()`, então quando o token de playback expirava (TTL
 * 1h) ou uma rajada de 425 nos `.ts` do edge escalava para erro fatal de rede, o
 * player ficava preso retentando uma URL morta pra sempre.
 *
 * Correção: em erro fatal do tipo REDE, o player busca uma URL NOVA
 * (`refreshLiveViewUrl`, que força um novo `/stream/start`) em vez de recarregar a
 * mesma. O ciclo tem backoff exponencial com teto de 30s e desiste após esgotar
 * `NETWORK_RECOVERY_DELAYS_MS` ([0, 2000, 4000, 8000, 16000, 30000]ms), mostrando
 * erro visível em vez de martelar o backend pra sempre em silêncio.
 */
import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { CameraPlayer } from '../../components/monitoring/CameraPlayer'
import { cameraService } from '../../services/cameraService'
import { __resetLiveViewCache } from '../../hooks/useLiveView'

type Listener = (event: string, data?: unknown) => void

const { instances } = vi.hoisted(() => ({ instances: [] as MockHlsInstance[] }))

interface MockHlsInstance {
  listeners: Record<string, Listener[]>
  stopLoad: ReturnType<typeof vi.fn>
  startLoad: ReturnType<typeof vi.fn>
  destroy: ReturnType<typeof vi.fn>
  loadSource: ReturnType<typeof vi.fn>
  attachMedia: ReturnType<typeof vi.fn>
  recoverMediaError: ReturnType<typeof vi.fn>
  on: (event: string, cb: Listener) => void
  trigger: (event: string, data?: unknown) => void
}

vi.mock('hls.js', () => {
  class MockHls implements MockHlsInstance {
    static isSupported = () => true
    static Events = {
      MANIFEST_PARSED: 'hlsManifestParsed',
      FRAG_LOADED: 'hlsFragLoaded',
      ERROR: 'hlsError',
    }
    static ErrorTypes = {
      MEDIA_ERROR: 'mediaError',
      NETWORK_ERROR: 'networkError',
      OTHER_ERROR: 'otherError',
    }
    static ErrorDetails = {
      MANIFEST_LOAD_ERROR: 'manifestLoadError',
      MANIFEST_LOAD_TIMEOUT: 'manifestLoadTimeOut',
      MANIFEST_PARSING_ERROR: 'manifestParsingError',
    }
    listeners: Record<string, Listener[]> = {}
    stopLoad = vi.fn()
    startLoad = vi.fn()
    destroy = vi.fn()
    loadSource = vi.fn()
    attachMedia = vi.fn()
    recoverMediaError = vi.fn()

    constructor() {
      instances.push(this)
    }

    on(event: string, cb: Listener) {
      ;(this.listeners[event] ||= []).push(cb)
    }

    trigger(event: string, data?: unknown) {
      ;(this.listeners[event] || []).forEach((cb) => cb(event, data))
    }
  }
  return { default: MockHls }
})

function lastHls(): MockHlsInstance {
  return instances[instances.length - 1]
}

/** Simula o evento ERROR fatal de rede que o hls.js emite (manifesto 404 por token
 * expirado, ou rajada de 425 nos .ts escalando para fatal). */
function triggerFatalNetworkError(hls: MockHlsInstance) {
  act(() => {
    hls.trigger('hlsError', { fatal: true, type: 'networkError', details: 'manifestLoadError' })
  })
}

const CAM = 'cam-recovery-1'
const OLD_URL = '/api/cameras/cam-recovery-1/stream/s/expired-token/stream.m3u8'

function mockFreshUrl(n: number) {
  return `/api/cameras/cam-recovery-1/stream/s/fresh-token-${n}/stream.m3u8`
}

describe('CameraPlayer — recuperação de erro fatal de rede (bug liveview-recovery)', () => {
  beforeEach(() => {
    instances.length = 0
    __resetLiveViewCache()
    vi.useFakeTimers()
    // jsdom não implementa HTMLMediaElement.play() — evita erro "not implemented"
    HTMLMediaElement.prototype.play = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(document, 'hidden', { configurable: true, get: () => false })
  })

  afterEach(() => {
    vi.clearAllTimers()
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('(a) erro fatal de rede: player busca URL NOVA (não a mesma) e retoma', async () => {
    let call = 0
    vi.spyOn(cameraService, 'start').mockImplementation(async () => {
      call += 1
      return { camera_id: CAM, hls_url: mockFreshUrl(call), status: 'started' } as never
    })

    render(<CameraPlayer cameraId={CAM} hlsUrl={OLD_URL} />)
    const hls = lastHls()

    triggerFatalNetworkError(hls)

    // 1ª tentativa é imediata (delay 0) — só precisa drenar o microtask do fetch.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0)
    })

    expect(cameraService.start).toHaveBeenCalledTimes(1)
    expect(cameraService.start).toHaveBeenCalledWith(CAM)

    // loadSource tem que ter sido chamado de novo, com uma URL DIFERENTE da original —
    // não a mesma URL morta que causou o 404/erro fatal.
    const loadSourceCalls = hls.loadSource.mock.calls.map((c) => c[0])
    expect(loadSourceCalls.length).toBeGreaterThanOrEqual(2) // inicial + recuperação
    const lastLoadedUrl = loadSourceCalls[loadSourceCalls.length - 1]
    expect(lastLoadedUrl).not.toBe(OLD_URL)
    expect(lastLoadedUrl).toBe(mockFreshUrl(1))

    // Retoma: progresso real chega e a UI sai do estado de erro/offline.
    act(() => {
      hls.trigger('hlsFragLoaded')
    })
    expect(screen.queryByText(/reconectando/i)).toBeNull()
    expect(screen.queryByText(/não foi possível reconectar/i)).toBeNull()
  })

  it('(b) backoff cresce entre tentativas (0 → 2s → 4s → 8s...) e zera após sucesso', async () => {
    let call = 0
    vi.spyOn(cameraService, 'start').mockImplementation(async () => {
      call += 1
      return { camera_id: CAM, hls_url: mockFreshUrl(call), status: 'started' } as never
    })

    render(<CameraPlayer cameraId={CAM} hlsUrl={OLD_URL} />)
    const hls = lastHls()

    // 1º erro fatal -> tentativa imediata (delay 0)
    triggerFatalNetworkError(hls)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0)
    })
    expect(cameraService.start).toHaveBeenCalledTimes(1)

    // 2º erro fatal (a tentativa 1 também falhou) -> próxima tentativa só em 2000ms
    triggerFatalNetworkError(hls)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000)
    })
    expect(cameraService.start).toHaveBeenCalledTimes(1) // ainda não — só passou 1000 dos 2000
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000)
    })
    expect(cameraService.start).toHaveBeenCalledTimes(2) // completou os 2000ms

    // 3º erro fatal -> próxima tentativa em 4000ms
    triggerFatalNetworkError(hls)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(3999)
    })
    expect(cameraService.start).toHaveBeenCalledTimes(2)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1)
    })
    expect(cameraService.start).toHaveBeenCalledTimes(3)

    // Sucesso: progresso real chega -> zera o backoff da recuperação de rede.
    act(() => {
      hls.trigger('hlsFragLoaded')
    })

    // Um novo erro fatal de rede depois do sucesso volta a tentar IMEDIATAMENTE
    // (delay 0), prova que o índice de backoff foi resetado — não continuou em 8000ms.
    triggerFatalNetworkError(hls)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0)
    })
    expect(cameraService.start).toHaveBeenCalledTimes(4)
  })

  it('(c) esgota as tentativas -> erro visível na UI, sem retentativa infinita', async () => {
    vi.spyOn(cameraService, 'start').mockImplementation(async () => {
      throw new Error('backend indisponível')
    })

    render(<CameraPlayer cameraId={CAM} hlsUrl={OLD_URL} />)
    const hls = lastHls()

    // NETWORK_RECOVERY_DELAYS_MS = [0, 2000, 4000, 8000, 16000, 30000] -> 6 tentativas.
    const delays = [0, 2000, 4000, 8000, 16000, 30000]
    for (const delay of delays) {
      triggerFatalNetworkError(hls)
      await act(async () => {
        await vi.advanceTimersByTimeAsync(delay)
      })
    }

    expect(cameraService.start).toHaveBeenCalledTimes(delays.length)

    // Esgotou -> mais um erro fatal não deve agendar nova tentativa (já desistiu).
    triggerFatalNetworkError(hls)
    expect(screen.getByText(/não foi possível reconectar/i)).toBeDefined()
    expect(screen.queryByText(/reconectando/i)).toBeNull()

    // Nenhuma retentativa infinita: avançar bastante o relógio não gera mais chamadas.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(120000)
    })
    expect(cameraService.start).toHaveBeenCalledTimes(delays.length)

    // Botão manual "Tentar novamente" ainda funciona (retry explícito do usuário).
    const retryBtn = screen.getByRole('button', { name: /tentar novamente/i })
    expect(retryBtn).toBeDefined()
  })

  it('(d) bug liveview-contexto-visivel: "Tentar novamente" busca URL FRESCA, não recarrega o token morto', async () => {
    // A 1ª tentativa automática falha 6x (esgota NETWORK_RECOVERY_DELAYS_MS);
    // só a partir da 7ª chamada (retry manual) o backend passa a responder OK.
    let call = 0
    vi.spyOn(cameraService, 'start').mockImplementation(async () => {
      call += 1
      if (call <= 6) throw new Error('backend indisponível')
      return { camera_id: CAM, hls_url: mockFreshUrl(call), status: 'started' } as never
    })

    render(<CameraPlayer cameraId={CAM} hlsUrl={OLD_URL} />)
    const hls = lastHls()

    const delays = [0, 2000, 4000, 8000, 16000, 30000]
    for (const delay of delays) {
      triggerFatalNetworkError(hls)
      await act(async () => {
        await vi.advanceTimersByTimeAsync(delay)
      })
    }
    expect(cameraService.start).toHaveBeenCalledTimes(6)

    // Esgotou -> mais um erro fatal desiste de vez (mesmo padrão do teste (c)).
    triggerFatalNetworkError(hls)
    expect(screen.getByText(/não foi possível reconectar/i)).toBeDefined()

    // Clique manual: busca /stream/start de novo (URL fresca), NÃO só recarrega
    // a mesma `hlsUrl` morta da prop original via loadSource.
    const retryBtn = screen.getByRole('button', { name: /tentar novamente/i })
    await act(async () => {
      fireEvent.click(retryBtn)
      await vi.advanceTimersByTimeAsync(0)
      await vi.advanceTimersByTimeAsync(0)
    })

    expect(cameraService.start).toHaveBeenCalledTimes(7)

    // "Tentar novamente" faz um restart completo (mesmo caminho de
    // reacquireAfterHidden — startHlsWithUrl): destrói a instância velha do
    // hls.js e cria uma nova já com a URL fresca — não reaproveita a
    // instância presa no token morto.
    const freshHls = lastHls()
    expect(freshHls).not.toBe(hls)
    const loadSourceCalls = freshHls.loadSource.mock.calls.map((c) => c[0])
    expect(loadSourceCalls[loadSourceCalls.length - 1]).toBe(mockFreshUrl(7))
    expect(loadSourceCalls[loadSourceCalls.length - 1]).not.toBe(OLD_URL)

    // Retomou: sucesso zera os dois ciclos de backoff, sem estado de erro visível.
    act(() => {
      freshHls.trigger('hlsFragLoaded')
    })
    expect(screen.queryByText(/não foi possível reconectar/i)).toBeNull()
    expect(screen.queryByText(/reconectando/i)).toBeNull()

    // Backoff de fato zerado: um novo erro fatal tenta de novo IMEDIATAMENTE
    // (delay 0), prova que o clique manual resetou networkRecoveryAttemptRef.
    triggerFatalNetworkError(freshHls)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0)
    })
    expect(cameraService.start).toHaveBeenCalledTimes(8)
  })

  it('(e) 410 playback_token_expired: renova a URL no PRIMEIRO evento, sem esperar escalar para fatal', async () => {
    // serve_hls agora distingue token expirado (410 + error_code
    // playback_token_expired) de stream inexistente (404). O player reage ao
    // primeiro ERROR não-fatal com response.code 410 — sem gastar os 2 retries
    // internos do hls.js (2×2s) recarregando uma URL que NUNCA vai voltar a
    // funcionar (o token precisa ser re-assinado pelo backend).
    let call = 0
    vi.spyOn(cameraService, 'start').mockImplementation(async () => {
      call += 1
      return { camera_id: CAM, hls_url: mockFreshUrl(call), status: 'started' } as never
    })

    render(<CameraPlayer cameraId={CAM} hlsUrl={OLD_URL} />)
    const hls = lastHls()

    // Evento NÃO-fatal (hls.js ainda ia retentar internamente) com HTTP 410.
    act(() => {
      hls.trigger('hlsError', {
        fatal: false,
        type: 'networkError',
        details: 'manifestLoadError',
        response: { code: 410 },
      })
    })

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0)
    })

    expect(cameraService.start).toHaveBeenCalledTimes(1)
    const loadSourceCalls = hls.loadSource.mock.calls.map((c) => c[0])
    expect(loadSourceCalls[loadSourceCalls.length - 1]).toBe(mockFreshUrl(1))
    expect(loadSourceCalls[loadSourceCalls.length - 1]).not.toBe(OLD_URL)
  })
})
