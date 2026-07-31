import Hls from 'hls.js'
import { useEffect, useRef, useState, useCallback } from 'react'
import { playerWrapper, video, connectingText, errorText, offlineOverlay, retryBtn } from './CameraPlayer.css'

// task-068: stream considerado travado se nenhum fragmento novo chegar por STALL_TIMEOUT_MS.
// Backend detecta stall via #EXT-X-MEDIA-SEQUENCE parado em ~12s; aqui damos margem de rede.
const STALL_TIMEOUT_MS = 14000

// task-068: backoff de reconexão (1s → 2s → 5s) em vez de retry fixo ou desistência após N tentativas.
// O ciclo nunca "desiste" sozinho — só o usuário via botão "Reconectar" reseta manualmente,
// mas o backoff evita martelar o backend com 1 tentativa/s indefinidamente.
const BACKOFF_DELAYS_MS = [1000, 2000, 5000]

type TimerRef = ReturnType<typeof setTimeout> | undefined

function clearTimer(ref: { current: TimerRef }) {
  if (ref.current) {
    clearTimeout(ref.current)
    ref.current = undefined
  }
}

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
  const backoffIndexRef = useRef(0)
  const stallTimerRef = useRef<TimerRef>(undefined)
  const backoffTimerRef = useRef<TimerRef>(undefined)
  // Marca que o último erro fatal foi no manifest — muda como triggerReconnect retoma.
  const manifestFailedRef = useRef(false)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [offline, setOffline] = useState(false)
  const [videoError, setVideoError] = useState(false)

  // Arma o watchdog de stall: se nenhum progresso real (FRAG_LOADED/MANIFEST_PARSED)
  // acontecer dentro de STALL_TIMEOUT_MS, dispara triggerReconnect.
  function armStallTimer() {
    clearTimer(stallTimerRef)
    stallTimerRef.current = setTimeout(() => {
      triggerReconnect()
    }, STALL_TIMEOUT_MS)
  }

  // Ciclo de reconexão com backoff: stopLoad -> aguarda delay atual -> retoma -> re-arma o
  // watchdog. Se o próximo watchdog disparar de novo (sem progresso), escala o backoff e repete.
  // Nunca desiste sozinho — só para de fato quando FRAG_LOADED chega (handleProgress) ou o
  // componente desmonta.
  //
  // Como retomar depende do que quebrou:
  //   - stall / erro depois do manifest parseado -> startLoad() basta;
  //   - erro FATAL no PRÓPRIO manifest -> startLoad() é no-op. O hls.js não tem level
  //     carregado, então não reemite request nenhum e o player fica mudo pra sempre,
  //     preso no overlay "Câmera offline". Nesse caso é obrigatório loadSource() de novo.
  //     Cenário real: câmera no edge (LV-3) responde 425 "Stream initializing" enquanto o
  //     FFmpeg do box sobe (~10s a frio) — e 4xx o hls.js trata como fatal não-retentável.
  function triggerReconnect() {
    setOffline(true)
    clearTimer(stallTimerRef)
    hlsRef.current?.stopLoad()
    clearTimer(backoffTimerRef)
    const delay = BACKOFF_DELAYS_MS[Math.min(backoffIndexRef.current, BACKOFF_DELAYS_MS.length - 1)]
    backoffTimerRef.current = setTimeout(() => {
      backoffIndexRef.current = Math.min(backoffIndexRef.current + 1, BACKOFF_DELAYS_MS.length - 1)
      if (manifestFailedRef.current) {
        manifestFailedRef.current = false
        hlsRef.current?.loadSource(hlsUrl)
      } else {
        hlsRef.current?.startLoad()
      }
      armStallTimer()
    }, delay)
  }

  // Progresso real confirmado: reseta backoff, sai do estado offline e re-arma o watchdog
  // pra continuar vigiando o próximo eventual stall.
  function handleProgress() {
    clearTimer(backoffTimerRef)
    backoffIndexRef.current = 0
    setOffline(false)
    armStallTimer()
  }

  const destroyHls = useCallback(() => {
    clearTimer(stallTimerRef)
    clearTimer(backoffTimerRef)
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
    backoffIndexRef.current = 0
    manifestFailedRef.current = false

    if (Hls.isSupported()) {
      const hls = new Hls({
        lowLatencyMode: true,
        backBufferLength: 4,
        // task-061: stay 2 segments (~2s) behind live edge; speed up gently to recover drift
        liveSyncDurationCount: 2,
        liveMaxLatencyDurationCount: 5,
        maxLiveSyncPlaybackRate: 1.05,
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
        handleProgress()
        vid.play().catch(() => {})
      })

      // task-068: FRAG_LOADED é o sinal de progresso real do stream (não só "cliente pediu").
      hls.on(Hls.Events.FRAG_LOADED, () => {
        handleProgress()
      })

      hls.on(Hls.Events.ERROR, (_, data) => {
        if (!data.fatal) return
        if (data.type === Hls.ErrorTypes.MEDIA_ERROR) {
          hls.recoverMediaError()
        }
        // Erro no manifest deixa a instância sem level carregado: só loadSource() reergue.
        if (
          data.type === Hls.ErrorTypes.NETWORK_ERROR &&
          (data.details === Hls.ErrorDetails.MANIFEST_LOAD_ERROR ||
            data.details === Hls.ErrorDetails.MANIFEST_LOAD_TIMEOUT ||
            data.details === Hls.ErrorDetails.MANIFEST_PARSING_ERROR)
        ) {
          manifestFailedRef.current = true
        }
        triggerReconnect()
      })

      // Watchdog ativo desde o início — cobre o caso do manifest nunca chegar a parsear.
      armStallTimer()
    } else if (vid.canPlayType('application/vnd.apple.mpegurl')) {
      vid.src = hlsUrl
      vid.addEventListener('loadedmetadata', () => {
        setLoading(false)
        vid.play().catch(() => {})
      })
    } else {
      setError('HLS nao suportado neste browser')
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hlsUrl, destroyHls, feedType])

  useEffect(() => {
    backoffIndexRef.current = 0
    if (feedType !== 'demo_video') startHls()

    // task-068: pausar rede com a aba oculta (Page Visibility API) — não destrói a instância,
    // só para de bater no backend enquanto ninguém está olhando. Retoma do zero ao voltar.
    const handleVisibilityChange = () => {
      const hls = hlsRef.current
      if (!hls) return
      if (document.hidden) {
        hls.stopLoad()
        clearTimer(stallTimerRef)
        clearTimer(backoffTimerRef)
      } else {
        backoffIndexRef.current = 0
        hls.startLoad()
        armStallTimer()
      }
    }

    if (feedType !== 'demo_video') {
      document.addEventListener('visibilitychange', handleVisibilityChange)
    }

    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange)
      destroyHls()
    }
  }, [startHls, destroyHls, feedType])

  const handleRetry = useCallback(() => {
    backoffIndexRef.current = 0
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
          <span>Câmera offline — reconectando...</span>
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
