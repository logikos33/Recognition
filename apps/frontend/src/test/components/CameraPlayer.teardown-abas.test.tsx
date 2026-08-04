/**
 * task-teardown-abas: abas antigas/em segundo plano do navegador mantinham a
 * sessão de live view viva indefinidamente, consumindo segmentos HLS e egress
 * sem que ninguém estivesse de fato olhando.
 *
 * O que existia antes (task-068, ver `CameraPlayer.test.tsx`): visibilitychange
 * já pausava a rede (`hls.stopLoad()`) na aba oculta e retomava
 * (`hls.startLoad()`) na volta — mas a instância hls.js continuava viva,
 * segurando buffers/watchdogs, e reaproveitava a MESMA url ao voltar (que pode
 * ter expirado depois de horas em segundo plano).
 *
 * O que muda aqui: a aba oculta ENCERRA a sessão de verdade — destrói a
 * instância hls.js (`destroy()`, não só `stopLoad()`) e solta o `<video>` — e a
 * volta à visibilidade READQUIRE pelo MESMO caminho já usado pela recuperação
 * de erro fatal de rede (#280, `refreshLiveViewUrl` — força um novo
 * `POST /stream/start` e devolve uma URL tokenizada fresca), nunca reaproveitando
 * a URL antiga.
 *
 * Não existe endpoint de "release" por espectador no backend
 * (`services/api/app/api/v1/cameras/routes.py` só expõe `/stream/start` e
 * `/stream/stop`) — `/stream/stop` mata o FFmpeg da câmera para TODO mundo que
 * estiver olhando (outra aba, outro usuário do tenant), então o teardown de aba
 * nunca deve chamá-lo. A sessão "morre" no servidor sozinha: a chave
 * `epi:stream:{camera_id}:active` (TTL `HLS_VIEWER_TTL`, default 90s —
 * `stream_handlers.py`) só é renovada quando alguém de fato busca um segmento;
 * parar de buscar (o que este teardown garante) é suficiente.
 */
import { act, render } from '@testing-library/react'
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

function setHidden(hidden: boolean) {
  Object.defineProperty(document, 'hidden', { configurable: true, get: () => hidden })
  act(() => {
    document.dispatchEvent(new Event('visibilitychange'))
  })
}

/** Promise controlável de fora — para testar corridas (hidden->visible->hidden
 * de novo ANTES da reaquisição assíncrona resolver). */
