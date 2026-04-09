/**
 * DemoCamera — Demo IA no browser com ONNX Runtime Web.
 * YOLOv8n: 640x640, NCHW float32.
 * Sessão de 5 minutos por visita.
 */
import { useState, useEffect, useRef, useCallback } from 'react'
import * as ort from 'onnxruntime-web'

const DEMO_DURATION_MS = 5 * 60 * 1000
const MODEL_PATH = '/models/yolov8n-demo.onnx'
const INPUT_SIZE = 640
const CONF_THRESHOLD = 0.45
const IOU_THRESHOLD = 0.45

// Subset de classes COCO relevantes + EPIs customizados (80-83)
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
}

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

function preprocessCanvas(ctx: CanvasRenderingContext2D): Float32Array {
  const imgData = ctx.getImageData(0, 0, INPUT_SIZE, INPUT_SIZE).data
  const out = new Float32Array(3 * INPUT_SIZE * INPUT_SIZE)
  const N = INPUT_SIZE * INPUT_SIZE
  for (let i = 0; i < N; i++) {
    out[i]         = imgData[i * 4]     / 255  // R
    out[i + N]     = imgData[i * 4 + 1] / 255  // G
    out[i + N * 2] = imgData[i * 4 + 2] / 255  // B
  }
  return out
}

function parseOutput(output: Float32Array, W: number, H: number): Detection[] {
  // YOLOv8 output shape: [1, 84, 8400] → transposed to [8400, 84]
  const numDet = output.length / 84
  const dets: Detection[] = []

  for (let i = 0; i < numDet; i++) {
    // Find max class score
    let maxScore = 0, maxClass = 0
    for (let c = 4; c < 84; c++) {
      const s = output[c * numDet + i]
      if (s > maxScore) { maxScore = s; maxClass = c - 4 }
    }
    if (maxScore < CONF_THRESHOLD) continue
    if (!(maxClass in CLASSES)) continue

    const cx = output[0 * numDet + i] / INPUT_SIZE * W
    const cy = output[1 * numDet + i] / INPUT_SIZE * H
    const w  = output[2 * numDet + i] / INPUT_SIZE * W
    const h  = output[3 * numDet + i] / INPUT_SIZE * H

    dets.push({
      classId: maxClass,
      className: CLASSES[maxClass].name,
      confidence: maxScore,
      x1: cx - w / 2, y1: cy - h / 2,
      x2: cx + w / 2, y2: cy + h / 2,
      color: CLASSES[maxClass].color,
    })
  }
  return nms(dets)
}

