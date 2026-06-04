/**
 * DrawingCanvas — overlay SVG interativo para desenho de geometrias sobre a câmera.
 *
 * Posição: absolute inset:0 — deve ser filho de um div com position:relative.
 * Ferramentas: zone (polígono ≥3 pts), line (2 pts), point (1 pt).
 * Undo/redo via Ctrl+Z / Ctrl+Shift+Z (ou Ctrl+Y).
 * Shapes: pointerEvents:none; camada de interação separada (padrão do projeto).
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import type { Operation, RoiPoint } from '../../types/operations'

export type DrawingTool = 'zone' | 'line' | 'point'

const STATUS_COLORS: Record<string, string> = {
  active: '#22c55e',
  warning: '#f59e0b',
  error: '#ef4444',
  inactive: '#6b7280',
}

function getOpPoints(op: Operation): RoiPoint[] {
  const cfg = op.config as Record<string, unknown>
  const pts = cfg?.roi_points ?? cfg?.line_points
  if (!Array.isArray(pts)) {
    const pt = cfg?.point
    if (Array.isArray(pt) && pt.length === 2) return [{ x: pt[0] as number, y: pt[1] as number }]
    return []
  }
  return (pts as [number, number][]).map(p => ({ x: p[0], y: p[1] }))
}

interface DrawingCanvasProps {
  points: RoiPoint[]
  tool: DrawingTool
  onChange: (points: RoiPoint[]) => void
  onUndo?: () => void
  onRedo?: () => void
  canUndo?: boolean
  canRedo?: boolean
  existingOperations?: Operation[]
}

export function DrawingCanvas({
  points,
  tool,
  onChange,
  onUndo,
  onRedo,
  canUndo = false,
  canRedo = false,
  existingOperations = [],
}: DrawingCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [hoverPt, setHoverPt] = useState<RoiPoint | null>(null)

  const toNorm = useCallback((e: React.MouseEvent): RoiPoint => {
    const rect = containerRef.current?.getBoundingClientRect()
    if (!rect) return { x: 0, y: 0 }
    return {
      x: Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width)),
      y: Math.max(0, Math.min(1, (e.clientY - rect.top) / rect.height)),
    }
  }, [])

  const handleClick = useCallback((e: React.MouseEvent) => {
    const pt = toNorm(e)
    if (tool === 'point') { onChange([pt]); return }
    if (tool === 'line') {
      onChange(points.length >= 2 ? [pt] : [...points, pt])
      return
    }
    // zone: click near first point closes (no action = polygon already closed visually)
    if (points.length >= 3) {
      const first = points[0]
      if (Math.hypot(pt.x - first.x, pt.y - first.y) < 0.03) return
    }
    onChange([...points, pt])
  }, [tool, points, onChange, toNorm])

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    setHoverPt(toNorm(e))
  }, [toNorm])

  useEffect(() => {
    const handle = (e: KeyboardEvent) => {
      if (!(e.metaKey || e.ctrlKey)) return
      if (!e.shiftKey && e.key === 'z') { e.preventDefault(); onUndo?.() }
      if ((e.shiftKey && e.key === 'z') || e.key === 'y') { e.preventDefault(); onRedo?.() }
    }
    window.addEventListener('keydown', handle)
    return () => window.removeEventListener('keydown', handle)
  }, [onUndo, onRedo])

  const pointsStr = points.map(p => `${p.x},${p.y}`).join(' ')
  const drawColor = '#3b82f6'

  return (
    <div
      data-testid="drawing-canvas"
      style={{ position: 'absolute', inset: 0, zIndex: 5 }}
    >
      {/* SVG layer — shapes pointerEvents:none (padrão obrigatório) */}
      <svg
        viewBox="0 0 1 1"
        preserveAspectRatio="none"
        style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none' }}
        aria-hidden="true"
      >
        {/* Operações existentes */}
        {existingOperations.map(op => {
          const pts = getOpPoints(op)
          if (!pts.length) return null
          const c = STATUS_COLORS[op.status] ?? '#6b7280'
          const s = pts.map(p => `${p.x},${p.y}`).join(' ')
          return (
            <g key={op.id}>
              {pts.length >= 3 && (
                <polygon points={s} fill={c} fillOpacity={0.08} stroke={c} strokeWidth={0.003} strokeDasharray="0.012 0.005" />
              )}
              {pts.length === 2 && (
                <line x1={pts[0].x} y1={pts[0].y} x2={pts[1].x} y2={pts[1].y} stroke={c} strokeWidth={0.005} />
              )}
              {pts.length === 1 && (
                <circle cx={pts[0].x} cy={pts[0].y} r={0.018} fill={c} fillOpacity={0.5} stroke={c} strokeWidth={0.003} />
              )}
              <text
                x={pts[0].x + 0.01}
                y={Math.max(0.04, pts[0].y - 0.02)}
                fontSize={0.035}
                fill={c}
                fontFamily="monospace"
              >
                {op.name}
              </text>
            </g>
          )
        })}

        {/* Desenho atual — zona (polígono) */}
        {tool === 'zone' && points.length >= 3 && (
          <polygon points={pointsStr} fill={drawColor} fillOpacity={0.15} stroke={drawColor} strokeWidth={0.003} />
        )}
        {tool === 'zone' && points.length >= 2 && points.length < 3 && (
          <polyline points={pointsStr} fill="none" stroke={drawColor} strokeWidth={0.003} strokeDasharray="0.01 0.005" />
        )}
        {tool === 'zone' && hoverPt && points.length >= 1 && (
          <line
            x1={points[points.length - 1].x} y1={points[points.length - 1].y}
            x2={hoverPt.x} y2={hoverPt.y}
            stroke={drawColor} strokeWidth={0.002} strokeDasharray="0.008 0.004" opacity={0.5}
          />
        )}

        {/* Linha */}
        {tool === 'line' && points.length === 2 && (
          <line x1={points[0].x} y1={points[0].y} x2={points[1].x} y2={points[1].y}
            stroke={drawColor} strokeWidth={0.005}
            strokeLinecap="round"
          />
        )}
        {tool === 'line' && points.length === 1 && hoverPt && (
          <line x1={points[0].x} y1={points[0].y} x2={hoverPt.x} y2={hoverPt.y}
            stroke={drawColor} strokeWidth={0.004} strokeDasharray="0.01 0.005" opacity={0.6}
          />
        )}

        {/* Ponto */}
        {tool === 'point' && points.length === 1 && (
          <>
            <circle cx={points[0].x} cy={points[0].y} r={0.025} fill={drawColor} fillOpacity={0.2} stroke={drawColor} strokeWidth={0.004} />
            <circle cx={points[0].x} cy={points[0].y} r={0.008} fill={drawColor} />
          </>
        )}

        {/* Vértices */}
        {points.map((p, i) => (
          <circle
            key={i}
            cx={p.x} cy={p.y}
            r={i === 0 && tool === 'zone' ? 0.016 : 0.01}
            fill={i === 0 ? drawColor : '#fff'}
            fillOpacity={i === 0 ? 0.9 : 0.8}
            stroke={drawColor}
            strokeWidth={0.003}
          />
        ))}

        {/* Hover indicator */}
        {hoverPt && tool !== 'point' && (
          <circle cx={hoverPt.x} cy={hoverPt.y} r={0.007} fill={drawColor} fillOpacity={0.35} />
        )}
      </svg>

      {/* Camada de interação (separada dos shapes — padrão obrigatório) */}
      <div
        ref={containerRef}
        role="img"
        aria-label={`Canvas de desenho — ferramenta ${tool}`}
        onClick={handleClick}
        onMouseMove={handleMouseMove}
        onMouseLeave={() => setHoverPt(null)}
        tabIndex={0}
        style={{ position: 'absolute', inset: 0, cursor: 'crosshair', outline: 'none' }}
      />

      {/* Toolbar: undo / redo / limpar */}
      <div
        role="toolbar"
        aria-label="Controles de desenho"
        style={{ position: 'absolute', top: 10, right: 10, display: 'flex', gap: 4, zIndex: 10 }}
      >
        <button
          onClick={onUndo}
          disabled={!canUndo}
          title="Desfazer (Ctrl+Z)"
          aria-label="Desfazer"
          style={toolBtnStyle(!canUndo)}
        >
          ↩
        </button>
        <button
          onClick={onRedo}
          disabled={!canRedo}
          title="Refazer (Ctrl+Shift+Z)"
          aria-label="Refazer"
          style={toolBtnStyle(!canRedo)}
        >
          ↪
        </button>
        {points.length > 0 && (
          <button
            onClick={() => onChange([])}
            title="Limpar desenho"
            aria-label="Limpar desenho"
            style={toolBtnStyle(false)}
          >
            ✕
          </button>
        )}
      </div>

      {/* Instrução */}
      <div
        role="status"
        aria-live="polite"
        style={{
          position: 'absolute', bottom: 10, left: 10,
          fontSize: 11, color: 'rgba(255,255,255,0.5)',
          pointerEvents: 'none', zIndex: 10,
          background: 'rgba(0,0,0,0.4)', borderRadius: 4, padding: '3px 8px',
        }}
      >
        {tool === 'zone' && (
          points.length === 0 ? 'Clique para adicionar pontos da zona'
            : points.length < 3 ? `${points.length} ponto(s) — adicione mais ${3 - points.length}`
              : `${points.length} pontos — clique no ● inicial para fechar`
        )}
        {tool === 'line' && (
          points.length === 0 ? 'Clique para definir início da linha'
            : points.length === 1 ? 'Clique para definir fim da linha'
              : 'Linha definida — clique para redesenhar'
        )}
        {tool === 'point' && (
          points.length === 0 ? 'Clique para definir o ponto de interesse'
            : 'Ponto definido — clique para reposicionar'
        )}
      </div>
    </div>
  )
}

function toolBtnStyle(disabled: boolean): React.CSSProperties {
  return {
    width: 28, height: 28,
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    background: 'rgba(0,0,0,0.75)',
    border: '1px solid rgba(255,255,255,0.2)',
    borderRadius: 4,
    color: disabled ? 'rgba(255,255,255,0.2)' : '#fff',
    fontSize: 14,
    cursor: disabled ? 'not-allowed' : 'pointer',
    backdropFilter: 'blur(4px)',
    transition: 'color 0.1s',
  }
}
