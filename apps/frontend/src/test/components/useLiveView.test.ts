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
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
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
