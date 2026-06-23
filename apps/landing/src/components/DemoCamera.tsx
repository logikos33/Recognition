import { useState, useEffect, useRef, useCallback } from 'react'
import * as ort from 'onnxruntime-web'

const DEMO_DURATION_MS = 15 * 60 * 1000
const MODEL_PATH = '/models/yolov8n-demo.onnx'
const INPUT_SIZE = 640

// Constantes ajustáveis do demo. Tunadas para reduzir alucinação e instabilidade.
const DEMO_CONFIG = {
  SCORE_THRESHOLD: 0.55,
  IOU_THRESHOLD: 0.45,
  MIN_BOX_AREA_RATIO: 0.012,
  FRAMES_TO_CONFIRM: 3,
  INFERENCE_INTERVAL_MS: 150,
  // Whitelist: classes que o demo aceita exibir.
  // Reduz radicalmente os falsos positivos do YOLOv8n COCO em cenas comuns.
  ALLOWED_CLASS_IDS: new Set<number>([
    0,   // pessoa
    39,  // garrafa
    41,  // copo
    62,  // monitor/TV
    63,  // notebook
    64,  // mouse
    65,  // controle
    66,  // teclado
    67,  // celular
    73,  // livro
    74,  // relógio
    76,  // tesoura
  ]),
}

const CLASSES: Record<number, { name: string; color: string }> = {
  0:  { name: 'pessoa',        color: '#3b82f6' },
  1:  { name: 'bicicleta',     color: '#6366f1' },
  2:  { name: 'carro',         color: '#8b5cf6' },
  3:  { name: 'moto',          color: '#8b5cf6' },
  5:  { name: 'ônibus',        color: '#8b5cf6' },
  7:  { name: 'caminhão',      color: '#8b5cf6' },
  14: { name: 'pássaro',       color: '#14b8a6' },
  15: { name: 'gato',          color: '#f59e0b' },
  16: { name: 'cachorro',      color: '#f59e0b' },
  24: { name: 'mochila',       color: '#8b5cf6' },
  25: { name: 'guarda-chuva',  color: '#6366f1' },
  26: { name: 'bolsa',         color: '#8b5cf6' },
  27: { name: 'gravata',       color: '#6366f1' },
  28: { name: 'mala',          color: '#8b5cf6' },
  39: { name: 'garrafa',       color: '#f59e0b' },
  40: { name: 'taça',          color: '#ec4899' },
  41: { name: 'copo',          color: '#f59e0b' },
  42: { name: 'garfo',         color: '#6366f1' },
  43: { name: 'faca',          color: '#ef4444' },
  44: { name: 'colher',        color: '#6366f1' },
  45: { name: 'tigela',        color: '#f59e0b' },
  46: { name: 'banana',        color: '#eab308' },
  47: { name: 'maçã',          color: '#22c55e' },
  49: { name: 'laranja',       color: '#f97316' },
  55: { name: 'bolo',          color: '#ec4899' },
  56: { name: 'cadeira',       color: '#6366f1' },
  57: { name: 'sofá',          color: '#6366f1' },
  58: { name: 'planta',        color: '#22c55e' },
  59: { name: 'cama',          color: '#8b5cf6' },
  60: { name: 'mesa',          color: '#6366f1' },
  62: { name: 'monitor/TV',    color: '#ec4899' },
  63: { name: 'notebook',      color: '#ec4899' },
  64: { name: 'mouse',         color: '#ec4899' },
  65: { name: 'controle',      color: '#ec4899' },
  66: { name: 'teclado',       color: '#ec4899' },
  67: { name: 'celular',       color: '#ec4899' },
  68: { name: 'micro-ondas',   color: '#6366f1' },
  69: { name: 'forno',         color: '#6366f1' },
  71: { name: 'pia',           color: '#06b6d4' },
  72: { name: 'geladeira',     color: '#06b6d4' },
  73: { name: 'livro',         color: '#14b8a6' },
  74: { name: 'relógio',       color: '#14b8a6' },
  75: { name: 'vaso',          color: '#22c55e' },
  76: { name: 'tesoura',       color: '#ef4444' },
  77: { name: 'pelúcia',       color: '#ec4899' },
  79: { name: 'escova dentes', color: '#06b6d4' },
  80: { name: 'capacete',      color: '#22c55e' },
  81: { name: 'sem capacete',  color: '#ef4444' },
  82: { name: 'colete',        color: '#22c55e' },
  83: { name: 'sem colete',    color: '#ef4444' },
  84: { name: 'óculos',        color: '#06b6d4' },
  85: { name: 'sem óculos',    color: '#f97316' },
}

