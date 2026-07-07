/**
 * Testes Vitest/RTL para CameraPlayer (task-068 — stall/offline/backoff/visibility).
 *
 * hls.js é mockado com uma classe fake que expõe stopLoad/startLoad/destroy como spies
 * e um método `trigger(event, data)` pra simular eventos (MANIFEST_PARSED, FRAG_LOADED, ERROR).
 */
import { act, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { CameraPlayer } from '../../components/monitoring/CameraPlayer'

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
    vi.useFakeTimers()
    // jsdom não implementa HTMLMediaElement.play() — evita erro "not implemented"
    HTMLMediaElement.prototype.play = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(document, 'hidden', { configurable: true, get: () => false })
  })

  afterEach(() => {
    vi.clearAllTimers()
    vi.useRealTimers()
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

  it('pausa a rede (stopLoad) quando a aba fica oculta e retoma (startLoad) quando volta a ficar visível', () => {
    render(<CameraPlayer cameraId="1" hlsUrl="/stream.m3u8" />)
    const hls = lastHls()

    act(() => {
      hls.trigger('hlsManifestParsed')
    })

    setDocumentHidden(true)
    expect(hls.stopLoad).toHaveBeenCalled()

    const startLoadCallsBefore = hls.startLoad.mock.calls.length
    setDocumentHidden(false)
    expect(hls.startLoad.mock.calls.length).toBeGreaterThan(startLoadCallsBefore)
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
