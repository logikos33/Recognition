/**
 * Vídeo ao vivo com bounding boxes + overlay SVG de ROIs das operações.
 * Botão "Operação" no canto superior direito ativa modo de edição.
 *
 * Camadas (bottom → top):
 *   1. CameraPlayer (vídeo HLS)
 *   2. DetectionOverlay (canvas canvas2D, pointerEvents:none)
 *   3. SVG ROI overlay (pointerEvents:none — apenas visual)
 *   4. Botões de controle (position:absolute, top-right)
 */
import { Settings } from 'lucide-react'
import { DetectionOverlay, type Detection } from '../../monitoring/DetectionOverlay'
import { CameraPlayer } from '../../monitoring/CameraPlayer'
import type { Operation, RoiPoint } from '../../../types/operations'

interface LiveVideoWithOperationsProps {
  cameraId: string
  hlsUrl: string
  feedType?: 'hls' | 'demo_video'
  feedUrl?: string
  detections?: Detection[]
  operations?: Operation[]
  isEditMode?: boolean
  onEnterEditMode?: () => void
  width?: number
  height?: number
}

function getRoiPoints(op: Operation): RoiPoint[] {
  const pts = (op.config as Record<string, unknown>)?.roi_points
  if (!Array.isArray(pts)) return []
  return pts.map((p: unknown) => {
    const pair = p as [number, number]
    return { x: pair[0], y: pair[1] }
  })
}

const STATUS_COLORS: Record<string, string> = {
  active: '#22c55e',
  warning: '#f59e0b',
  error: '#ef4444',
  inactive: '#6b7280',
}

export function LiveVideoWithOperations({
  cameraId,
  hlsUrl,
  feedType = 'hls',
  feedUrl,
  detections = [],
  operations = [],
  isEditMode = false,
  onEnterEditMode,
  width = 640,
  height = 360,
}: LiveVideoWithOperationsProps) {
  const opsWithRoi = operations.filter(op => getRoiPoints(op).length >= 3)

  return (
    <div
      style={{
        position: 'relative',
        width,
        height,
        borderRadius: 8,
        overflow: 'hidden',
        background: '#000',
        flexShrink: 0,
      }}
    >
      {/* Layer 1: HLS video */}
      <CameraPlayer
        cameraId={cameraId}
        hlsUrl={hlsUrl}
        feedType={feedType}
        feedUrl={feedUrl}
        width={width}
        height={height}
      />

      {/* Layer 2: YOLO detection bboxes (canvas, non-interactive) */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          pointerEvents: 'none',
        }}
      >
        <DetectionOverlay
          detections={detections}
          videoWidth={640}
          videoHeight={360}
          displayWidth={width}
          displayHeight={height}
        />
      </div>

      {/* Layer 3: ROI overlays (SVG, non-interactive) */}
      {opsWithRoi.length > 0 && (
        <svg
          viewBox="0 0 1 1"
          preserveAspectRatio="none"
          style={{
            position: 'absolute',
            inset: 0,
            width: '100%',
            height: '100%',
            pointerEvents: 'none',
          }}
          aria-hidden="true"
        >
          {opsWithRoi.map((op, idx) => {
            const pts = getRoiPoints(op)
            const points = pts.map(p => `${p.x},${p.y}`).join(' ')
            const color = STATUS_COLORS[op.status] ?? '#3b82f6'
            return (
              <g key={op.id}>
                <polygon
                  points={points}
                  fill={color}
                  fillOpacity={0.1}
                  stroke={color}
                  strokeWidth={0.003}
                  strokeDasharray="0.01 0.005"
                />
                {/* Label do nome da operação */}
                <text
                  x={pts[0].x + 0.01}
                  y={pts[0].y - 0.01}
                  fontSize={0.04}
                  fill={color}
                  fontFamily="monospace"
                >
                  {idx + 1}. {op.name}
                </text>
              </g>
            )
          })}
        </svg>
      )}

      {/* Layer 4: botão "Operação" (canto superior direito) */}
      {!isEditMode && onEnterEditMode && (
        <button
          onClick={onEnterEditMode}
          title="Modo de edição de operações"
          style={{
            position: 'absolute',
            top: 10,
            right: 10,
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            padding: '6px 12px',
            background: 'rgba(0,0,0,0.75)',
            border: '1px solid rgba(255,255,255,0.2)',
            borderRadius: 6,
            color: '#fff',
            fontSize: 12,
            fontWeight: 500,
            cursor: 'pointer',
            backdropFilter: 'blur(4px)',
            zIndex: 10,
          }}
        >
          <Settings size={14} />
          Operação
        </button>
      )}

      {/* Edit mode badge */}
      {isEditMode && (
        <div
          style={{
            position: 'absolute',
            top: 10,
            right: 10,
            padding: '4px 10px',
            background: 'rgba(59, 130, 246, 0.85)',
            borderRadius: 6,
            color: '#fff',
            fontSize: 11,
            fontWeight: 600,
            letterSpacing: '0.05em',
            zIndex: 10,
          }}
        >
          EDITANDO
        </div>
      )}
    </div>
  )
}
