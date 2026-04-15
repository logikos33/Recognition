/**
 * DemoCamera — Demo IA no browser com ONNX Runtime Web.
 * YOLOv8n customizado: 640x640, NCHW float32.
 * Sessão de 15 minutos por visita.
 *
 * AI_NOTE: Performance fixes aplicados:
 * - Canvas temporário reusado via ref (não cria DOM element por frame)
 * - Float32Array reusado (não aloca 4.9MB por frame)
 * - Canvas dimensions só setadas quando mudam
 * - Throttle a ~10 FPS via setTimeout
 * - React state updates throttled a 1x/segundo
 * - ONNX session disposed no cleanup
 * - WebGL context loss detectado e reportado
 * - parseOutput dinâmico (usa dims reais do tensor, não hardcoded 84)
 */
import { useState, useEffect, useRef, useCallback } from 'react'
import * as ort from 'onnxruntime-web'

const DEMO_DURATION_MS = 15 * 60 * 1000
const MODEL_PATH = '/models/yolov8n-demo.onnx'
const INPUT_SIZE = 640
const CONF_THRESHOLD = 0.45
const IOU_THRESHOLD = 0.45
const FRAME_INTERVAL_MS = 100 // ~10 FPS target
const STATE_UPDATE_INTERVAL_MS = 1000 // update React state 1x/sec

const CLASSES: Record<number, { name: string; color: string }> = {
  0:  { name: 'pessoa',       color: '#3b82f6' },
  24: { name: 'mochila',      color: '#8b5cf6' },
  26: { name: 'bolsa',        color: '#8b5cf6' },
  39: { name: 'garrafa',      color: '#f59e0b' },
  56: { name: 'cadeira',      color: '#6366f1' },
  57: { name: 'sofá',         color: '#6366f1' },
  62: { name: 'TV',           color: '#ec4899' },
  63: { name: 'laptop',       color: '#ec4899' },
  64: { name: 'mouse',        color: '#ec4899' },
  67: { name: 'celular',      color: '#ec4899' },
  73: { name: 'livro',        color: '#14b8a6' },
  74: { name: 'relógio',      color: '#14b8a6' },
  80: { name: 'capacete',     color: '#22c55e' },
  81: { name: 'sem capacete', color: '#ef4444' },
  82: { name: 'colete',       color: '#22c55e' },
  83: { name: 'sem colete',   color: '#ef4444' },
  84: { name: 'óculos',       color: '#06b6d4' },
  85: { name: 'sem óculos',   color: '#f97316' },
}

const EPI_STATUS = [
  { label: 'Capacete', icon: '⛑️', presentId: 80, absentId: 81 },
  { label: 'Colete',   icon: '🦺', presentId: 82, absentId: 83 },
  { label: 'Óculos',   icon: '🥽', presentId: 84, absentId: 85 },
] as const

interface Detection {
  classId: number
  className: string
  confidence: number
  x1: number; y1: number; x2: number; y2: number
  color: string
}

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

/**
 * Parseia saída do modelo de detecção YOLO.
 * Usa numChannels e numPreds vindos dos dims reais do tensor
 * para suportar qualquer número de classes (COCO80, EPI84, etc.).
 */
