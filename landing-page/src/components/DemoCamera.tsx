import { useState, useEffect, useRef, useCallback } from 'react'
import * as ort from 'onnxruntime-web'

const DEMO_DURATION_MS = 15 * 60 * 1000
const MODEL_PATH = '/models/yolov8n-demo.onnx'
const INPUT_SIZE = 640
const CONF_THRESHOLD = 0.40
const IOU_THRESHOLD = 0.45

// All COCO80 classes relevant for home/office environments, plus EPI classes
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
  // EPI classes (custom model)
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

type CountMap = Record<string, { count: number; color: string }>

function iou(a: Detection, b: Detection): number {
  const ix1 = Math.max(a.x1, b.x1), iy1 = Math.max(a.y1, b.y1)
  const ix2 = Math.min(a.x2, b.x2), iy2 = Math.min(a.y2, b.y2)
  const inter = Math.max(0, ix2 - ix1) * Math.max(0, iy2 - iy1)
  const aArea = (a.x2 - a.x1) * (a.y2 - a.y1)
  const bArea = (b.x2 - b.x1) * (b.y2 - b.y1)
  return inter / (aArea + bArea - inter + 1e-6)
}

function nms(dets: Detection[]): Detection[] {
  const sorted = [...dets].sort((a, b) => b.confidence - a.confidence)
  const kept: Detection[] = []
  for (const d of sorted) {
    if (!kept.some(k => k.classId === d.classId && iou(d, k) > IOU_THRESHOLD)) {
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
  W: number, H: number,
  numChannels: number, numPreds: number,
): Detection[] {
  const dets: Detection[] = []
  for (let i = 0; i < numPreds; i++) {
    let maxScore = 0, maxClass = 0
    for (let c = 4; c < numChannels; c++) {
      const s = output[c * numPreds + i]
      if (s > maxScore) { maxScore = s; maxClass = c - 4 }
    }
    if (maxScore < CONF_THRESHOLD) continue
    if (!(maxClass in CLASSES)) continue
    const cx = output[0 * numPreds + i] / INPUT_SIZE * W
    const cy = output[1 * numPreds + i] / INPUT_SIZE * H
    const w  = output[2 * numPreds + i] / INPUT_SIZE * W
    const h  = output[3 * numPreds + i] / INPUT_SIZE * H
    dets.push({
      classId: maxClass, className: CLASSES[maxClass].name,
      confidence: maxScore, color: CLASSES[maxClass].color,
      x1: cx - w / 2, y1: cy - h / 2, x2: cx + w / 2, y2: cy + h / 2,
    })
  }
  return nms(dets)
}

function drawDetections(ctx: CanvasRenderingContext2D, dets: Detection[]): void {
  ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height)
  for (const d of dets) {
    ctx.strokeStyle = d.color
    ctx.lineWidth = 3
    ctx.strokeRect(d.x1, d.y1, d.x2 - d.x1, d.y2 - d.y1)
    const label = `${d.className} ${(d.confidence * 100).toFixed(0)}%`
    ctx.font = 'bold 14px sans-serif'
    const tw = ctx.measureText(label).width
    ctx.fillStyle = d.color
    ctx.fillRect(d.x1, d.y1 - 22, tw + 10, 22)
    ctx.fillStyle = '#fff'
    ctx.fillText(label, d.x1 + 5, d.y1 - 6)
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
  const tmpCanvasRef = useRef<HTMLCanvasElement | null>(null)
  const tmpCtxRef    = useRef<CanvasRenderingContext2D | null>(null)
  const bufferRef    = useRef<Float32Array | null>(null)

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

  const stopDemo = useCallback(() => {
    runningRef.current = false
    cancelAnimationFrame(rafRef.current)
    setPhase('done')
    if (videoRef.current?.srcObject) {
      (videoRef.current.srcObject as MediaStream).getTracks().forEach(t => t.stop())
      videoRef.current.srcObject = null
    }
    sessionRef.current?.release?.()
    sessionRef.current = null
  }, [])

  // Draw loop: runs at native display rate via rAF — smooth video + overlay
  const drawLoop = useCallback(() => {
    if (!runningRef.current) return
    const canvas = canvasRef.current
    const video  = videoRef.current
    if (canvas && video) {
      const vw = video.videoWidth || 640
      const vh = video.videoHeight || 480
      if (canvas.width !== vw)  canvas.width  = vw
      if (canvas.height !== vh) canvas.height = vh
      const ctx = canvas.getContext('2d')!
      drawDetections(ctx, lastDetsRef.current)
    }
    rafRef.current = requestAnimationFrame(drawLoop)
  }, [])

  // Inference loop: runs as fast as the model allows, no artificial throttle
  const inferenceLoop = useCallback(async () => {
    while (runningRef.current) {
      const video = videoRef.current
      const sess  = sessionRef.current
      if (!video || !sess) break

      const elapsed = Date.now() - startRef.current
      if (elapsed >= DEMO_DURATION_MS) { stopDemo(); break }

      const vw = video.videoWidth || 640
      const vh = video.videoHeight || 480

      try {
        const { tmpCtx, buf } = getBuffers()
        tmpCtx.drawImage(video, 0, 0, INPUT_SIZE, INPUT_SIZE)
        preprocessInto(tmpCtx, buf)

        const tensor = new ort.Tensor('float32', buf, [1, 3, INPUT_SIZE, INPUT_SIZE])
        const results = await sess.run({ images: tensor })
        const outTensor = results[Object.keys(results)[0]]
        const dims = outTensor.dims as number[]

        const dets = parseOutput(
          outTensor.data as Float32Array,
          vw, vh, dims[1], dims[2],
        )

        lastDetsRef.current = dets

        // count once per inference pass per unique class (not per instance)
        const seenClasses = new Set<string>()
        for (const d of dets) {
          if (!seenClasses.has(d.className)) {
            seenClasses.add(d.className)
            const entry = countsRef.current[d.className]
            countsRef.current[d.className] = {
              count: (entry?.count ?? 0) + 1,
              color: d.color,
            }
          }
        }

        inferFrames.current++
        const now = performance.now()
        if (now - lastFpsTime.current >= 1000) {
          const dt = (now - lastFpsTime.current) / 1000
          setFps(Math.round(inferFrames.current / dt))
          setTimeLeft(DEMO_DURATION_MS - elapsed)
          setCounts({ ...countsRef.current })
          inferFrames.current = 0
          lastFpsTime.current = now
        }
      } catch (err) {
        console.warn('Demo inference error:', err)
        await new Promise(r => setTimeout(r, 200))
      }

      // yield to the event loop so rAF and UI updates can run between inferences
      await new Promise(r => setTimeout(r, 0))
    }
  }, [stopDemo, getBuffers])

  const startDemo = async () => {
    setPhase('loading')
    setError(null)
    countsRef.current = {}
    setCounts({})
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment', width: { ideal: 1280 }, height: { ideal: 720 } },
      })
      if (videoRef.current) {
        videoRef.current.srcObject = stream
        await videoRef.current.play()
      }

      if (!sessionRef.current) {
        sessionRef.current = await ort.InferenceSession.create(MODEL_PATH, {
          executionProviders: ['webgl', 'wasm'],
          graphOptimizationLevel: 'all',
        })
      }

      startRef.current = Date.now()
      lastFpsTime.current = performance.now()
      inferFrames.current = 0
      runningRef.current = true
      setPhase('running')
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Erro desconhecido'
      if (msg.includes('Permission') || msg.includes('NotAllowed')) {
        setError('Permissão de câmera negada. Libere o acesso e tente novamente.')
      } else if (msg.includes('model') || msg.includes('fetch')) {
        setError('Modelo IA não encontrado. Use a versão exportada para demos.')
      } else {
        setError(msg)
      }
      setPhase('idle')
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
      sessionRef.current?.release?.()
    }
  }, [])

  const fmtTime = (ms: number) => {
    const s = Math.floor(ms / 1000)
    return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
  }

  const sortedCounts = Object.entries(counts).sort((a, b) => b[1].count - a[1].count)

  return (
    <div className="bg-gray-100 rounded-xl sm:rounded-2xl p-2 sm:p-4 w-full">

      <div className="relative bg-black rounded-lg sm:rounded-xl overflow-hidden aspect-video mb-3" style={{ minHeight: '220px' }}>
        {/* Video always visible — smooth native rendering */}
        <video
          ref={videoRef}
          className="absolute inset-0 w-full h-full object-cover"
          playsInline muted
        />
        {/* Canvas overlay — transparent, draws only bounding boxes */}
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
                <p className="text-gray-400 text-sm">Sessão finalizada</p>
              </>
            ) : (
              <button
                onClick={startDemo}
                className="flex items-center gap-2 px-6 py-3 bg-orange-500 text-white rounded-xl hover:bg-orange-600 transition text-lg font-semibold shadow-lg"
              >
                📷 Iniciar Demo
              </button>
            )}
          </div>
        )}

        {phase === 'loading' && (
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/70 gap-3">
            <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-orange-400" />
            <p className="text-white text-sm">Carregando modelo IA...</p>
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
              className="absolute bottom-2 right-2 bg-red-600 text-white px-2 py-1 rounded-lg hover:bg-red-700 transition text-xs font-bold"
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
          <p className="text-xs font-medium text-gray-500 mb-2">Objetos reconhecidos</p>
          <div className="grid grid-cols-2 gap-1.5">
            {sortedCounts.map(([name, { count, color }]) => (
              <div key={name} className="flex items-center justify-between bg-white rounded-lg px-3 py-1.5 border border-gray-100 shadow-sm">
                <div className="flex items-center gap-2 min-w-0">
                  <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: color }} />
                  <span className="text-xs font-medium text-gray-700 capitalize truncate">{name}</span>
                </div>
                <span className="text-xs font-bold text-gray-900 tabular-nums ml-2">{count}</span>
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
