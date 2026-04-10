import Hls from 'hls.js'
import { useEffect, useRef, useState, useCallback } from 'react'
import { playerWrapper, video, connectingText, errorText, offlineOverlay, retryBtn } from './CameraPlayer.css'

const MAX_FATAL_RETRIES = 3
const RETRY_DELAY_MS = 3000

interface CameraPlayerProps {
  cameraId: string
  hlsUrl: string  // ex: /api/cameras/{id}/stream/stream.m3u8
  width?: number
  height?: number
}

export function CameraPlayer({ cameraId: _cameraId, hlsUrl, width = 640, height = 360 }: CameraPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const hlsRef = useRef<Hls | null>(null)
  const retriesRef = useRef(0)
  const retryTimerRef = useRef<ReturnType<typeof setTimeout>>()
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [offline, setOffline] = useState(false)

  const destroyHls = useCallback(() => {
    if (retryTimerRef.current) clearTimeout(retryTimerRef.current)
    hlsRef.current?.destroy()
    hlsRef.current = null
  }, [])

  const startHls = useCallback(() => {
    const vid = videoRef.current
    if (!vid) return

    destroyHls()
    setError(null)
    setOffline(false)
    setLoading(true)

    if (Hls.isSupported()) {
      const hls = new Hls({
        lowLatencyMode: true,
        backBufferLength: 4,
        manifestLoadingMaxRetry: 2,
        manifestLoadingRetryDelay: 2000,
        levelLoadingMaxRetry: 2,
        fragLoadingMaxRetry: 2,
      })
      hlsRef.current = hls
      hls.loadSource(hlsUrl)
      hls.attachMedia(vid)

      hls.on(Hls.Events.MANIFEST_PARSED, () => {
        setLoading(false)
        retriesRef.current = 0
        vid.play().catch(() => {})
      })

      hls.on(Hls.Events.ERROR, (_, data) => {
        if (!data.fatal) return
        retriesRef.current += 1
        if (retriesRef.current >= MAX_FATAL_RETRIES) {
          hls.destroy()
          hlsRef.current = null
          setLoading(false)
          setOffline(true)
        } else {
          // Auto-retry with delay
          retryTimerRef.current = setTimeout(() => {
            hls.destroy()
            hlsRef.current = null
            startHls()
          }, RETRY_DELAY_MS)
        }
      })
    } else if (vid.canPlayType('application/vnd.apple.mpegurl')) {
      vid.src = hlsUrl
      vid.addEventListener('loadedmetadata', () => {
        setLoading(false)
        vid.play().catch(() => {})
      })
    } else {
      setError('HLS nao suportado neste browser')
    }
  }, [hlsUrl, destroyHls])

  useEffect(() => {
    retriesRef.current = 0
    startHls()
    return destroyHls
  }, [startHls, destroyHls])

  const handleRetry = useCallback(() => {
    retriesRef.current = 0
    startHls()
  }, [startHls])

  return (
    <div className={playerWrapper} style={{ width, height }}>
      {loading && !error && !offline && (
        <div className={connectingText}>Conectando...</div>
      )}
      {error && (
        <div className={errorText}>{error}</div>
      )}
      {offline && (
        <div className={offlineOverlay}>
          <span>Camera offline</span>
          <button className={retryBtn} onClick={handleRetry}>Reconectar</button>
        </div>
      )}
      <video
        ref={videoRef}
        className={video}
        muted
        playsInline
        autoPlay
      />
    </div>
  )
}
