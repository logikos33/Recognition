import { useEffect, useRef, useState } from 'react'
import Hls from 'hls.js'

export function CameraPlayer({ cameraId, autoPlay = true, style }) {
  const videoRef = useRef(null)
  const hlsRef = useRef(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!cameraId || !videoRef.current) return
    const streamUrl = `/streams/${cameraId}/stream.m3u8`
    setError(null)
    setLoading(true)

    if (Hls.isSupported()) {
      const hls = new Hls({
        enableWorker: true, lowLatencyMode: true,
        backBufferLength: 0, maxBufferLength: 10,
        liveSyncDurationCount: 2, liveMaxLatencyDurationCount: 5,
      })
      hls.loadSource(streamUrl)
      hls.attachMedia(videoRef.current)
      hls.on(Hls.Events.MANIFEST_PARSED, () => setLoading(false))
      hls.on(Hls.Events.ERROR, (_, data) => {
        if (data.fatal) {
          switch (data.type) {
            case Hls.ErrorTypes.NETWORK_ERROR: hls.startLoad(); break
            case Hls.ErrorTypes.MEDIA_ERROR: hls.recoverMediaError(); break
            default: setError('Stream indisponível'); break
          }
        }
      })
      hlsRef.current = hls
    } else if (videoRef.current.canPlayType('application/vnd.apple.mpegurl')) {
      videoRef.current.src = streamUrl
      setLoading(false)
    } else {
      setError('Browser não suporta streaming HLS')
    }

    return () => { if (hlsRef.current) { hlsRef.current.destroy(); hlsRef.current = null } }
  }, [cameraId])

  const containerStyle = {
    position: 'relative', background: '#111',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    ...style
  }

  if (error) return (
    <div style={{ ...containerStyle, color: '#ef4444', fontSize: 13 }}>
      {error}
    </div>
  )

  return (
    <div style={containerStyle}>
      {loading && (
        <div style={{ position: 'absolute', inset: 0, background: '#111',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: '#9ca3af', fontSize: 13, zIndex: 1 }}>
          Conectando...
        </div>
      )}
      <video ref={videoRef} autoPlay={autoPlay} muted playsInline
        style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
    </div>
  )
}
