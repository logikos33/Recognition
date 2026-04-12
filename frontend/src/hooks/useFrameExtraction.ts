/**
 * useFrameExtraction — browser-side frame capture via <video> + <canvas>.
 * No Celery, no FFmpeg. Seeks through the video, captures JPEGs, uploads each
 * frame to the backend one by one.
 */
import { useCallback } from 'react'
import { api } from '../services/api'

type ProgressCallback = (current: number, total: number) => void

export function useFrameExtraction() {
  const extract = useCallback(async (
    videoId: string,
    apiBase: string,
    token: string,
    onProgress?: ProgressCallback,
  ): Promise<number> => {
    // 1. Get presigned download URL for the raw video
    const urlRes = await api.get<{ status: string; data: { url: string } }>(`/v1/videos/${videoId}/download-url`)
    const rawUrl = (urlRes as any)?.data?.url ?? (urlRes as any)?.url
    if (!rawUrl) throw new Error('Nao foi possivel obter URL do video')

    // 2. Load video metadata (seeks only — does not buffer the whole file)
    const video = document.createElement('video')
    video.crossOrigin = 'anonymous'
    video.preload = 'metadata'
    video.src = rawUrl

    await new Promise<void>((resolve, reject) => {
      video.onloadedmetadata = () => resolve()
      video.onerror = () => reject(new Error(
        'Nao foi possivel carregar o video. Verifique sua conexao ou tente novamente. Se o problema persistir, delete e re-envie o arquivo.'
      ))
    })

    const duration = video.duration
    if (!duration || !isFinite(duration)) throw new Error('Duracao do video invalida')

    // 3. Build timestamp list (max 60 frames, one every ~2 s)
    const TARGET = Math.min(60, Math.max(10, Math.floor(duration / 2)))
    const interval = duration / TARGET
    const timestamps = Array.from({ length: TARGET }, (_, i) => i * interval)
    onProgress?.(0, timestamps.length)

    // 4. Canvas for JPEG capture at 640×360
    const canvas = document.createElement('canvas')
    canvas.width = 640
    canvas.height = 360
    const ctx = canvas.getContext('2d')!

    let captured = 0
    for (let i = 0; i < timestamps.length; i++) {
      const ts = timestamps[i]
      video.currentTime = ts
      await new Promise<void>((resolve) => {
        video.onseeked = () => resolve()
      })

      ctx.drawImage(video, 0, 0, 640, 360)
      const blob = await new Promise<Blob>((resolve, reject) => {
        canvas.toBlob((b) => b ? resolve(b) : reject(new Error('canvas.toBlob falhou')), 'image/jpeg', 0.85)
      })

      const form = new FormData()
      form.append('frame', blob, `frame_${String(i).padStart(4, '0')}.jpg`)
      form.append('frame_number', String(i))
      form.append('timestamp', String(ts))

      await new Promise<void>((resolve, reject) => {
        const xhr = new XMLHttpRequest()
        xhr.onload = () => (xhr.status < 300 ? resolve() : reject(new Error(`Frame ${i} falhou: ${xhr.status}`)))
        xhr.onerror = () => reject(new Error(`Erro de rede no frame ${i}`))
        xhr.open('POST', `${apiBase}/api/v1/videos/${videoId}/frames/upload`)
        xhr.setRequestHeader('Authorization', `Bearer ${token}`)
        xhr.send(form)
      })

      captured++
      onProgress?.(captured, timestamps.length)
    }

    // 5. Finalize — mark video as extracted
    await api.post(`/v1/videos/${videoId}/finalize-extraction`, { frame_count: captured })

    return captured
  }, [])

  return { extract }
}
