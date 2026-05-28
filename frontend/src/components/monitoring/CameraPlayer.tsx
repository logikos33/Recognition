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
  /**
   * Tipo de feed retornado pelo backend (/stream/info).
   * 'demo_video' → renderiza <video loop> com feedUrl (superadmin demo mode).
   * 'hls' → comportamento padrão com HLS.js.
   * Backend garante isolamento: clientes sempre recebem 'hls'.
   */
  feedType?: 'hls' | 'demo_video'
  feedUrl?: string  // URL do MP4 demo (usado somente quando feedType === 'demo_video')
}

export function CameraPlayer({
  cameraId: _cameraId,
  hlsUrl,
  width = 640,
  height = 360,
  feedType = 'hls',
  feedUrl,
}: CameraPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const hlsRef = useRef<Hls | null>(null)
  const retriesRef = useRef(0)
  const retryTimerRef = useRef<ReturnType<typeof setTimeout>>()
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [offline, setOffline] = useState(false)
  const [videoError, setVideoError] = useState(false)

  const destroyHls = useCallback(() => {
    if (retryTimerRef.current) clearTimeout(retryTimerRef.current)
    hlsRef.current?.destroy()
    hlsRef.current = null
  }, [])

  const startHls = useCallback(() => {
    // Modo demo: não inicializar HLS — o <video loop> cuida do playback
    if (feedType === 'demo_video') return

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
  }, [hlsUrl, destroyHls, feedType])

  useEffect(() => {
    retriesRef.current = 0
    if (feedType !== 'demo_video') startHls()
    return destroyHls
  }, [startHls, destroyHls, feedType])

  const handleRetry = useCallback(() => {
    retriesRef.current = 0
    startHls()
  }, [startHls])

  // Modo demo: <video> em loop — sem HLS
  if (feedType === 'demo_video' && feedUrl) {
    return (
      <div className={playerWrapper} style={{ width, height }}>
        {videoError ? (
          <div className={errorText}>Vídeo indisponível — verifique a configuração do vídeo demo</div>
        ) : (
          <video
            ref={videoRef}
            src={feedUrl}
            className={video}
            autoPlay
            loop
            muted
            playsInline
            onError={() => setVideoError(true)}
            onEnded={() => {
              if (videoRef.current) {
                videoRef.current.currentTime = 0
                videoRef.current.play().catch(() => {})
              }
            }}
          />
        )}
      </div>
    )
  }

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