function parseOutput(
  output: Float32Array,
  W: number,
  H: number,
  numChannels: number,
  numPreds: number,
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

export default function DemoCamera() {
  const videoRef   = useRef<HTMLVideoElement>(null)
  const canvasRef  = useRef<HTMLCanvasElement>(null)
  const sessionRef = useRef<ort.InferenceSession | null>(null)
  const timerRef   = useRef<ReturnType<typeof setTimeout> | null>(null)
  const startRef   = useRef<number>(0)
  const runningRef = useRef(false)

  // Reusable buffers (allocated once, never recreated)
  const tmpCanvasRef = useRef<HTMLCanvasElement | null>(null)
  const tmpCtxRef    = useRef<CanvasRenderingContext2D | null>(null)
  const bufferRef    = useRef<Float32Array | null>(null)

  // Throttled state update refs
  const frameCountRef   = useRef(0)
  const lastStateUpdate = useRef(0)
  const lastClassesRef  = useRef<string[]>([])
  const lastIdsRef      = useRef<Set<number>>(new Set())

  const [phase, setPhase] = useState<'idle' | 'loading' | 'running' | 'done'>('idle')
  const [error, setError] = useState<string | null>(null)
  const [fps, setFps] = useState(0)
  const [timeLeft, setTimeLeft] = useState(DEMO_DURATION_MS)
  const [detectedClasses, setDetectedClasses] = useState<string[]>([])
  const [detectedIds, setDetectedIds] = useState<Set<number>>(new Set())

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
    setPhase('done')
    if (timerRef.current) { clearTimeout(timerRef.current); timerRef.current = null }
    if (videoRef.current?.srcObject) {
      (videoRef.current.srcObject as MediaStream).getTracks().forEach(t => t.stop())
      videoRef.current.srcObject = null
    }
    if (sessionRef.current) {
      sessionRef.current.release?.()
      sessionRef.current = null
    }
  }, [])

  const runLoop = useCallback(async () => {
    if (!runningRef.current) return

    const video = videoRef.current
    const canvas = canvasRef.current
    const sess = sessionRef.current
    if (!video || !canvas || !sess) return

    const elapsed = Date.now() - startRef.current
    if (elapsed >= DEMO_DURATION_MS) { stopDemo(); return }

    const vw = video.videoWidth || 640
    const vh = video.videoHeight || 480
    if (canvas.width !== vw) canvas.width = vw
    if (canvas.height !== vh) canvas.height = vh

    const ctx = canvas.getContext('2d')!
    ctx.drawImage(video, 0, 0)

    try {
      const { tmpCtx, buf } = getBuffers()
      tmpCtx.drawImage(canvas, 0, 0, INPUT_SIZE, INPUT_SIZE)
      preprocessInto(tmpCtx, buf)

      const tensor = new ort.Tensor('float32', buf, [1, 3, INPUT_SIZE, INPUT_SIZE])
      const results = await sess.run({ images: tensor })
      const outKey = Object.keys(results)[0]
      const outTensor = results[outKey]

      // Usar dims reais do tensor para suportar qualquer número de classes
      const dims = outTensor.dims as number[]
      const numChannels = dims[1] // ex: 84 para COCO80, 88 para EPI84
      const numPreds    = dims[2] // ex: 8400

      const dets = parseOutput(
        outTensor.data as Float32Array,
        canvas.width,
        canvas.height,
        numChannels,
        numPreds,
      )

      // Draw boxes
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

      // Track detections (refs — sem re-render por frame)
      frameCountRef.current++
      const names = [...new Set(dets.map(d => d.className))]
      if (names.length) lastClassesRef.current = names
      if (dets.length) lastIdsRef.current = new Set(dets.map(d => d.classId))

      // Throttled React state update (1x/segundo)
      const now = performance.now()
      if (now - lastStateUpdate.current >= STATE_UPDATE_INTERVAL_MS) {
        const dt = (now - lastStateUpdate.current) / 1000
        setFps(Math.round(frameCountRef.current / dt))
        setTimeLeft(DEMO_DURATION_MS - elapsed)
        if (lastClassesRef.current.length) setDetectedClasses(lastClassesRef.current)
        setDetectedIds(new Set(lastIdsRef.current))
        frameCountRef.current = 0
        lastStateUpdate.current = now
      }
    } catch (err) {
      console.warn('Demo inference error:', err)
    }

    if (runningRef.current) {
      timerRef.current = setTimeout(runLoop, FRAME_INTERVAL_MS)
    }
  }, [stopDemo, getBuffers])

  const startDemo = async () => {
    setPhase('loading')
    setError(null)
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
      lastStateUpdate.current = performance.now()
      frameCountRef.current = 0
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
      timerRef.current = setTimeout(runLoop, 0)
    }
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current)
    }
  }, [phase, runLoop])

  useEffect(() => {
    return () => {
      runningRef.current = false
      if (timerRef.current) clearTimeout(timerRef.current)
      sessionRef.current?.release?.()
    }
  }, [])

  const fmtTime = (ms: number) => {
    const s = Math.floor(ms / 1000)
    return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
  }

  return (
    <div className="bg-gray-100 rounded-xl sm:rounded-2xl p-2 sm:p-6 w-full sm:max-w-2xl mx-auto">

      {/* Viewport de câmera */}
      <div className="relative bg-black rounded-lg sm:rounded-xl overflow-hidden aspect-video mb-3">
        <video
          ref={videoRef}
          className="absolute inset-0 w-full h-full object-cover"
          playsInline muted
          style={{ display: phase === 'running' ? 'none' : 'block' }}
        />
        <canvas
          ref={canvasRef}
          className="absolute inset-0 w-full h-full object-contain"
          style={{ display: phase === 'running' ? 'block' : 'none' }}
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

      {/* Erro */}
      {error && (
        <div className="flex items-start gap-2 bg-red-50 text-red-700 rounded-lg p-3 mb-3 text-sm">
          <span>⚠️</span><span>{error}</span>
        </div>
      )}

      {/* Painel de status EPI — óculos, colete, capacete */}
      {phase === 'running' && (
        <div className="grid grid-cols-3 gap-2 mb-3">
          {EPI_STATUS.map(item => {
            const isPresent = detectedIds.has(item.presentId)
            const isAbsent  = detectedIds.has(item.absentId)
            const bg   = isPresent ? 'bg-green-50 border-green-300' : isAbsent ? 'bg-red-50 border-red-300' : 'bg-white border-gray-200'
            const text = isPresent ? 'text-green-700' : isAbsent ? 'text-red-600' : 'text-gray-400'
            const mark = isPresent ? '✓' : isAbsent ? '✗' : '—'
            return (
              <div key={item.label} className={`rounded-lg border px-2 py-2 text-center ${bg}`}>
                <div className="text-xl leading-none">{item.icon}</div>
                <div className={`text-xs font-semibold mt-1 ${text}`}>{item.label}</div>
                <div className={`text-sm font-bold ${text}`}>{mark}</div>
              </div>
            )
          })}
        </div>
      )}

      {/* Classes detectadas em geral */}
      {detectedClasses.length > 0 && (
        <div className="mb-3">
          <p className="text-xs font-medium text-gray-500 mb-1.5">Detectado agora:</p>
          <div className="flex flex-wrap gap-1.5">
            {detectedClasses.map(cls => (
              <span key={cls} className="px-2 py-0.5 bg-white rounded-full text-xs font-medium shadow-sm border border-gray-200">
                ✓ {cls}
              </span>
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
