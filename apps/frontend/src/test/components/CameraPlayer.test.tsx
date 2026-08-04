/**
 * Testes Vitest/RTL para CameraPlayer (task-068 — stall/offline/backoff/visibility).
 *
 * hls.js é mockado com uma classe fake que expõe stopLoad/startLoad/destroy como spies
 * e um método `trigger(event, data)` pra simular eventos (MANIFEST_PARSED, FRAG_LOADED, ERROR).
 */
import { act, render, screen } from '@testing-library/react'
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

function setDocumentHidden(hidden: boolean) {
  Object.defineProperty(document, 'hidden', { configurable: true, get: () => hidden })
  act(() => {
    document.dispatchEvent(new Event('visibilitychange'))
  })
}

describe('CameraPlayer — stall/offline/backoff/visibility (task-068)', () => {
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

  it('mostra "Câmera offline — reconectando..." quando nenhum fragmento chega por STALL_TIMEOUT_MS', async () => {
    render(<CameraPlayer cameraId="1" hlsUrl="/stream.m3u8" />)

    act(() => {
      lastHls().trigger('hlsManifestParsed')
    })

    expect(screen.queryByText(/reconectando/i)).toBeNull()

    // Nenhum FRAG_LOADED chega — avança até o watchdog de stall disparar (14s)
    act(() => {
      vi.advanceTimersByTime(14000)
    })

    expect(screen.getByText('Câmera offline — reconectando...')).toBeDefined()
    expect(lastHls().stopLoad).toHaveBeenCalled()
  })

  it('escala o backoff de reconexão em 1s → 2s → 5s entre tentativas', async () => {
    render(<CameraPlayer cameraId="1" hlsUrl="/stream.m3u8" />)
    const hls = lastHls()

    act(() => {
      hls.trigger('hlsManifestParsed')
    })

    // 1ª falta de progresso -> stall dispara -> agenda 1ª tentativa em 1000ms
    act(() => {
      vi.advanceTimersByTime(14000)
    })
    expect(hls.startLoad).toHaveBeenCalledTimes(0)
    act(() => {
      vi.advanceTimersByTime(1000)
    })
    expect(hls.startLoad).toHaveBeenCalledTimes(1)

    // 2ª falta de progresso -> próxima tentativa agora em 2000ms
    act(() => {
      vi.advanceTimersByTime(14000)
    })
    act(() => {
      vi.advanceTimersByTime(1000)
    })
    expect(hls.startLoad).toHaveBeenCalledTimes(1) // ainda não — só passaram 1000 dos 2000
    act(() => {
      vi.advanceTimersByTime(1000)
    })
    expect(hls.startLoad).toHaveBeenCalledTimes(2)

    // 3ª falta de progresso -> próxima tentativa em 5000ms (teto)
    act(() => {
      vi.advanceTimersByTime(14000)
    })
    act(() => {
      vi.advanceTimersByTime(4000)
    })
    expect(hls.startLoad).toHaveBeenCalledTimes(2) // ainda não — só passaram 4000 dos 5000
    act(() => {
      vi.advanceTimersByTime(1000)
    })
    expect(hls.startLoad).toHaveBeenCalledTimes(3)
  })

  it('reseta o backoff e sai do estado offline quando um fragmento novo chega (recuperação)', async () => {
    render(<CameraPlayer cameraId="1" hlsUrl="/stream.m3u8" />)
    const hls = lastHls()

    act(() => {
      hls.trigger('hlsManifestParsed')
    })
    act(() => {
      vi.advanceTimersByTime(14000)
    })
    expect(screen.getByText('Câmera offline — reconectando...')).toBeDefined()

    act(() => {
      hls.trigger('hlsFragLoaded')
    })

    expect(screen.queryByText(/reconectando/i)).toBeNull()
  })

  // task-teardown-abas: substitui o teste antigo de pausa (stopLoad/startLoad).
  // A sessão agora é encerrada DE VERDADE quando a aba fica oculta — destrói a
  // instância hls.js (não fetch nenhum sobrevive, nem watchdog) — e, ao voltar
  // a ficar visível, readquire pelo MESMO caminho do #280 (refreshLiveViewUrl:
  // novo /stream/start, URL tokenizada fresca), com uma instância nova.
  it('encerra a sessão de verdade (destrói hls.js) quando a aba fica oculta, e readquire com URL nova ao voltar a ficar visível', async () => {
    let call = 0
    vi.spyOn(cameraService, 'start').mockImplementation(async () => {
      call += 1
      return {
        camera_id: '1',
        hls_url: `/api/cameras/1/stream/s/fresh-token-${call}/stream.m3u8`,
        status: 'started',
      } as never
    })

    render(<CameraPlayer cameraId="1" hlsUrl="/stream.m3u8" />)
    const hlsBefore = lastHls()

    act(() => {
      hlsBefore.trigger('hlsManifestParsed')
    })

    setDocumentHidden(true)

    // Destrói de verdade — não é mais só stopLoad().
    expect(hlsBefore.destroy).toHaveBeenCalled()

    setDocumentHidden(false)

    // Reaquisição é assíncrona (refreshLiveViewUrl -> novo POST /stream/start).
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0)
    })

    expect(cameraService.start).toHaveBeenCalledWith('1')

    const hlsAfter = lastHls()
    // Instância NOVA (a antiga foi destruída, não reaproveitada).
    expect(hlsAfter).not.toBe(hlsBefore)
    expect(hlsAfter.loadSource).toHaveBeenCalledWith('/api/cameras/1/stream/s/fresh-token-1/stream.m3u8')
  })

  it('limpa todos os timers pendentes no unmount (nenhum setTimeout sobrevive)', () => {
    const { unmount } = render(<CameraPlayer cameraId="1" hlsUrl="/stream.m3u8" />)
    const hls = lastHls()

    act(() => {
      hls.trigger('hlsManifestParsed')
    })

    expect(vi.getTimerCount()).toBeGreaterThan(0)

    act(() => {
      unmount()
    })

    expect(vi.getTimerCount()).toBe(0)
    expect(hls.destroy).toHaveBeenCalled()

    // avançar o relógio não deve chamar mais nada (nenhum timer órfão)
    const startLoadCallsAfterUnmount = hls.startLoad.mock.calls.length
    act(() => {
      vi.advanceTimersByTime(30000)
    })
    expect(hls.startLoad.mock.calls.length).toBe(startLoadCallsAfterUnmount)
  })
})
