/**
 * Regressão do live view.
 *
 * Dois bugs que este teste tranca:
 *
 * 1. TELA PRETA — as telas montavam a URL do stream no front
 *    (`${API}/api/cameras/{id}/stream/stream.m3u8`). Com
 *    `HLS_REQUIRE_PLAYBACK_TOKEN` ligado (default desde o mutirão), essa URL
 *    recebe 404 em `serve_hls`, porque o token de playback é o único portão de
 *    tenant do endpoint (que é público por design). A URL TEM que vir do
 *    backend, via `POST /stream/start`.
 *
 * 2. TEMPESTADE DE /stream/start — havia registro de 5 chamadas em 13s: um grid
 *    com N câmeras disparava um POST por câmera a cada re-render.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { act, renderHook, waitFor } from '@testing-library/react'
import { useLiveView, __resetLiveViewCache } from '../../hooks/useLiveView'
import { cameraService } from '../../services/cameraService'

const CAM = 'eb1501db-82ad-485a-a441-5c665b4e5a28'
const TOKENIZED = `/api/cameras/${CAM}/stream/s/1799999999.abc123/stream.m3u8`

describe('useLiveView', () => {
  beforeEach(() => {
    __resetLiveViewCache()
    vi.restoreAllMocks()
  })

  it('usa a hls_url tokenizada do backend, não uma URL montada no front', async () => {
    const spy = vi
      .spyOn(cameraService, 'start')
      .mockResolvedValue({ hls_url: TOKENIZED } as never)

    const { result } = renderHook(() => useLiveView(CAM))

    await waitFor(() => expect(result.current.hlsUrl).not.toBeNull())

    expect(spy).toHaveBeenCalledWith(CAM)
    // O token tem que estar no PATH — `?token=` em query é ignorado pelo
    // serve_hls, que lê do path (os .ts relativos herdam o token).
    expect(result.current.hlsUrl).toContain('/stream/s/')
    expect(result.current.hlsUrl).not.toContain('?token=')
  })

  it('não dispara /stream/start em duplicidade para a mesma câmera', async () => {
    const spy = vi
      .spyOn(cameraService, 'start')
      .mockResolvedValue({ hls_url: TOKENIZED } as never)

    // Três consumidores da mesma câmera, como num grid — devem compartilhar
    // uma única chamada.
    const a = renderHook(() => useLiveView(CAM))
    const b = renderHook(() => useLiveView(CAM))
    const c = renderHook(() => useLiveView(CAM))

    await waitFor(() => {
      expect(a.result.current.hlsUrl).not.toBeNull()
      expect(b.result.current.hlsUrl).not.toBeNull()
      expect(c.result.current.hlsUrl).not.toBeNull()
    })

    expect(spy).toHaveBeenCalledTimes(1)
  })

  it('reaproveita a URL em cache num remount, sem novo request', async () => {
    const spy = vi
      .spyOn(cameraService, 'start')
      .mockResolvedValue({ hls_url: TOKENIZED } as never)

    const first = renderHook(() => useLiveView(CAM))
    await waitFor(() => expect(first.result.current.hlsUrl).not.toBeNull())
    first.unmount()

    const second = renderHook(() => useLiveView(CAM))
    await waitFor(() => expect(second.result.current.hlsUrl).not.toBeNull())

    expect(spy).toHaveBeenCalledTimes(1)
  })

  it('refresh() força novo /stream/start (renovação de token expirado)', async () => {
    const spy = vi
      .spyOn(cameraService, 'start')
      .mockResolvedValue({ hls_url: TOKENIZED } as never)

    const { result } = renderHook(() => useLiveView(CAM))
    await waitFor(() => expect(result.current.hlsUrl).not.toBeNull())
    expect(spy).toHaveBeenCalledTimes(1)

    result.current.refresh()
    await waitFor(() => expect(spy).toHaveBeenCalledTimes(2))
  })

  // Regressão: o mesmo mecanismo do commit 2caeace ("live view parava
  // sozinho a cada ~90s") tem uma segunda porta de entrada — o token de
  // PLAYBACK (não o sinal epi:stream:*:active do backend) expira depois de
  // HLS_PLAYBACK_TOKEN_TTL (1h) e o manifesto passa a devolver 404 idêntico
  // ao de stream inexistente (PRs #255/#256). O contrato documentado no
  // topo de useLiveView.ts é: "o player pode chamar refresh() quando levar
  // 404 no meio da sessão". Não basta refresh() DISPARAR um novo
  // /stream/start (teste acima) — hlsUrl precisa de fato virar a URL NOVA
  // devolvida pelo backend, senão CameraPlayer segue preso no manifesto
  // velho e a tela não se recupera sozinha (o mesmo sintoma "só volta
  // reabrindo a tela", só que por outra causa).
  it('refresh() substitui hlsUrl pela URL nova (não fica preso na antiga)', async () => {
    const PRIMEIRA = TOKENIZED
    const SEGUNDA = `/api/cameras/${CAM}/stream/s/1899999999.novoToken/stream.m3u8`
    const spy = vi
      .spyOn(cameraService, 'start')
      .mockResolvedValueOnce({ hls_url: PRIMEIRA } as never)
      .mockResolvedValueOnce({ hls_url: SEGUNDA } as never)

    const { result } = renderHook(() => useLiveView(CAM))
    await waitFor(() => expect(result.current.hlsUrl).not.toBeNull())
    const urlAntesDoRefresh = result.current.hlsUrl
    expect(urlAntesDoRefresh).toContain('1799999999.abc123')

    result.current.refresh()

    await waitFor(() => expect(spy).toHaveBeenCalledTimes(2))
    await waitFor(() => expect(result.current.hlsUrl).toContain('1899999999.novoToken'))
    expect(result.current.hlsUrl).not.toBe(urlAntesDoRefresh)
  })

  it('não chama o backend quando desabilitado (câmera fora da viewport)', async () => {
    const spy = vi.spyOn(cameraService, 'start').mockResolvedValue({} as never)

    const { result } = renderHook(() => useLiveView(CAM, false))

    await new Promise((r) => setTimeout(r, 20))
    expect(spy).not.toHaveBeenCalled()
    expect(result.current.hlsUrl).toBeNull()
  })

  it('reporta erro quando o backend não devolve hls_url', async () => {
    vi.spyOn(cameraService, 'start').mockResolvedValue({} as never)

    const { result } = renderHook(() => useLiveView(CAM))

    await waitFor(() => expect(result.current.error).not.toBeNull())
    expect(result.current.hlsUrl).toBeNull()
  })
})

/**
 * task-teardown-abas + congelamento 04/08: o heartbeat de renovação proativa
 * pausa com a aba oculta (abas em segundo plano não têm espectador) e, desde a
 * correção do congelamento, é ANCORADO NO EXP REAL do token de playback (lido
 * da própria URL, formato /stream/s/<exp>.<sig>/), com retry curto em falha e
 * catch-up imediato ao voltar visível com a renovação atrasada.
 *
 * Sem a correção, três modos de morte (todos medidos em 04/08): falha
 * transitória só tentava de novo 55min depois (token já morto aos 60); voltar
 * de aba oculta reiniciava o intervalo inteiro; e o efeito re-executando por
 * toggle de visibilidade da célula também zerava o relógio sem re-mintar.
 */