export default function DemoCamera() {
  const videoRef   = useRef<HTMLVideoElement>(null)
  const canvasRef  = useRef<HTMLCanvasElement>(null)
  const sessionRef = useRef<ort.InferenceSession | null>(null)
  const rafRef     = useRef<number | null>(null)
  const startRef   = useRef<number>(0)
  const lastFpsRef = useRef<number>(performance.now())

  const [phase, setPhase] = useState<'idle' | 'loading' | 'running' | 'done'>('idle')
  const [error, setError] = useState<string | null>(null)
  const [fps, setFps] = useState(0)
  const [timeLeft, setTimeLeft] = useState(DEMO_DURATION_MS)
  const [detectedClasses, setDetectedClasses] = useState<string[]>([])

  const stopDemo = useCallback(() => {
    setPhase('done')
    if (rafRef.current) cancelAnimationFrame(rafRef.current)
    if (videoRef.current?.srcObject) {
      (videoRef.current.srcObject as MediaStream).getTracks().forEach(t => t.stop())
      videoRef.current.srcObject = null
    }
  }, [])

  const runLoop = useCallback(async () => {
    const video = videoRef.current
    const canvas = canvasRef.current
    const sess = sessionRef.current
    if (!video || !canvas || !sess) return

    const elapsed = Date.now() - startRef.current
    if (elapsed >= DEMO_DURATION_MS) { stopDemo(); return }

    setTimeLeft(DEMO_DURATION_MS - elapsed)

    // FPS
    const now = performance.now()
    setFps(Math.round(1000 / (now - lastFpsRef.current)))
    lastFpsRef.current = now

    canvas.width = video.videoWidth || 640
    canvas.height = video.videoHeight || 480
    const ctx = canvas.getContext('2d')!
    ctx.drawImage(video, 0, 0)

    try {
      const tmp = document.createElement('canvas')
      tmp.width = tmp.height = INPUT_SIZE
      const tmpCtx = tmp.getContext('2d')!
      tmpCtx.drawImage(canvas, 0, 0, INPUT_SIZE, INPUT_SIZE)

      const data = preprocessCanvas(tmpCtx)
      const tensor = new ort.Tensor('float32', data, [1, 3, INPUT_SIZE, INPUT_SIZE])
      const results = await sess.run({ images: tensor })
      const outKey = Object.keys(results)[0]
      const dets = parseOutput(results[outKey].data as Float32Array, canvas.width, canvas.height)

      // Draw boxes
      dets.forEach(d => {
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
      })

      const names = [...new Set(dets.map(d => d.className))]
      if (names.length) setDetectedClasses(names)
    } catch { /* inference error — continue */ }

    rafRef.current = requestAnimationFrame(runLoop)
  }, [stopDemo])

  const startDemo = async () => {
    setPhase('loading')
    setError(null)
    try {
      // Request camera
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment', width: { ideal: 640 }, height: { ideal: 480 } },
      })
      if (videoRef.current) {
        videoRef.current.srcObject = stream
        await videoRef.current.play()
      }

      // Load model
      if (!sessionRef.current) {
        sessionRef.current = await ort.InferenceSession.create(MODEL_PATH, {
          executionProviders: ['webgl', 'wasm'],
          graphOptimizationLevel: 'all',
        })
      }

      startRef.current = Date.now()
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
      rafRef.current = requestAnimationFrame(runLoop)
    }
    return () => { if (rafRef.current) cancelAnimationFrame(rafRef.current) }
  }, [phase, runLoop])

  const fmtTime = (ms: number) => {
    const s = Math.floor(ms / 1000)
    return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
  }

  return (
    <div className="bg-gray-100 rounded-2xl p-6 max-w-2xl mx-auto">
      {/* Video/Canvas display */}
      <div className="relative bg-black rounded-xl overflow-hidden aspect-video mb-4">
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

        {/* Idle / Done overlay */}
        {(phase === 'idle' || phase === 'done') && (
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/60 gap-4">
            {phase === 'done' ? (
              <>
                <div className="text-4xl">🎉</div>
                <p className="text-white font-semibold">Demo encerrada</p>
                <p className="text-gray-400 text-sm">5 minutos utilizados</p>
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

        {/* Loading */}
        {phase === 'loading' && (
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/70 gap-3">
            <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-orange-400" />
            <p className="text-white text-sm">Carregando modelo IA...</p>
          </div>
        )}

        {/* Running HUD */}
        {phase === 'running' && (
          <>
            <div className="absolute top-3 left-3 bg-black/70 text-white px-3 py-1 rounded-lg text-sm flex items-center gap-2">
              <span>⏱</span>{fmtTime(timeLeft)}
            </div>
            <div className="absolute top-3 right-3 bg-black/70 text-white px-3 py-1 rounded-lg text-xs">
              {fps} FPS
            </div>
            <button
              onClick={stopDemo}
              className="absolute bottom-3 right-3 bg-red-600 text-white p-2 rounded-lg hover:bg-red-700 transition text-xs font-bold"
            >
              ⏹ Stop
            </button>
          </>
        )}
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-start gap-2 bg-red-50 text-red-700 rounded-lg p-3 mb-4 text-sm">
          <span>⚠️</span><span>{error}</span>
        </div>
      )}

      {/* Detected objects */}
      {detectedClasses.length > 0 && (
        <div className="mb-4">
          <p className="text-sm font-medium text-gray-600 mb-2">Detectado agora:</p>
          <div className="flex flex-wrap gap-2">
            {detectedClasses.map(cls => (
              <span key={cls} className="px-3 py-1 bg-white rounded-full text-sm font-medium shadow-sm border border-gray-200">
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
