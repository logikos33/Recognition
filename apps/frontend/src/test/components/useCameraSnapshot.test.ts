/**
 * useCameraSnapshot — miniatura de triagem (Bloco A, CameraTriagePage).
 *
 * Cobre: inativo não dispara rede; refresh+poll até 'ready'; poll continua
 * enquanto 'pending'; teto de tentativas -> timedOut; refresh() cancela o
 * loop de poll anterior; erro de rede vira status 'failed'.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, renderHook, waitFor } from '@testing-library/react'
import { useCameraSnapshot } from '../../hooks/useCameraSnapshot'
import { cameraService } from '../../services/cameraService'

const CAM = 'cam-1'

describe('useCameraSnapshot', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('inativo (active=false) nunca chama refresh/getSnapshot', () => {
    const refreshSpy = vi.spyOn(cameraService, 'refreshSnapshot')
    const getSpy = vi.spyOn(cameraService, 'getSnapshot')

    const { result } = renderHook(() => useCameraSnapshot(CAM, false))

    expect(result.current.status).toBe('idle')
    expect(refreshSpy).not.toHaveBeenCalled()
    expect(getSpy).not.toHaveBeenCalled()
  })

  it('ativo: dispara refresh seguido de UM get quando já vem ready', async () => {
    const refreshSpy = vi.spyOn(cameraService, 'refreshSnapshot').mockResolvedValue({
      status: 'ready', queued: false, reason: 'fresh',
    })
    const getSpy = vi.spyOn(cameraService, 'getSnapshot').mockResolvedValue({
      status: 'ready', url: 'https://fake/x.jpg', captured_at: '2026-01-01T00:00:00Z',
      error_reason: null,
    })

    const { result } = renderHook(() => useCameraSnapshot(CAM, true))

    await waitFor(() => expect(result.current.status).toBe('ready'))

    expect(refreshSpy).toHaveBeenCalledWith(CAM)
    expect(getSpy).toHaveBeenCalledTimes(1)
    expect(result.current.url).toBe('https://fake/x.jpg')
    expect(result.current.loading).toBe(false)
  })

  it('continua fazendo poll enquanto pending, até resolver ready', async () => {
    vi.useFakeTimers()
    vi.spyOn(cameraService, 'refreshSnapshot').mockResolvedValue({
      status: 'pending', queued: true,
    })
    const getSpy = vi.spyOn(cameraService, 'getSnapshot')
      .mockResolvedValueOnce({ status: 'pending', url: null, captured_at: null, error_reason: null })
      .mockResolvedValueOnce({ status: 'pending', url: null, captured_at: null, error_reason: null })
      .mockResolvedValueOnce({
        status: 'ready', url: 'https://fake/late.jpg',
        captured_at: '2026-01-01T00:00:00Z', error_reason: null,
      })

    const { result } = renderHook(() => useCameraSnapshot(CAM, true))

    await vi.waitFor(() => expect(getSpy).toHaveBeenCalledTimes(1))
    expect(result.current.status).toBe('pending')

    await act(async () => {
      await vi.advanceTimersByTimeAsync(4000)
    })
    await vi.waitFor(() => expect(getSpy).toHaveBeenCalledTimes(2))

    await act(async () => {
      await vi.advanceTimersByTimeAsync(4000)
    })
    await vi.waitFor(() => expect(getSpy).toHaveBeenCalledTimes(3))
    await vi.waitFor(() => expect(result.current.status).toBe('ready'))
    expect(result.current.url).toBe('https://fake/late.jpg')
  })

  it('desiste após o teto de tentativas e marca timedOut', async () => {
    vi.useFakeTimers()
    vi.spyOn(cameraService, 'refreshSnapshot').mockResolvedValue({
      status: 'pending', queued: true,
    })
    vi.spyOn(cameraService, 'getSnapshot').mockResolvedValue({
      status: 'pending', url: null, captured_at: null, error_reason: null,
    })

    const { result } = renderHook(() => useCameraSnapshot(CAM, true))

    // 15 tentativas (MAX_POLL_ATTEMPTS) x 4000ms — avança tudo de uma vez.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(15 * 4000)
    })

    expect(result.current.timedOut).toBe(true)
    expect(result.current.loading).toBe(false)
  })

  it('erro de rede no poll vira status failed, sem lançar', async () => {
    vi.spyOn(cameraService, 'refreshSnapshot').mockResolvedValue({
      status: 'pending', queued: true,
    })
    vi.spyOn(cameraService, 'getSnapshot').mockRejectedValue(new Error('offline'))

    const { result } = renderHook(() => useCameraSnapshot(CAM, true))

    await waitFor(() => expect(result.current.status).toBe('failed'))
    expect(result.current.loading).toBe(false)
  })

  it('refresh() manual dispara uma nova rodada de captura', async () => {
    const refreshSpy = vi.spyOn(cameraService, 'refreshSnapshot').mockResolvedValue({
      status: 'ready', queued: false, reason: 'fresh',
    })
    vi.spyOn(cameraService, 'getSnapshot').mockResolvedValue({
      status: 'ready', url: 'https://fake/x.jpg', captured_at: '2026-01-01T00:00:00Z',
      error_reason: null,
    })

    const { result } = renderHook(() => useCameraSnapshot(CAM, true))
    await waitFor(() => expect(result.current.status).toBe('ready'))
    expect(refreshSpy).toHaveBeenCalledTimes(1)

    act(() => {
      result.current.refresh()
    })

    await waitFor(() => expect(refreshSpy).toHaveBeenCalledTimes(2))
  })

  it('trocar de câmera (cameraId muda) reinicia a busca para a nova câmera', async () => {
    const getSpy = vi.spyOn(cameraService, 'getSnapshot').mockImplementation((id) =>
      Promise.resolve({
        status: 'ready', url: `https://fake/${id}.jpg`,
        captured_at: '2026-01-01T00:00:00Z', error_reason: null,
      }),
    )
    vi.spyOn(cameraService, 'refreshSnapshot').mockResolvedValue({
      status: 'ready', queued: false, reason: 'fresh',
    })

    const { result, rerender } = renderHook(
      ({ cameraId }: { cameraId: string }) => useCameraSnapshot(cameraId, true),
      { initialProps: { cameraId: 'cam-a' } },
    )
    await waitFor(() => expect(result.current.url).toBe('https://fake/cam-a.jpg'))

    rerender({ cameraId: 'cam-b' })
    await waitFor(() => expect(result.current.url).toBe('https://fake/cam-b.jpg'))

    expect(getSpy).toHaveBeenCalledWith('cam-a')
    expect(getSpy).toHaveBeenCalledWith('cam-b')
  })
})
