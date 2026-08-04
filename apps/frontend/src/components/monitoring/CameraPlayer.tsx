import Hls from 'hls.js'
import { useEffect, useRef, useState, useCallback } from 'react'
import {
  playerWrapper,
  video,
  connectingText,
  errorText,
  offlineOverlay,
  recoveryFailedOverlay,
  retryBtn,
} from './CameraPlayer.css'
import { refreshLiveViewUrl } from '../../hooks/useLiveView'

// task-068: stream considerado travado se nenhum fragmento novo chegar por STALL_TIMEOUT_MS.
// Backend detecta stall via #EXT-X-MEDIA-SEQUENCE parado em ~12s; aqui damos margem de rede.
const STALL_TIMEOUT_MS = 14000

// task-068: backoff de reconexão (1s → 2s → 5s) em vez de retry fixo ou desistência após N tentativas.
// O ciclo nunca "desiste" sozinho — só o usuário via botão "Reconectar" reseta manualmente,
// mas o backoff evita martelar o backend com 1 tentativa/s indefinidamente.
// Usado para STALL (sem progresso) e para erros fatais que não são de rede (MEDIA_ERROR/OTHER_ERROR).
const BACKOFF_DELAYS_MS = [1000, 2000, 5000]

// bug liveview-recovery: erro FATAL de rede do hls.js (manifesto 404 — token de playback
// expirado, ou rajada de 425 nos .ts do edge escalando pra fatal) não se resolve recarregando
// a MESMA URL — o backend precisa re-assinar o token via /stream/start. Ciclo dedicado:
// 1ª tentativa imediata, depois cresce exponencialmente até um teto de 30s. O tamanho do
// array também é o limite de tentativas contínuas — ao esgotar, desiste e mostra erro visível
// em vez de martelar o backend pra sempre em silêncio.
const NETWORK_RECOVERY_DELAYS_MS = [0, 2000, 4000, 8000, 16000, 30000]

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
  cameraId,
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
  // URL efetivamente carregada no hls.js — começa igual à prop, mas diverge dela
  // quando a recuperação de erro de rede busca uma URL nova (a prop `hlsUrl` do
  // componente pai não é atualizada; ver useLiveView.refreshLiveViewUrl).
  const currentUrlRef = useRef(hlsUrl)
  // Ciclo de recuperação por URL nova (erro fatal de rede — ver NETWORK_RECOVERY_DELAYS_MS).
  const networkRecoveryAttemptRef = useRef(0)
  const networkRecoveryTimerRef = useRef<TimerRef>(undefined)
  // task-teardown-abas: guardas contra corrida/obsolescência no teardown de aba oculta.
  // mountedRef: evita aplicar resultado de reaquisição assíncrona depois do unmount.
  // startEpochRef: incrementado a cada (re)início real do hls.js — uma reaquisição em
  // voo (refreshLiveViewUrl) checa se ainda é a mais recente antes de aplicar o
  // resultado, senão foi superada (aba oculta de novo, retry manual, outro toggle).
  const mountedRef = useRef(true)
  const startEpochRef = useRef(0)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [offline, setOffline] = useState(false)
  // Esgotou NETWORK_RECOVERY_DELAYS_MS sem recuperar — desiste do retry automático e
  // mostra erro visível. Só sai desse estado com startHls() (ex.: botão "Tentar novamente").
  const [recoveryFailed, setRecoveryFailed] = useState(false)
  const [videoError, setVideoError] = useState(false)

  // Arma o watchdog de stall: se nenhum progresso real (FRAG_LOADED/MANIFEST_PARSED)
  // acontecer dentro de STALL_TIMEOUT_MS, dispara triggerReconnect.
  function armStallTimer() {
    clearTimer(stallTimerRef)
    stallTimerRef.current = setTimeout(() => {
      triggerReconnect()
    }, STALL_TIMEOUT_MS)
  }

  // Ciclo de reconexão com backoff para STALL (sem progresso) e erros fatais que não são de
  // rede (MEDIA_ERROR/OTHER_ERROR): stopLoad -> aguarda delay atual -> startLoad() -> re-arma o
  // watchdog. Se o próximo watchdog disparar de novo (sem progresso), escala o backoff e repete.
  // Nunca desiste sozinho — só para de fato quando FRAG_LOADED chega (handleProgress) ou o
  // componente desmonta. Erro fatal de REDE não passa por aqui — vai para
  // startNetworkRecovery(), que pede URL nova e tem limite de tentativas (ver abaixo).
  function triggerReconnect() {
    setOffline(true)
    clearTimer(stallTimerRef)
    hlsRef.current?.stopLoad()
    clearTimer(backoffTimerRef)
    const delay = BACKOFF_DELAYS_MS[Math.min(backoffIndexRef.current, BACKOFF_DELAYS_MS.length - 1)]
    backoffTimerRef.current = setTimeout(() => {
      backoffIndexRef.current = Math.min(backoffIndexRef.current + 1, BACKOFF_DELAYS_MS.length - 1)
      hlsRef.current?.startLoad()
      armStallTimer()
    }, delay)
  }

  // Ciclo de recuperação dedicado a erro FATAL de rede do hls.js (manifesto 404 — token
  // expirado — ou rajada de 425 nos .ts escalando pra fatal). Martelar startLoad()/loadSource()
  // com a MESMA URL não resolve: o token só é renovado via novo /stream/start. Cada tentativa
  // busca uma URL fresca (refreshLiveViewUrl) antes de recarregar. 1ª tentativa imediata, depois
  // cresce exponencialmente até 30s; ao esgotar NETWORK_RECOVERY_DELAYS_MS, desiste e mostra
  // erro visível em vez de martelar o backend pra sempre em silêncio.
  function startNetworkRecovery() {
    setOffline(true)
    setRecoveryFailed(false)
    clearTimer(stallTimerRef)
    hlsRef.current?.stopLoad()
    scheduleNetworkRecoveryAttempt()
  }

  function scheduleNetworkRecoveryAttempt() {
    clearTimer(networkRecoveryTimerRef)
    const attempt = networkRecoveryAttemptRef.current
    if (attempt >= NETWORK_RECOVERY_DELAYS_MS.length) {
      // Esgotou as tentativas contínuas — desiste e avisa em vez de martelar em silêncio.
      setOffline(false)
      setRecoveryFailed(true)
      return
    }
    const delay = NETWORK_RECOVERY_DELAYS_MS[attempt]
    networkRecoveryTimerRef.current = setTimeout(() => {
      networkRecoveryAttemptRef.current += 1
      void runNetworkRecoveryAttempt()
    }, delay)
  }

  async function runNetworkRecoveryAttempt() {
    let freshUrl: string | null = null
    try {
      freshUrl = await refreshLiveViewUrl(cameraId)
    } catch {
      freshUrl = null
    }
    // Desmontou, ou um startHls() (ex.: retry manual) trocou de instância nesse meio-tempo.
    if (!hlsRef.current) return
    currentUrlRef.current = freshUrl ?? currentUrlRef.current
    hlsRef.current.loadSource(currentUrlRef.current)
    armStallTimer()
  }

  // Progresso real confirmado: reseta backoff (stall e recuperação de rede), sai dos estados
  // offline/recoveryFailed e re-arma o watchdog pra continuar vigiando o próximo eventual stall.
  function handleProgress() {
    clearTimer(backoffTimerRef)
    backoffIndexRef.current = 0
    clearTimer(networkRecoveryTimerRef)
    networkRecoveryAttemptRef.current = 0
    setRecoveryFailed(false)
    setOffline(false)
    armStallTimer()
  }

  const destroyHls = useCallback(() => {
    clearTimer(stallTimerRef)
    clearTimer(backoffTimerRef)
    clearTimer(networkRecoveryTimerRef)
    hlsRef.current?.destroy()
    hlsRef.current = null
  }, [])

  const startHlsWithUrl = useCallback((url: string) => {
    // Modo demo: não inicializar HLS — o <video loop> cuida do playback
    if (feedType === 'demo_video') return

    const vid = videoRef.current
    if (!vid) return

    // Todo (re)início real invalida qualquer reaquisição assíncrona ainda em voo
    // (ver reacquireAfterHidden) — o resultado dela, quando chegar, vai descobrir
    // que foi superada e desistir de aplicar uma URL desatualizada.
    startEpochRef.current += 1
    destroyHls()
    setError(null)
    setOffline(false)
    setRecoveryFailed(false)
    setLoading(true)
    backoffIndexRef.current = 0
    networkRecoveryAttemptRef.current = 0
    currentUrlRef.current = url

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
      hls.loadSource(currentUrlRef.current)
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

        // bug liveview-recovery: erro fatal de REDE (manifesto 404 por token expirado, ou
        // rajada de 425 nos .ts escalando pra fatal) não se resolve recarregando a mesma URL
        // — precisa de URL nova (token novo). Ciclo dedicado com backoff + limite de tentativas.
        if (data.type === Hls.ErrorTypes.NETWORK_ERROR) {
          startNetworkRecovery()
          return
        }

        if (data.type === Hls.ErrorTypes.MEDIA_ERROR) {
          hls.recoverMediaError()
        }
        triggerReconnect()
      })

      // Watchdog ativo desde o início — cobre o caso do manifest nunca chegar a parsear.
      armStallTimer()
    } else if (vid.canPlayType('application/vnd.apple.mpegurl')) {
      vid.src = currentUrlRef.current
      vid.addEventListener('loadedmetadata', () => {
        setLoading(false)
        vid.play().catch(() => {})
      })
    } else {
      setError('HLS nao suportado neste browser')
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cameraId, destroyHls, feedType])

  const startHls = useCallback(() => {
    startHlsWithUrl(hlsUrl)
  }, [startHlsWithUrl, hlsUrl])

  // task-teardown-abas: encerramento DE VERDADE da sessão de live view desta aba —
  // não só pausar o carregamento (era o que o antigo handler de visibilitychange
  // fazia via hls.stopLoad()/startLoad()). Destrói a instância hls.js (pára todo
  // fetch de segmento/playlist — o que consome egress) e solta o <video> nativo
  // (fallback Safari sem hls.js, que usa vid.src direto em vez de MediaSource).
  //
  // Não existe endpoint de "release" por espectador no backend — só
  // POST /stream/start (abre) e /stream/stop (mata o FFmpeg pra TODOS os
  // espectadores da câmera, inclusive outras abas/usuários olhando a mesma
  // câmera). Chamar /stream/stop aqui derrubaria quem mais estiver vendo.
  // O sinal correto de "sem espectador" já existe no servidor:
  // `epi:stream:{camera_id}:active` (TTL HLS_VIEWER_TTL, default 90s,
  // stream_handlers.py) só é renovado quando ALGUÉM de fato busca um arquivo
  // via serve_hls. Parar de buscar — o que este teardown garante — é
  // suficiente para a chave expirar sozinha e o edge parar de transmitir
  // (GET /edge/live-view/wanted) ou o watchdog local matar o FFmpeg idle.
  const teardownSession = useCallback(() => {
    destroyHls()
    const vid = videoRef.current
    if (vid) {
      vid.pause()
      vid.removeAttribute('src')
      vid.load()
    }
  }, [destroyHls])

  useEffect(() => {
    mountedRef.current = true
    backoffIndexRef.current = 0
    if (feedType !== 'demo_video') startHls()

    // Reaquisição ao voltar visível: MESMO caminho do #280 (erro fatal de rede) —
    // refreshLiveViewUrl força um novo /stream/start e devolve uma URL tokenizada
    // fresca, nunca recarrega a URL antiga (pode ter token expirado depois de
    // horas em segundo plano). Guardas: aba pode ter ficado oculta de novo, o
    // componente pode ter desmontado, ou outro (re)início pode ter acontecido
    // (retry manual) enquanto o /stream/start estava em voo — startEpochRef
    // detecta essa última corrida.
    async function reacquireAfterHidden() {
      const myEpoch = startEpochRef.current
      try {
        const freshUrl = await refreshLiveViewUrl(cameraId)
        if (!mountedRef.current || document.hidden) return
        if (startEpochRef.current !== myEpoch) return
        startHlsWithUrl(freshUrl)
      } catch {
        if (!mountedRef.current || document.hidden) return
        if (startEpochRef.current !== myEpoch) return
        // Melhor esforço: cai pra URL atual (pode já estar fresca via prop) — se
        // ainda estiver morta, o ciclo de recuperação de erro de rede (#280)
        // assume dali.
        startHls()
      }
    }

    const handleVisibilityChange = () => {
      if (feedType === 'demo_video') return
      if (document.hidden) {
        teardownSession()
        setLoading(true)
        setOffline(false)
        setRecoveryFailed(false)
        setError(null)
      } else {
        void reacquireAfterHidden()
      }
    }

    if (feedType !== 'demo_video') {
      document.addEventListener('visibilitychange', handleVisibilityChange)
    }

    return () => {
      mountedRef.current = false
      document.removeEventListener('visibilitychange', handleVisibilityChange)
      teardownSession()
    }
  }, [startHls, startHlsWithUrl, teardownSession, feedType, cameraId])

  const handleRetry = useCallback(() => {
    backoffIndexRef.current = 0
    startHls()
  }, [startHls])

  // bug liveview-contexto-visivel: o botão "Tentar novamente" do estado
  // recoveryFailed reiniciava com a MESMA `hlsUrl` da prop (via handleRetry ->
  // startHls) — se o motivo do esgotamento foi token expirado, o retry manual
  // falhava de novo na hora, voltando pro mesmo estado sem o usuário entender
  // por quê. Busca uma URL fresca primeiro (mesmo caminho de
  // runNetworkRecoveryAttempt), com fallback pra `hlsUrl` só se o
  // /stream/start falhar.
  const handleManualNetworkRetry = useCallback(() => {
    backoffIndexRef.current = 0
    networkRecoveryAttemptRef.current = 0
    clearTimer(networkRecoveryTimerRef)
    void (async () => {
      let freshUrl: string | null = null
      try {
        freshUrl = await refreshLiveViewUrl(cameraId)
      } catch {
        freshUrl = null
      }
      startHlsWithUrl(freshUrl ?? hlsUrl)
    })()
  }, [cameraId, hlsUrl, startHlsWithUrl])

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
      {loading && !error && !offline && !recoveryFailed && (
        <div className={connectingText}>Conectando...</div>
      )}
      {error && (
        <div className={errorText}>{error}</div>
      )}
      {offline && !recoveryFailed && (
        <div className={offlineOverlay}>
          <span>Câmera offline — reconectando...</span>
          <button className={retryBtn} onClick={handleRetry}>Reconectar</button>
        </div>
      )}
      {recoveryFailed && (
        <div className={recoveryFailedOverlay}>
          <span>Câmera indisponível — não foi possível reconectar</span>
          <button className={retryBtn} onClick={handleManualNetworkRetry}>Tentar novamente</button>
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
