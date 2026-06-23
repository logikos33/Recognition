/**
 * Canvas interativo para desenho de ROI/linha/ponto sobre frame de câmera.
 * Ferramentas: zone (polígono), line (2 pontos), point (1 ponto).
 * Shapes têm pointerEvents:none (padrão obrigatório — nunca onClick em shapes).
 * Undo/redo: Ctrl+Z / Ctrl+Shift+Z disparam callbacks externos (gerenciados pelo pai).
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import type { Operation, RoiPoint } from '../../types/operations'

export type DrawingTool = 'zone' | 'line' | 'point'

const STATUS_COLORS: Record<string, string> = {
  active: '#22c55e',
  warning: '#eab308',
  error: '#ef4444',
  inactive: '#6b7280',
}

export interface DrawingCanvasProps {
  tool: DrawingTool
  points: RoiPoint[]
  onChange: (points: RoiPoint[]) => void
  onUndo: () => void
  onRedo: () => void
  existingOperations?: Operation[]
  backgroundSrc?: string
  width?: number
  height?: number
}

export function DrawingCanvas({
  tool,
  points,
  onChange,
  onUndo,
  onRedo,
  existingOperations = [],
  backgroundSrc,
  width = 640,
  height = 360,
}: DrawingCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [hoverPoint, setHoverPoint] = useState<RoiPoint | null>(null)

  const toNorm = useCallback((e: React.MouseEvent): RoiPoint => {
    const rect = containerRef.current?.getBoundingClientRect()
    if (!rect || rect.width === 0) return { x: 0, y: 0 }
    return {
      x: Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width)),
      y: Math.max(0, Math.min(1, (e.clientY - rect.top) / rect.height)),
    }
  }, [])

  const handleClick = useCallback(
    (e: React.MouseEvent) => {
      const pt = toNorm(e)
      if (tool === 'point') {
        onChange([pt])
        return
      }
      if (tool === 'line') {
        onChange(points.length >= 2 ? [pt] : [...points, pt])
        return
      }
      // zone: não fechar se clicou perto do primeiro ponto
      if (points.length >= 3) {
        const first = points[0]
        if (Math.hypot(pt.x - first.x, pt.y - first.y) < 0.03) return
      }
      onChange([...points, pt])
    },
    [tool, points, onChange, toNorm]
  )

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => setHoverPoint(toNorm(e)),
    [toNorm]
  )

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (!(e.ctrlKey || e.metaKey) || e.key !== 'z') return
      if (e.shiftKey) {
        onRedo()
      } else {
        onUndo()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onUndo, onRedo])

  const activeColor = '#3b82f6'
  const pointsStr = points.map(p => `${p.x},${p.y}`).join(' ')
  const isZoneClosed = tool === 'zone' && points.length >= 3

  const instruction =
    tool === 'zone'
      ? points.length === 0
        ? 'Clique para adicionar vértices da zona'
        : points.length < 3
        ? `${points.length} vértices — adicione mais ${3 - points.length}`
        : `${points.length} vértices — clique no ● para fechar`
      : tool === 'line'
      ? points.length < 2
        ? `Ponto ${points.length + 1}/2`
        : 'Linha definida'
      : 'Clique para posicionar o ponto'

  return (
    <div
      data-testid="drawing-canvas"
      style={{
        position: 'relative', width, height,
        borderRadius: 6, overflow: 'hidden',
        background: '#111', border: '1px solid #333',
      }}
    >
      {backgroundSrc ? (
        <img
          src={backgroundSrc}
          alt="frame da câmera"
          style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover', pointerEvents: 'none' }}
          draggable={false}
        />
      ) : (
        <div
          aria-hidden="true"
          style={{
            position: 'absolute', inset: 0,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: 'rgba(255,255,255,0.2)', fontSize: 13, pointerEvents: 'none',
          }}
        >
          Frame da câmera (placeholder em dev)
        </div>
      )}

      {/* SVG overlay — shapes SEMPRE pointerEvents:none */}
      <svg
        viewBox="0 0 1 1"
        preserveAspectRatio="none"
        style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none' }}
        aria-hidden="true"
      >
        {/* Operações existentes */}
        {existingOperations.map(op => {
          const pts = Array.isArray(op.config?.roi) ? (op.config.roi as RoiPoint[]) : []
          const color = STATUS_COLORS[op.status] ?? '#6b7280'
          const pStr = pts.map(p => `${p.x},${p.y}`).join(' ')
          if (pts.length >= 3) {
            return (
              <polygon key={op.id} points={pStr}
                fill={color} fillOpacity={0.1}
                stroke={color} strokeWidth={0.003} strokeDasharray="0.012 0.006" />
            )
          }
          if (pts.length === 2) {
            return (
              <line key={op.id}
                x1={pts[0].x} y1={pts[0].y} x2={pts[1].x} y2={pts[1].y}
                stroke={color} strokeWidth={0.004} />
            )
          }
          if (pts.length === 1) {
            return (
              <circle key={op.id} cx={pts[0].x} cy={pts[0].y} r={0.015}
                fill={color} fillOpacity={0.7} stroke={color} strokeWidth={0.003} />
            )
          }
          return null
        })}

        {/* Desenho em progresso */}
        {isZoneClosed && (
          <polygon points={pointsStr}
            fill={activeColor} fillOpacity={0.15}
            stroke={activeColor} strokeWidth={0.003} />
        )}
        {!isZoneClosed && points.length >= 2 && (
          <polyline points={pointsStr}
            fill="none" stroke={activeColor}
            strokeWidth={0.003} strokeDasharray="0.01 0.005" />
        )}
        {hoverPoint && points.length >= 1 && (
          <line
            x1={points[points.length - 1].x} y1={points[points.length - 1].y}
            x2={hoverPoint.x} y2={hoverPoint.y}
            stroke={activeColor} strokeWidth={0.002}
            strokeDasharray="0.008 0.004" opacity={0.6} />
        )}
        {points.map((p, i) => (
          <circle key={i} cx={p.x} cy={p.y}
            r={i === 0 && isZoneClosed ? 0.018 : 0.012}
            fill={i === 0 ? activeColor : '#fff'} fillOpacity={0.9}
            stroke={activeColor} strokeWidth={0.003} />
        ))}
        {hoverPoint && (
          <circle cx={hoverPoint.x} cy={hoverPoint.y} r={0.01}
            fill={activeColor} fillOpacity={0.5} />
        )}
      </svg>

      {/* Camada de interação — separada dos shapes (padrão obrigatório) */}
      <div
        ref={containerRef}
        data-testid="canvas-interaction-layer"
        role="img"
        aria-label={`Canvas de desenho — ferramenta ${tool}. Clique para adicionar pontos. Ctrl+Z para desfazer, Ctrl+Shift+Z para refazer.`}
        tabIndex={0}
        onClick={handleClick}
        onMouseMove={handleMouseMove}
        onMouseLeave={() => setHoverPoint(null)}
        style={{ position: 'absolute', inset: 0, cursor: 'crosshair', zIndex: 5 }}
      />

      <div
        aria-live="polite"
        style={{
          position: 'absolute', bottom: 6, left: 8,
          fontSize: 11, color: 'rgba(255,255,255,0.6)',
          pointerEvents: 'none', zIndex: 10,
        }}
      >
        {instruction}
      </div>

      {points.length > 0 && (
        <button
          onClick={e => { e.stopPropagation(); onChange([]) }}
          aria-label="Limpar pontos desenhados"
          style={{
            position: 'absolute', top: 6, right: 6,
            padding: '3px 8px', background: 'rgba(0,0,0,0.7)',
            border: '1px solid rgba(255,255,255,0.2)',
            borderRadius: 4, color: '#fff', fontSize: 11,
            cursor: 'pointer', zIndex: 10,
          }}
        >
          Limpar
        </button>
      )}
    </div>
  )
}
