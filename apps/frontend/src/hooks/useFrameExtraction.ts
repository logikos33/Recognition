/**
 * useFrameExtraction — browser-side frame capture via <video> + <canvas>.
 * Downloads video through the API (avoids R2 CORS for GET), creates a blob URL,
 * then seeks and captures JPEGs frame by frame.
 */
import { useCallback } from 'react'
import { api } from '../services/api'

type ProgressCallback = (current: number, total: number) => void
type DownloadProgressCallback = (loaded: number, total: number) => void

export function useFrameExtraction() {
  const extract = useCallback(async (
    videoId: string,
    apiBase: string,
    token: string,
    onProgress?: ProgressCallback,
    onDownloadProgress?: DownloadProgressCallback,
  ): Promise<number> => {
    // 1. Download video through our API (avoids R2 CORS for GET)
    const rawUrl = await new Promise<string>((resolve, reject) => {
      const xhr = new XMLHttpRequest()
      xhr.responseType = 'blob'
      xhr.onprogress = (e) => {
        if (e.lengthComputable) onDownloadProgress?.(e.loaded, e.total)
      }
      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve(URL.createObjectURL(xhr.response as Blob))
        } else {
          reject(new Error(`Falha ao baixar video: ${xhr.status}`))
        }
      }
      xhr.onerror = () => reject(new Error('Erro de rede ao baixar video'))
      xhr.open('GET', `${apiBase}/api/v1/videos/${videoId}/blob`)
      xhr.setRequestHeader('Authorization', `Bearer ${token}`)
      xhr.send()
    })

    // 2. Load video metadata (blob URL — no CORS, instant seeking)
    const video = document.createElement('video')
    video.preload = 'metadata'
    video.src = rawUrl

    await new Promise<void>((resolve, reject) => {
      video.onloadedmetadata = () => resolve()
      video.onerror = () => reject(new Error(
        'Nao foi possivel carregar o video. O arquivo pode estar corrompido.'
      ))
    })

    const duration = video.duration
    if (!duration || !isFinite(duration)) throw new Error('Duracao do video invalida')

    // 3. Build timestamp list (max 60 frames, one every ~2 s)
    const TARGET = Math.min(60, Math.max(10, Math.floor(duration / 2)))
    const interval = duration / TARGET
    const timestamps = Array.from({ length: TARGET }, (_, i) => i * interval)
    onProgress?.(0, timestamps.length)

    // 4. Canvas for JPEG capture at 640x360
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

    // 5. Cleanup blob URL
    URL.revokeObjectURL(rawUrl)

    // 6. Finalize
    await api.post(`/v1/videos/${videoId}/finalize-extraction`, { frame_count: captured })

    return captured
  }, [])

  return { extract }
}