describe('useLiveView — heartbeat de renovação (exp real do token + visibilidade)', () => {
  // Espelhos de useLiveView.ts (não exportados): margem de renovação, retry
  // curto e o TTL nominal usado como fallback/teto.
  const RENEW_MARGIN_MS = 5 * 60 * 1000
  const RENEW_RETRY_MS = 30_000
  const TTL_MS = 60 * 60 * 1000

  // Relógio fixo: tokens construídos relativos a AGORA para o fake timer.
  const NOW = new Date('2026-08-04T21:00:00Z').getTime()

  const urlWithExp = (expMs: number) =>
    `/api/cameras/${CAM}/stream/s/${Math.floor(expMs / 1000)}.sig/stream.m3u8`

  beforeEach(() => {
    __resetLiveViewCache()
    vi.restoreAllMocks()
    vi.useFakeTimers()
    vi.setSystemTime(NOW)
    Object.defineProperty(document, 'hidden', { configurable: true, get: () => false })
  })

  afterEach(() => {
    vi.clearAllTimers()
    vi.useRealTimers()
  })

  function setHidden(hidden: boolean) {
    Object.defineProperty(document, 'hidden', { configurable: true, get: () => hidden })
    document.dispatchEvent(new Event('visibilitychange'))
  }

  it('renova sozinho na margem antes do exp do token (visível o tempo todo)', async () => {
    const spy = vi
      .spyOn(cameraService, 'start')
      .mockImplementation(async () => ({ hls_url: urlWithExp(Date.now() + TTL_MS) }) as never)

    renderHook(() => useLiveView(CAM))
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0)
    })
    expect(spy).toHaveBeenCalledTimes(1) // mint inicial, exp = NOW+60min

    // Até a borda da margem (55min) nada acontece…
    await act(async () => {
      await vi.advanceTimersByTimeAsync(TTL_MS - RENEW_MARGIN_MS - 1000)
    })
    expect(spy).toHaveBeenCalledTimes(1)

    // …e logo depois dela o token é re-mintado, bem antes do exp.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000)
    })
    expect(spy).toHaveBeenCalledTimes(2)
  })

  it('falha transitória na renovação → retry curto, não espera outro ciclo inteiro (bug 04/08)', async () => {
    const spy = vi
      .spyOn(cameraService, 'start')
      .mockImplementationOnce(async () => ({ hls_url: urlWithExp(Date.now() + TTL_MS) }) as never)
      .mockRejectedValueOnce(new Error('API reiniciando (deploy)'))
      .mockImplementation(async () => ({ hls_url: urlWithExp(Date.now() + TTL_MS) }) as never)

    renderHook(() => useLiveView(CAM))
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0)
    })
    expect(spy).toHaveBeenCalledTimes(1)

    // Na borda de renovação a tentativa falha (deploy)…
    await act(async () => {
      await vi.advanceTimersByTimeAsync(TTL_MS - RENEW_MARGIN_MS + 2000)
    })
    expect(spy).toHaveBeenCalledTimes(2)

    // …e o retry vem em RENEW_RETRY_MS — com o token AINDA vivo (margem de
    // 5min), não 55min depois com o token morto.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(RENEW_RETRY_MS + 1000)
    })
    expect(spy).toHaveBeenCalledTimes(3)
  })

  it('não bate no backend (renovação) enquanto a aba está oculta; ao voltar visível com renovação atrasada, renova imediatamente', async () => {
    const spy = vi
      .spyOn(cameraService, 'start')
      .mockImplementation(async () => ({ hls_url: urlWithExp(Date.now() + TTL_MS) }) as never)

    renderHook(() => useLiveView(CAM))
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0)
    })
    expect(spy).toHaveBeenCalledTimes(1)

    act(() => setHidden(true))

    // A borda de renovação passa inteira com a aba oculta — nenhuma chamada.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(TTL_MS - RENEW_MARGIN_MS + 60_000)
    })
    expect(spy).toHaveBeenCalledTimes(1)

    act(() => setHidden(false))

    // Catch-up: a renovação estava atrasada → dispara já (não em +55min).
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000)
    })
    expect(spy).toHaveBeenCalledTimes(2)
  })

  it('desmontar enquanto oculto não deixa timer de renovação pendente', async () => {
    const spy = vi
      .spyOn(cameraService, 'start')
      .mockImplementation(async () => ({ hls_url: urlWithExp(Date.now() + TTL_MS) }) as never)

    const { unmount } = renderHook(() => useLiveView(CAM))
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0)
    })
    expect(spy).toHaveBeenCalledTimes(1)

    act(() => setHidden(true))
    unmount()

    await act(async () => {
      await vi.advanceTimersByTimeAsync(TTL_MS * 3)
    })
    expect(spy).toHaveBeenCalledTimes(1)
  })
})