function deferred<T>() {
  let resolve!: (v: T) => void
  let reject!: (e: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

const CAM = 'cam-teardown-abas-1'
const INITIAL_URL = '/api/cameras/cam-teardown-abas-1/stream/s/initial-token/stream.m3u8'

describe('CameraPlayer — teardown de sessão da aba (task-teardown-abas)', () => {
  beforeEach(() => {
    instances.length = 0
    __resetLiveViewCache()
    vi.useFakeTimers()
    // jsdom não implementa HTMLMediaElement.play/pause/load() — evita erro "not implemented"
    HTMLMediaElement.prototype.play = vi.fn().mockResolvedValue(undefined)
    HTMLMediaElement.prototype.pause = vi.fn()
    HTMLMediaElement.prototype.load = vi.fn()
    Object.defineProperty(document, 'hidden', { configurable: true, get: () => false })
  })

  afterEach(() => {
    vi.clearAllTimers()
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('aba oculta: destrói a instância hls.js de verdade (não fica esperando fragmento, nenhuma instância nova enquanto oculta)', () => {
    render(<CameraPlayer cameraId={CAM} hlsUrl={INITIAL_URL} />)
    const hls = lastHls()

    act(() => {
      hls.trigger('hlsManifestParsed')
    })

    setHidden(true)

    expect(hls.destroy).toHaveBeenCalled()
    // Nenhuma instância nova é criada enquanto a aba segue oculta.
    expect(instances.length).toBe(1)
  })

  it('volta a ficar visível: readquire pelo caminho normal (#280) — URL tokenizada NOVA, nunca a antiga', async () => {
    let call = 0
    vi.spyOn(cameraService, 'start').mockImplementation(async () => {
      call += 1
      return {
        camera_id: CAM,
        hls_url: `/api/cameras/${CAM}/stream/s/fresh-token-${call}/stream.m3u8`,
        status: 'started',
      } as never
    })

    render(<CameraPlayer cameraId={CAM} hlsUrl={INITIAL_URL} />)
    const hlsBefore = lastHls()
    act(() => {
      hlsBefore.trigger('hlsManifestParsed')
    })

    setHidden(true)
    expect(hlsBefore.destroy).toHaveBeenCalled()

    setHidden(false)

    // refreshLiveViewUrl -> POST /stream/start é assíncrono; drena o microtask.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0)
    })

    expect(cameraService.start).toHaveBeenCalledWith(CAM)

    const hlsAfter = lastHls()
    expect(hlsAfter).not.toBe(hlsBefore)
    expect(hlsAfter.loadSource).toHaveBeenCalledWith(
      `/api/cameras/${CAM}/stream/s/fresh-token-1/stream.m3u8`,
    )
    // Nunca a URL antiga/pré-oculta.
    expect(hlsAfter.loadSource).not.toHaveBeenCalledWith(INITIAL_URL)
  })

  it('reaquisição em voo é descartada se a aba ficar oculta de novo antes dela resolver (sem instância zumbi)', async () => {
    const first = deferred<{ camera_id: string; hls_url: string; status: string }>()
    vi.spyOn(cameraService, 'start').mockReturnValueOnce(first.promise as never)

    render(<CameraPlayer cameraId={CAM} hlsUrl={INITIAL_URL} />)
    const hls = lastHls()
    act(() => {
      hls.trigger('hlsManifestParsed')
    })

    // 1ª oculta: destrói.
    setHidden(true)
    expect(instances.length).toBe(1)

    // Volta visível: dispara reaquisição, mas a promise ainda não resolveu.
    setHidden(false)

    // 2ª oculta ANTES da resposta chegar — supera a reaquisição em voo.
    setHidden(true)

    // Agora a resposta chega (URL fresca) — mas a aba já está oculta de novo.
    first.resolve({
      camera_id: CAM,
      hls_url: '/api/cameras/cam-teardown-abas-1/stream/s/stale-race-token/stream.m3u8',
      status: 'started',
    })
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0)
    })

    // Nenhuma instância nova foi criada — a reaquisição obsoleta foi descartada.
    expect(instances.length).toBe(1)
  })

  it('unmount enquanto uma reaquisição está em voo não deixa instância órfã depois de resolver', async () => {
    const first = deferred<{ camera_id: string; hls_url: string; status: string }>()
    vi.spyOn(cameraService, 'start').mockReturnValueOnce(first.promise as never)

    const { unmount } = render(<CameraPlayer cameraId={CAM} hlsUrl={INITIAL_URL} />)
    const hls = lastHls()
    act(() => {
      hls.trigger('hlsManifestParsed')
    })

    setHidden(true)
    setHidden(false) // dispara reaquisição, promise ainda pendente

    act(() => {
      unmount()
    })

    first.resolve({
      camera_id: CAM,
      hls_url: '/api/cameras/cam-teardown-abas-1/stream/s/post-unmount-token/stream.m3u8',
      status: 'started',
    })
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0)
    })

    // Nenhuma instância nova surge depois do unmount.
    expect(instances.length).toBe(1)
    expect(vi.getTimerCount()).toBe(0)
  })

  it('nunca chama /stream/stop (endpoint global da câmera) no teardown de aba — derrubaria outros espectadores da mesma câmera', async () => {
    const stopSpy = vi.spyOn(cameraService, 'stop').mockResolvedValue(undefined)
    vi.spyOn(cameraService, 'start').mockResolvedValue({
      camera_id: CAM,
      hls_url: '/api/cameras/cam-teardown-abas-1/stream/s/next-token/stream.m3u8',
      status: 'started',
    } as never)

    const { unmount } = render(<CameraPlayer cameraId={CAM} hlsUrl={INITIAL_URL} />)
    const hls = lastHls()
    act(() => {
      hls.trigger('hlsManifestParsed')
    })

    setHidden(true)
    setHidden(false)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0)
    })
    act(() => {
      unmount()
    })

    expect(stopSpy).not.toHaveBeenCalled()
  })
})
