/**
 * Testes de `refreshLiveViewUrl` — exportação nova usada por `CameraPlayer` pra
 * recuperar de erro fatal de rede do hls.js (bug liveview-recovery) sem depender
 * de um componente pai re-renderizar com uma `hlsUrl` nova.
 *
 * Não duplica os testes de `useLiveView.test.ts` (hook em si, TTL/dedupe/refresh
 * via React) — cobre só o contrato da função standalone.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { refreshLiveViewUrl, __resetLiveViewCache } from '../../hooks/useLiveView'
import { cameraService } from '../../services/cameraService'

const CAM = 'cam-refresh-standalone'

describe('refreshLiveViewUrl', () => {
  beforeEach(() => {
    __resetLiveViewCache()
    vi.restoreAllMocks()
  })

  it('bate no backend (POST /stream/start) e devolve a hls_url tokenizada', async () => {
    const spy = vi
      .spyOn(cameraService, 'start')
      .mockResolvedValue({ hls_url: '/api/cameras/x/stream/s/tok1/stream.m3u8' } as never)

    const url = await refreshLiveViewUrl(CAM)

    expect(spy).toHaveBeenCalledWith(CAM)
    expect(url).toBe('/api/cameras/x/stream/s/tok1/stream.m3u8')
  })

  it('cada chamada força um novo /stream/start — não reaproveita cache fresco', async () => {
    const spy = vi
      .spyOn(cameraService, 'start')
      .mockResolvedValueOnce({ hls_url: '/tok1' } as never)
      .mockResolvedValueOnce({ hls_url: '/tok2' } as never)

    const first = await refreshLiveViewUrl(CAM)
    const second = await refreshLiveViewUrl(CAM)

    expect(spy).toHaveBeenCalledTimes(2)
    expect(first).toBe('/tok1')
    expect(second).toBe('/tok2')
    expect(second).not.toBe(first)
  })

  it('propaga o erro quando o backend não devolve hls_url', async () => {
    vi.spyOn(cameraService, 'start').mockResolvedValue({} as never)

    await expect(refreshLiveViewUrl(CAM)).rejects.toThrow('Backend não devolveu hls_url')
  })
})
