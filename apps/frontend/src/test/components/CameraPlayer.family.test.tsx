/**
 * Teste de REGRESSÃO DE FAMÍLIA — lado do cliente do live view (bug liveview-recovery).
 *
 * Contexto da família de bug (já voltou uma vez):
 *   - Servidor (PR #278, `stream_handlers.py:serve_hls`): a chave
 *     `epi:stream:{camera_id}:active` tem TTL de `HLS_VIEWER_TTL` (90s, default) e é
 *     RENOVADA a cada request bem-sucedido em `serve_hls` — mas só depois de validar o
 *     token de playback. Requests com token morto retornam 404 ANTES da renovação (ver
 *     `stream_handlers.py:376-384` — gate de token vem antes da linha 402, que faz o
 *     `setex`). Se o cliente parar de bater no servidor com um token VÁLIDO por mais de
 *     90s, o edge para de considerar a câmera "wanted" e o pipeline cai — com a tela
 *     aberta, sem qualquer ação do usuário.
 *   - Cliente (PR #280, `CameraPlayer.tsx`): erro fatal de rede do hls.js (manifesto 404
 *     por token expirado, ou rajada de 425 nos .ts escalando a fatal) passa a acionar
 *     `startNetworkRecovery()` → busca URL nova via `refreshLiveViewUrl` (novo
 *     `/stream/start`, token novo) → `loadSource()` com a URL fresca. Backoff dedicado
 *     (`NETWORK_RECOVERY_DELAYS_MS`) e reset do índice de tentativa em `handleProgress()`
 *     quando o progresso volta.
 *
 * O QUE ESTE ARQUIVO PROVA (e os testes de #280 não provam):
 *   `CameraPlayer.recovery.test.tsx` prova peças isoladas — "pede URL nova" (a) e "o
 *   backoff cresce e zera uma vez" (b). Nenhum dos dois olha para a LINHA DO TEMPO
 *   completa nem conecta isso ao TTL do servidor. Este arquivo prova a propriedade de
 *   família: ao longo de uma sessão longa (≥5min virtuais) com múltiplos ciclos de
 *   falha→recuperação, o maior intervalo sem "requisição de manifesto bem-sucedida"
 *   (proxy: evento `FRAG_LOADED`, que só acontece quando o token/URL em uso é válido)
 *   fica sempre abaixo do TTL de 90s do servidor — inclusive no 4º ciclo, que é
 *   exatamente onde a regressão "esqueceram de zerar o backoff" apareceria (backoff
 *   acumulando entre ciclos em vez de resetar a cada sucesso).
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
    static ErrorDetails = {
      MANIFEST_LOAD_ERROR: 'manifestLoadError',
      MANIFEST_LOAD_TIMEOUT: 'manifestLoadTimeOut',
      MANIFEST_PARSING_ERROR: 'manifestParsingError',
      FRAG_LOAD_ERROR: 'fragLoadError',
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

const CAM = 'cam-family-1'
const OLD_URL = '/api/cameras/cam-family-1/stream/s/expired-token/stream.m3u8'

// TTL real do servidor — services/api/app/api/v1/cameras/stream_handlers.py:48
// (`_HLS_INACTIVITY_TTL = int(os.environ.get("HLS_VIEWER_TTL", "90"))`). A chave
// `epi:stream:{camera_id}:active` só é renovada por um request que passa no gate de
// token (linha ~376-384) — ou seja, por um FRAG_LOADED real do lado do cliente.
const SERVER_TTL_MS = 90_000

// Cadência de "heartbeat" saudável simulada entre falhas — bem abaixo do TTL de
// propósito (não é o que este teste mede; só preenche a linha do tempo pra somar
// ≥5min virtuais e garantir que o cenário de falha não é o único tráfego simulado).
const HEALTHY_HEARTBEAT_MS = 20_000
const HEALTHY_BEATS_PER_CYCLE = 4 // 4 * 20s = 80s de tráfego saudável por ciclo

describe('CameraPlayer — regressão de família: gap de manifesto vs TTL do servidor (liveview-recovery)', () => {
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

  it(
    'falha fatal de rede -> re-assina e retoma; gap entre manifestos sob 4 ciclos falha->recuperação ' +
      'nunca chega perto do TTL de 90s do servidor, mesmo repetido',
    async () => {
      let call = 0
      vi.spyOn(cameraService, 'start').mockImplementation(async () => {
        call += 1
        return {
          camera_id: CAM,
          hls_url: `/api/cameras/${CAM}/stream/s/fresh-token-${call}/stream.m3u8`,
          status: 'started',
        } as never
      })

      render(<CameraPlayer cameraId={CAM} hlsUrl={OLD_URL} />)
      const hls = lastHls()

      // manifestRequestLog: timestamp (relógio fake) de cada evento FRAG_LOADED — proxy
      // para "requisição de manifesto/segmento que chegou ao servidor com token válido e
      // renovou a chave :active". É exatamente o mesmo evento que o componente usa para
      // decidir que "progresso real" aconteceu (handleProgress).
      const manifestRequestLog: number[] = []

      function healthyHeartbeat() {
        act(() => {
          hls.trigger('hlsFragLoaded')
        })
        manifestRequestLog.push(Date.now())
      }

      async function advance(ms: number) {
        await act(async () => {
          await vi.advanceTimersByTimeAsync(ms)
        })
      }

      // Playback inicial ok.
      act(() => {
        hls.trigger('hlsManifestParsed')
      })
      manifestRequestLog.push(Date.now())

      const CYCLES = 4
      for (let cycle = 1; cycle <= CYCLES; cycle += 1) {
        // --- fase saudável: tráfego normal de manifesto/segmentos ---
        for (let beat = 0; beat < HEALTHY_BEATS_PER_CYCLE; beat += 1) {
          await advance(HEALTHY_HEARTBEAT_MS)
          healthyHeartbeat()
        }

        // --- surto de erros escalando a fatal ---
        // Alguns erros não-fatais primeiro (ex.: 425 pontual nos .ts) — o componente os
        // ignora (`if (!data.fatal) return`), só documentam o "surto" antes do fatal.
        act(() => {
          hls.trigger('hlsError', { fatal: false, type: 'networkError', details: 'fragLoadError' })
          hls.trigger('hlsError', { fatal: false, type: 'networkError', details: 'fragLoadError' })
        })

        // Erro fatal: alterna entre "manifesto 404 por token vencido" (ciclos ímpares) e
        // "rajada de 425 nos segmentos escalando a fatal" (ciclos pares) — os dois batem
        // no mesmo branch do componente (qualquer NETWORK_ERROR fatal -> startNetworkRecovery).
        const details = cycle % 2 === 1 ? 'manifestLoadError' : 'fragLoadError'
        act(() => {
          hls.trigger('hlsError', { fatal: true, type: 'networkError', details })
        })

        // (a) Câmera some da UI (overlay "reconectando"), sem overlay de desistência ainda.
        expect(screen.getByText(/reconectando/i)).toBeDefined()
        expect(screen.queryByText(/não foi possível reconectar/i)).toBeNull()

        // (c) A 1ª tentativa de recuperação é IMEDIATA (delay 0) em TODO ciclo — isso só é
        // verdade se `networkRecoveryAttemptRef` foi zerado no sucesso do ciclo anterior
        // (handleProgress). Se a regressão "esqueceram de resetar o backoff entre ciclos"
        // voltasse, a partir do 2º ciclo o índice de tentativa já estaria em 1 e a próxima
        // tentativa só sairia em NETWORK_RECOVERY_DELAYS_MS[1] = 2000ms — avançar 0ms NÃO
        // bastaria e esta asserção falharia aqui, no ciclo exato em que a regressão nasce.
        const callsBeforeAttempt = call
        await advance(0)
        expect(
          cameraService.start,
          `ciclo ${cycle}: 1ª tentativa de recuperação deveria ser IMEDIATA (delay 0) — ` +
            'backoff da recuperação de rede não foi resetado entre ciclos (regressão de família)',
        ).toHaveBeenCalledTimes(callsBeforeAttempt + 1)

        // A URL usada é NOVA (não a antiga morta) — mesma prova do teste (a) do #280,
        // repetida em CADA ciclo (não só no primeiro).
        const lastLoadedUrl = hls.loadSource.mock.calls[hls.loadSource.mock.calls.length - 1][0]
        expect(lastLoadedUrl).toBe(`/api/cameras/${CAM}/stream/s/fresh-token-${call}/stream.m3u8`)
        expect(lastLoadedUrl).not.toBe(OLD_URL)

        // Progresso real confirma que o manifesto voltou a ser consumido com a URL nova —
        // este é o request que, no servidor real, renova a chave :active.
        healthyHeartbeat()

        // (a) Retomou: overlays de erro somem.
        expect(screen.queryByText(/reconectando/i)).toBeNull()
        expect(screen.queryByText(/não foi possível reconectar/i)).toBeNull()
      }

      // --- (b) propriedade de família: gap máximo entre requisições de manifesto ao longo
      // de TODA a linha do tempo fica abaixo do TTL do servidor (90s) ---
      let maxGap = 0
      for (let i = 1; i < manifestRequestLog.length; i += 1) {
        maxGap = Math.max(maxGap, manifestRequestLog[i] - manifestRequestLog[i - 1])
      }
      expect(manifestRequestLog.length).toBeGreaterThan(CYCLES * HEALTHY_BEATS_PER_CYCLE)
      expect(
        maxGap,
        `maior gap entre requisições de manifesto (${maxGap}ms) precisa ficar abaixo do ` +
          `TTL do servidor (${SERVER_TTL_MS}ms) — senão o edge derruba a câmera com a tela aberta`,
      ).toBeLessThan(SERVER_TTL_MS)

      // Linha do tempo virtual total >= 5min, como pedido.
      const totalElapsed = manifestRequestLog[manifestRequestLog.length - 1] - manifestRequestLog[0]
      expect(totalElapsed).toBeGreaterThanOrEqual(5 * 60 * 1000)
    },
  )
})