interface Detection {
  classId: number
  className: string
  confidence: number
  x1: number; y1: number; x2: number; y2: number
  color: string
}

interface Letterbox { scale: number; padX: number; padY: number }

type CountMap = Record<string, { count: number; color: string }>

function iou(a: Detection, b: Detection): number {
  const ix1 = Math.max(a.x1, b.x1), iy1 = Math.max(a.y1, b.y1)
  const ix2 = Math.min(a.x2, b.x2), iy2 = Math.min(a.y2, b.y2)
  const inter = Math.max(0, ix2 - ix1) * Math.max(0, iy2 - iy1)
  const aArea = (a.x2 - a.x1) * (a.y2 - a.y1)
  const bArea = (b.x2 - b.x1) * (b.y2 - b.y1)
  return inter / (aArea + bArea - inter + 1e-6)
}

// NMS global (sem filtro por classe). Duas caixas sobrepostas, ainda que de
// classes diferentes, são consideradas o mesmo objeto e a de menor score cai.
function nms(dets: Detection[]): Detection[] {
  const sorted = [...dets].sort((a, b) => b.confidence - a.confidence)
  const kept: Detection[] = []
  for (const d of sorted) {
    if (!kept.some(k => iou(d, k) > DEMO_CONFIG.IOU_THRESHOLD)) {
      kept.push(d)
    }
  }
  return kept
}

function preprocessInto(ctx: CanvasRenderingContext2D, buf: Float32Array): void {
  const imgData = ctx.getImageData(0, 0, INPUT_SIZE, INPUT_SIZE).data
  const N = INPUT_SIZE * INPUT_SIZE
  for (let i = 0; i < N; i++) {
    buf[i]         = imgData[i * 4]     / 255
    buf[i + N]     = imgData[i * 4 + 1] / 255
    buf[i + N * 2] = imgData[i * 4 + 2] / 255
  }
}

function parseOutput(
  output: Float32Array,
  vw: number, vh: number,
  numChannels: number, numPreds: number,
  lb: Letterbox,
): Detection[] {
  const dets: Detection[] = []
  const minArea = vw * vh * DEMO_CONFIG.MIN_BOX_AREA_RATIO
  for (let i = 0; i < numPreds; i++) {
    let maxScore = 0, maxClass = 0
    for (let c = 4; c < numChannels; c++) {
      const s = output[c * numPreds + i]
      if (s > maxScore) { maxScore = s; maxClass = c - 4 }
    }
    if (maxScore < DEMO_CONFIG.SCORE_THRESHOLD) continue
    if (!DEMO_CONFIG.ALLOWED_CLASS_IDS.has(maxClass)) continue
    if (!(maxClass in CLASSES)) continue

    const cx = output[0 * numPreds + i]
    const cy = output[1 * numPreds + i]
    const w  = output[2 * numPreds + i]
    const h  = output[3 * numPreds + i]

    // Reverte letterbox: coords vêm em espaço 640x640 com padding centralizado.
    const x1 = Math.max(0, Math.min(vw, (cx - w / 2 - lb.padX) / lb.scale))
    const y1 = Math.max(0, Math.min(vh, (cy - h / 2 - lb.padY) / lb.scale))
    const x2 = Math.max(0, Math.min(vw, (cx + w / 2 - lb.padX) / lb.scale))
    const y2 = Math.max(0, Math.min(vh, (cy + h / 2 - lb.padY) / lb.scale))

    if ((x2 - x1) * (y2 - y1) < minArea) continue

    dets.push({
      classId: maxClass, className: CLASSES[maxClass].name,
      confidence: maxScore, color: CLASSES[maxClass].color,
      x1, y1, x2, y2,
    })
  }
  return nms(dets)
}

// Mapeia coords do espaço do vídeo nativo (vw x vh) para o retângulo VISÍVEL
// do canvas (que usa object-fit: contain), evitando o desalinhamento causado
// por crop do object-fit: cover ou por rotação portrait/landscape no celular.
interface DrawTransform { scale: number; offsetX: number; offsetY: number }

