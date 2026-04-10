import Hls from 'hls.js'
import { useEffect, useRef, useState } from 'react'
import { playerWrapper, video, connectingText, errorText } from './CameraPlayer.css'

interface CameraPlayerProps {
  cameraId: string
  hlsUrl: string  // ex: /api/cameras/{id}/stream/stream.m3u8
  width?: number
  height?: number
}

export function CameraPlayer({ cameraId: _cameraId, hlsUrl, width = 640, height = 360 }: CameraPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const video = videoRef.current
    if (!video) return

    let hls: Hls | null = null

    if (Hls.isSupported()) {
      hls = new Hls({ lowLatencyMode: true, backBufferLength: 4 })
      hls.loadSource(hlsUrl)
      hls.attachMedia(video)
      hls.on(Hls.Events.MANIFEST_PARSED, () => {
        setLoading(false)
        video.play().catch(() => {})
      })
      hls.on(Hls.Events.ERROR, (_, data) => {
        if (data.fatal) setError('Erro no stream HLS')
      })
    } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
      video.src = hlsUrl
      video.addEventListener('loadedmetadata', () => {
        setLoading(false)
        video.play().catch(() => {})
      })
    } else {
      setError('HLS não suportado neste browser')
    }

    return () => { hls?.destroy() }
  }, [hlsUrl])

  return (
    <div className={playerWrapper} style={{ width, height }}>
      {loading && !error && (
        <div className={connectingText}>Conectando...</div>
      )}
      {error && (
        <div className={errorText}>{error}</div>
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
