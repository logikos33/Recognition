/**
 * Canvas overlay para bounding boxes de detecções YOLO.
 *
 * REGRAS ABSOLUTAS (herança Fase 1):
 * - pointerEvents: 'none' no canvas — NUNCA remover
 * - Zero handlers onClick em qualquer bounding box — NUNCA adicionar
 */
import { useEffect, useRef } from 'react'
import { canvas as canvasClass } from './DetectionOverlay.css'

export interface Detection {
  class: string
  confidence: number
  bbox: [number, number, number, number]  // x, y, w, h (pixels no frame original)
}

interface DetectionOverlayProps {
  detections: Detection[]
  videoWidth: number
  videoHeight: number
  displayWidth?: number
  displayHeight?: number
}

// Canvas context cannot use CSS vars — centralized here for auditability // allow: canvas DETECTION_COLORS
// allow: canvas 2D context cannot consume CSS vars — semantic palette only
const DETECTION_COLORS: Record<string, string> = {
  helmet: '#22c55e', // allow: canvas DETECTION_COLORS
  no_helmet: '#ef4444', // allow: canvas DETECTION_COLORS
  vest: '#22c55e', // allow: canvas DETECTION_COLORS
  no_vest: '#ef4444', // allow: canvas DETECTION_COLORS
  gloves: '#22c55e', // allow: canvas DETECTION_COLORS
  no_gloves: '#ef4444', // allow: canvas DETECTION_COLORS
  safety_glasses: '#22c55e', // allow: canvas DETECTION_COLORS
  no_safety_glasses: '#ef4444', // allow: canvas DETECTION_COLORS
}

function getColor(cls: string): string {
  return DETECTION_COLORS[cls] ?? '#3b82f6' // allow: canvas semantic fallback
}

export function DetectionOverlay({
  detections,
  videoWidth,
  videoHeight,
  displayWidth = 640,
  displayHeight = 360,
}: DetectionOverlayProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    ctx.clearRect(0, 0, displayWidth, displayHeight)

    const scaleX = displayWidth / videoWidth
    const scaleY = displayHeight / videoHeight

    for (const det of detections) {
      const [x, y, w, h] = det.bbox
      const dx = x * scaleX
      const dy = y * scaleY
      const dw = w * scaleX
      const dh = h * scaleY
      const color = getColor(det.class)

      ctx.strokeStyle = color
      ctx.lineWidth = 2
      ctx.strokeRect(dx, dy, dw, dh)

      const label = `${det.class} ${(det.confidence * 100).toFixed(0)}%`
      ctx.font = '12px monospace'
      const textW = ctx.measureText(label).width
      ctx.fillStyle = color + 'cc'
      ctx.fillRect(dx, dy - 18, textW + 6, 18)
      ctx.fillStyle = '#fff' // allow: canvas DETECTION_COLORS
      ctx.fillText(label, dx + 3, dy - 4)
    }
  }, [detections, videoWidth, videoHeight, displayWidth, displayHeight])

  return (
    <canvas
      ref={canvasRef}
      width={displayWidth}
      height={displayHeight}
      className={canvasClass}
    />
  )
}