function fitTransform(vw: number, vh: number, cw: number, ch: number): DrawTransform {
  const scale = Math.min(cw / vw, ch / vh)
  const offsetX = (cw - vw * scale) / 2
  const offsetY = (ch - vh * scale) / 2
  return { scale, offsetX, offsetY }
}

function drawDetections(
  ctx: CanvasRenderingContext2D,
  dets: Detection[],
  cw: number, ch: number,
  t: DrawTransform,
): void {
  ctx.clearRect(0, 0, cw, ch)
  for (const d of dets) {
    const x = t.offsetX + d.x1 * t.scale
    const y = t.offsetY + d.y1 * t.scale
    const w = (d.x2 - d.x1) * t.scale
    const h = (d.y2 - d.y1) * t.scale

    ctx.strokeStyle = d.color
    ctx.lineWidth = 3
    ctx.strokeRect(x, y, w, h)

    const label = `${d.className} ${(d.confidence * 100).toFixed(0)}%`
    ctx.font = 'bold 13px sans-serif'
    const tw = ctx.measureText(label).width
    ctx.fillStyle = d.color
    ctx.fillRect(x, y - 20, tw + 10, 20)
    ctx.fillStyle = '#fff'
    ctx.fillText(label, x + 5, y - 5)
  }
}

export default function DemoCamera() {
  const videoRef    = useRef<HTMLVideoElement>(null)
  const canvasRef   = useRef<HTMLCanvasElement>(null)
  const sessionRef  = useRef<ort.InferenceSession | null>(null)
  const startRef    = useRef<number>(0)
  const runningRef  = useRef(false)
  const rafRef      = useRef<number>(0)

  // Reusable inference buffers
  const tmpCanvasRef  = useRef<HTMLCanvasElement | null>(null)
  const tmpCtxRef     = useRef<CanvasRenderingContext2D | null>(null)
  const bufferRef     = useRef<Float32Array | null>(null)
  const letterboxRef  = useRef<Letterbox>({ scale: 1, padX: 0, padY: 0 })

  // Estabilidade temporal: rastreia detecções pendentes por chave espacial.
  // Só passa para a UI quando aparece em FRAMES_TO_CONFIRM frames consecutivos.
  const pendingRef = useRef<Map<string, { hits: number; det: Detection }>>(new Map())

  // Shared state between draw loop and inference loop
  const lastDetsRef = useRef<Detection[]>([])
  const countsRef   = useRef<CountMap>({})
  const lastFpsTime = useRef(0)
  const inferFrames = useRef(0)

  const [phase, setPhase]     = useState<'idle' | 'loading' | 'running' | 'done'>('idle')
  const [error, setError]     = useState<string | null>(null)
  const [fps, setFps]         = useState(0)
  const [timeLeft, setTimeLeft] = useState(DEMO_DURATION_MS)
  const [counts, setCounts]   = useState<CountMap>({})
  const [loadingPct, setLoadingPct] = useState<number>(0)

  const getBuffers = useCallback(() => {
    if (!tmpCanvasRef.current) {
      const c = document.createElement('canvas')
      c.width = c.height = INPUT_SIZE
      tmpCanvasRef.current = c
      tmpCtxRef.current = c.getContext('2d')!
    }
    if (!bufferRef.current) {
      bufferRef.current = new Float32Array(3 * INPUT_SIZE * INPUT_SIZE)
    }
    return { tmpCtx: tmpCtxRef.current!, buf: bufferRef.current }
  }, [])

  const stopTracks = useCallback(() => {
    const stream = videoRef.current?.srcObject as MediaStream | null
    stream?.getTracks().forEach(t => t.stop())
    if (videoRef.current) videoRef.current.srcObject = null
  }, [])

  const stopDemo = useCallback(() => {
    runningRef.current = false
    cancelAnimationFrame(rafRef.current)
    setPhase('done')
    stopTracks()
    sessionRef.current?.release?.()
    sessionRef.current = null
    // Reset visual: contadores zeram quando o usuário para o demo
    countsRef.current = {}
    setCounts({})
    pendingRef.current.clear()
    lastDetsRef.current = []
  }, [stopTracks])

  // Draw loop: runs at native display rate via rAF — smooth video + overlay
  const drawLoop = useCallback(() => {
    if (!runningRef.current) return
    const canvas = canvasRef.current
    const video  = videoRef.current
    if (canvas && video) {
      const vw = video.videoWidth || 640
      const vh = video.videoHeight || 480
      const cw = canvas.clientWidth || vw
      const ch = canvas.clientHeight || vh
      const dpr = window.devicePixelRatio || 1
      const internalW = Math.round(cw * dpr)
      const internalH = Math.round(ch * dpr)
      if (canvas.width !== internalW)  canvas.width  = internalW
      if (canvas.height !== internalH) canvas.height = internalH
      const ctx = canvas.getContext('2d')!
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      const t = fitTransform(vw, vh, cw, ch)
      drawDetections(ctx, lastDetsRef.current, cw, ch, t)
    }
    rafRef.current = requestAnimationFrame(drawLoop)
  }, [])

  // Inference loop: throttled to INFERENCE_INTERVAL_MS (cap ~6.6 FPS).
  // Suficiente para o demo e evita queimar bateria/aquecer celular.
  const inferenceLoop = useCallback(async () => {
    while (runningRef.current) {
      const tInferStart = performance.now()
      const video = videoRef.current
      const sess  = sessionRef.current
      if (!video || !sess) break

      const elapsed = Date.now() - startRef.current
      if (elapsed >= DEMO_DURATION_MS) { stopDemo(); break }

      const vw = video.videoWidth || 640
      const vh = video.videoHeight || 480

      try {
        const { tmpCtx, buf } = getBuffers()

        // Letterbox: preserva aspect ratio. YOLOv8 foi treinado com isso.
        const scale = Math.min(INPUT_SIZE / vw, INPUT_SIZE / vh)
        const newW = Math.round(vw * scale)
        const newH = Math.round(vh * scale)
        const padX = Math.floor((INPUT_SIZE - newW) / 2)
        const padY = Math.floor((INPUT_SIZE - newH) / 2)

        tmpCtx.fillStyle = '#727272'
        tmpCtx.fillRect(0, 0, INPUT_SIZE, INPUT_SIZE)
        tmpCtx.drawImage(video, padX, padY, newW, newH)
        letterboxRef.current = { scale, padX, padY }

        preprocessInto(tmpCtx, buf)

        const tensor = new ort.Tensor('float32', buf, [1, 3, INPUT_SIZE, INPUT_SIZE])
        const results = await sess.run({ images: tensor })
        const outTensor = results[Object.keys(results)[0]]
        const dims = outTensor.dims as number[]

        const rawDets = parseOutput(
          outTensor.data as Float32Array,
          vw, vh, dims[1], dims[2],
          letterboxRef.current,
        )

        // Estabilidade temporal: cada detecção ganha uma chave baseada em
        // (classe, posição em grid de 64px). Só passa para UI/contagem após
        // FRAMES_TO_CONFIRM frames consecutivos vendo a mesma chave.
        const seen = new Set<string>()
        const stable: Detection[] = []
        for (const d of rawDets) {
          const cx = (d.x1 + d.x2) / 2
          const cy = (d.y1 + d.y2) / 2
          const key = `${d.classId}:${Math.floor(cx / 64)}:${Math.floor(cy / 64)}`
          seen.add(key)
          const prev = pendingRef.current.get(key)
          const hits = (prev?.hits ?? 0) + 1
          pendingRef.current.set(key, { hits, det: d })
          if (hits >= DEMO_CONFIG.FRAMES_TO_CONFIRM) stable.push(d)
        }
        // Decai chaves não vistas neste frame; remove ao zerar.
        for (const [key, val] of pendingRef.current) {
          if (!seen.has(key)) {
            const hits = val.hits - 1
            if (hits <= 0) pendingRef.current.delete(key)
            else pendingRef.current.set(key, { ...val, hits })
          }
        }

        lastDetsRef.current = stable

        // Contagem live (modo: objetos em cena agora). Reset por frame.
        const frameCounts: CountMap = {}
        for (const d of stable) {
          const entry = frameCounts[d.className]
          frameCounts[d.className] = {
            count: (entry?.count ?? 0) + 1,
            color: d.color,
          }
        }
        // Só re-renderiza se o map mudou (evita re-render desnecessário a cada inferência)
        const prev = countsRef.current
        const prevKeys = Object.keys(prev)
        const nextKeys = Object.keys(frameCounts)
        let changed = prevKeys.length !== nextKeys.length
        if (!changed) {
          for (const k of nextKeys) {
            if (!prev[k] || prev[k].count !== frameCounts[k].count) { changed = true; break }
          }
        }
        if (changed) {
          countsRef.current = frameCounts
          setCounts(frameCounts)
        }

        inferFrames.current++
        const now = performance.now()
        if (now - lastFpsTime.current >= 1000) {
          const dt = (now - lastFpsTime.current) / 1000
          setFps(Math.round(inferFrames.current / dt))
          setTimeLeft(DEMO_DURATION_MS - elapsed)
          inferFrames.current = 0
          lastFpsTime.current = now
        }
      } catch (err) {
        console.warn('Demo inference error:', err)
        await new Promise(r => setTimeout(r, 200))
      }

      const dt = performance.now() - tInferStart
      const wait = Math.max(0, DEMO_CONFIG.INFERENCE_INTERVAL_MS - dt)
      await new Promise(r => setTimeout(r, wait))
    }
  }, [stopDemo, getBuffers])

  const loadModelWithProgress = useCallback(async (): Promise<ort.InferenceSession> => {
    const resp = await fetch(MODEL_PATH)
    if (!resp.ok || !resp.body) throw new Error('model fetch failed')
    const total = Number(resp.headers.get('content-length')) || 0
    const reader = resp.body.getReader()
    const chunks: Uint8Array[] = []
    let received = 0
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      chunks.push(value)
      received += value.length
      if (total > 0) setLoadingPct(Math.round((received / total) * 100))
    }
    const total_ = chunks.reduce((s, c) => s + c.length, 0)
    const merged = new Uint8Array(total_)
    let off = 0
    for (const c of chunks) { merged.set(c, off); off += c.length }
    setLoadingPct(100)
    return ort.InferenceSession.create(merged.buffer, {
      executionProviders: ['webgl', 'wasm'],
      graphOptimizationLevel: 'all',
    })
  }, [])

  const startDemo = async () => {
    setPhase('loading')
    setError(null)
    setLoadingPct(0)
    countsRef.current = {}
    setCounts({})
    pendingRef.current.clear()
    try {
      // facingMode SOFT (ideal) com fallback — evita OverconstrainedError em iOS/webview
      let stream: MediaStream
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: {
            facingMode: { ideal: 'environment' },
            width:  { ideal: 1280 },
            height: { ideal: 720 },
          },
        })
      } catch {
        stream = await navigator.mediaDevices.getUserMedia({ video: true })
      }

      if (videoRef.current) {
        // Atributo iOS legado: garante render inline (sem fullscreen)
        videoRef.current.setAttribute('webkit-playsinline', 'true')
        videoRef.current.setAttribute('playsinline', 'true')
        videoRef.current.srcObject = stream
        try { await videoRef.current.play() } catch { /* play rejection ignorada — autoplay attr cobre */ }
      }

      if (!sessionRef.current) {
        sessionRef.current = await loadModelWithProgress()
      }

      startRef.current = Date.now()
      lastFpsTime.current = performance.now()
      inferFrames.current = 0
      runningRef.current = true
      setPhase('running')
    } catch (err: unknown) {
      const name = err instanceof Error ? err.name : ''
      const msg = err instanceof Error ? err.message : 'Erro desconhecido'
      if (name === 'NotAllowedError' || msg.includes('Permission') || msg.includes('NotAllowed')) {
        setError('Permissão de câmera negada. Libere o acesso nas configurações e toque em "Iniciar Demo" novamente.')
      } else if (name === 'NotFoundError' || name === 'OverconstrainedError') {
        setError('Nenhuma câmera disponível neste dispositivo.')
      } else if (name === 'NotReadableError') {
        setError('A câmera está em uso por outro aplicativo. Feche-o e tente novamente.')
      } else if (msg.includes('model') || msg.includes('fetch')) {
        setError('Falha ao baixar o modelo IA. Verifique sua conexão e tente novamente.')
      } else {
        setError(msg)
      }
      setPhase('idle')
      stopTracks()
    }
  }

  useEffect(() => {
    if (phase === 'running') {
      rafRef.current = requestAnimationFrame(drawLoop)
      inferenceLoop()
    }
    return () => { cancelAnimationFrame(rafRef.current) }
  }, [phase, drawLoop, inferenceLoop])

  useEffect(() => {
    return () => {
      runningRef.current = false
      cancelAnimationFrame(rafRef.current)
      stopTracks()
      sessionRef.current?.release?.()
    }
  }, [stopTracks])

  const fmtTime = (ms: number) => {
    const s = Math.floor(ms / 1000)
    return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
  }

  const sortedCounts = Object.entries(counts).sort((a, b) => b[1].count - a[1].count)
  const totalObjects = sortedCounts.reduce((sum, [, v]) => sum + v.count, 0)

  return (
    <div className="bg-gray-100 rounded-xl sm:rounded-2xl p-2 sm:p-4 w-full">

      <div className="relative w-full max-w-full mx-auto bg-black rounded-lg sm:rounded-xl overflow-hidden aspect-video mb-3">
        {/* object-fit: contain garante que o vídeo NÃO seja cropado.
            O canvas overlay desenha no mesmo retângulo visível. */}
        <video
          ref={videoRef}
          className="absolute inset-0 w-full h-full"
          style={{ objectFit: 'contain', background: '#000' }}
          playsInline muted autoPlay
        />
        {/* Canvas overlay — transparente, desenha apenas bounding boxes */}
        <canvas
          ref={canvasRef}
          className="absolute inset-0 w-full h-full"
          style={{ pointerEvents: 'none', display: phase === 'running' ? 'block' : 'none' }}
        />

        {(phase === 'idle' || phase === 'done') && (
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/60 gap-4">
            {phase === 'done' ? (
              <>
                <div className="text-4xl">🎉</div>
                <p className="text-white font-semibold">Demo encerrada</p>
                <button
                  onClick={startDemo}
                  className="flex items-center gap-2 px-5 py-2.5 bg-orange-500 text-white rounded-xl hover:bg-orange-600 transition text-sm font-semibold shadow-lg"
                >
                  📷 Reiniciar
                </button>
              </>
            ) : (
              <button
                onClick={startDemo}
                className="flex items-center gap-2 px-6 py-3 bg-orange-500 text-white rounded-xl hover:bg-orange-600 transition text-lg font-semibold shadow-lg"
                style={{ minHeight: '48px' }}
              >
                📷 Iniciar Demo
              </button>
            )}
          </div>
        )}

        {phase === 'loading' && (
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/70 gap-3 px-4">
            <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-orange-400" />
            <p className="text-white text-sm">
              {loadingPct > 0 ? `Baixando modelo IA... ${loadingPct}%` : 'Iniciando câmera...'}
            </p>
            {loadingPct > 0 && loadingPct < 100 && (
              <div className="w-full max-w-xs bg-gray-700 rounded-full h-1.5 overflow-hidden">
                <div className="bg-orange-400 h-full transition-all" style={{ width: `${loadingPct}%` }} />
              </div>
            )}
          </div>
        )}

        {phase === 'running' && (
          <>
            <div className="absolute top-2 left-2 bg-black/70 text-white px-2 py-1 rounded-lg text-xs sm:text-sm flex items-center gap-1.5">
              <span>⏱</span>{fmtTime(timeLeft)}
            </div>
            <div className="absolute top-2 right-2 bg-black/70 text-white px-2 py-1 rounded-lg text-xs">
              {fps} FPS
            </div>
            <button
              onClick={stopDemo}
              className="absolute bottom-2 right-2 bg-red-600 text-white px-3 py-1.5 rounded-lg hover:bg-red-700 transition text-xs font-bold"
              style={{ minHeight: '36px' }}
            >
              ⏹ Stop
            </button>
          </>
        )}
      </div>

      {error && (
        <div className="flex items-start gap-2 bg-red-50 text-red-700 rounded-lg p-3 mb-3 text-sm">
          <span>⚠️</span><span>{error}</span>
        </div>
      )}

      {sortedCounts.length > 0 && (
        <div className="mb-3">
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs font-medium text-gray-500">Objetos em cena</p>
            <p className="text-xs font-bold text-orange-500">{totalObjects} {totalObjects === 1 ? 'objeto' : 'objetos'}</p>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {sortedCounts.map(([name, { count, color }]) => (
              <div
                key={name}
                className="flex items-center gap-1.5 bg-white rounded-lg px-2.5 py-1 border border-gray-200 shadow-sm"
              >
                <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: color }} />
                <span className="text-xs font-medium text-gray-700 capitalize">{name}</span>
                <span className="text-xs font-bold text-orange-500">×{count}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <p className="text-xs text-gray-400 text-center">
        Todo processamento ocorre no seu dispositivo. Nenhuma imagem é enviada para servidores.
      </p>
    </div>
  )
}
