/**
 * Canvas SVG para desenho interativo de polígonos ROI.
 *
 * Padrão: espelha AnnotationCanvas.tsx do módulo quality —
 *   - SVG viewBox="0 0 1 1" com pointerEvents:'none' em shapes
 *   - Camada transparente separada para interação (div com onMouseDown/Move/Up)
 *   - Coordenadas normalizadas [0,1]
 *   - NUNCA onClick em shapes
 *
 * Uso: inserir sobre ou ao lado do vídeo durante modal de configuração de ROI.
 */
import { useCallback, useRef, useState } from 'react'
import type { RoiPoint } from '../../../types/operations'

interface RoiDrawerProps {
  points: RoiPoint[]
  onChange: (points: RoiPoint[]) => void
  width?: number
  height?: number
  backgroundSrc?: string
  color?: string
  readOnly?: boolean
}

export function RoiDrawer({
  points,
  onChange,
  width = 480,
  height = 270,
  backgroundSrc,
  color = '#3b82f6',
  readOnly = false,
}: RoiDrawerProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [hoverPoint, setHoverPoint] = useState<RoiPoint | null>(null)
  const [isDragging, setIsDragging] = useState<number | null>(null)

  const toNorm = useCallback(
    (e: React.MouseEvent): RoiPoint => {
      const rect = containerRef.current?.getBoundingClientRect()
      if (!rect) return { x: 0, y: 0 }
      return {
        x: Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width)),
        y: Math.max(0, Math.min(1, (e.clientY - rect.top) / rect.height)),
      }
    },
    []
  )

  const handleClick = useCallback(
    (e: React.MouseEvent) => {
      if (readOnly) return
      if (isDragging !== null) return
      const pt = toNorm(e)
      // Fechar polígono se clicou perto do primeiro ponto
      if (points.length >= 3) {
        const first = points[0]
        const dist = Math.hypot(pt.x - first.x, pt.y - first.y)
        if (dist < 0.03) {
          return
        }
      }
      onChange([...points, pt])
    },
    [points, onChange, toNorm, readOnly, isDragging]
  )

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      if (readOnly) return
      const pt = toNorm(e)
      if (isDragging !== null) {
        const next = [...points]
        next[isDragging] = pt
        onChange(next)
        return
      }
      setHoverPoint(pt)
    },
    [toNorm, points, onChange, isDragging, readOnly]
  )

  const handleMouseLeave = useCallback(() => {
    setHoverPoint(null)
    setIsDragging(null)
  }, [])

  const handleMouseUp = useCallback(() => {
    setIsDragging(null)
  }, [])

  const pointsStr = points.map(p => `${p.x},${p.y}`).join(' ')
  const isClosed = points.length >= 3

  return (
    <div style={{ position: 'relative', width, height, borderRadius: 6, overflow: 'hidden', background: '#111', border: '1px solid #333' }}>
      {/* Background: frame de referência */}
      {backgroundSrc && (
        <img
          src={backgroundSrc}
          alt="frame de referência"
          style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover', pointerEvents: 'none' }}
          draggable={false}
        />
      )}

      {/* SVG overlay — shapes sempre pointerEvents:none */}
      <svg
        viewBox="0 0 1 1"
        preserveAspectRatio="none"
        style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none' }}
        aria-hidden="true"
      >
        {/* Polígono fechado */}
        {isClosed && (
          <polygon
            points={pointsStr}
            fill={color}
            fillOpacity={0.15}
            stroke={color}
            strokeWidth={0.003}
          />
        )}

        {/* Linhas abertas enquanto não fechado */}
        {!isClosed && points.length >= 2 && (
          <polyline
            points={pointsStr}
            fill="none"
            stroke={color}
            strokeWidth={0.003}
            strokeDasharray="0.01 0.005"
          />
        )}

        {/* Linha do último ponto até o hover */}
        {!readOnly && hoverPoint && points.length >= 1 && (
          <line
            x1={points[points.length - 1].x}
            y1={points[points.length - 1].y}
            x2={hoverPoint.x}
            y2={hoverPoint.y}
            stroke={color}
            strokeWidth={0.002}
            strokeDasharray="0.008 0.004"
            opacity={0.6}
          />
        )}

        {/* Pontos clicáveis (círculos) */}
        {points.map((p, i) => (
          <circle
            key={i}
            cx={p.x}
            cy={p.y}
            r={i === 0 && isClosed ? 0.018 : 0.012}
            fill={i === 0 ? color : '#fff'}
            fillOpacity={i === 0 ? 0.9 : 0.8}
            stroke={color}
            strokeWidth={0.003}
          />
        ))}

        {/* Hover indicator */}
        {!readOnly && hoverPoint && (
          <circle
            cx={hoverPoint.x}
            cy={hoverPoint.y}
            r={0.01}
            fill={color}
            fillOpacity={0.5}
          />
        )}
      </svg>

      {/* Camada de interação (separada dos shapes — padrão obrigatório) */}
      {!readOnly && (
        <div
          ref={containerRef}
          onClick={handleClick}
          onMouseMove={handleMouseMove}
          onMouseLeave={handleMouseLeave}
          onMouseUp={handleMouseUp}
          style={{
            position: 'absolute',
            inset: 0,
            cursor: 'crosshair',
            zIndex: 5,
          }}
        />
      )}

      {/* Read-only overlay para posicionamento correto do containerRef */}
      {readOnly && <div ref={containerRef} style={{ position: 'absolute', inset: 0 }} />}

      {/* Instrução */}
      {!readOnly && (
        <div
          style={{
            position: 'absolute',
            bottom: 6,
            left: 8,
            fontSize: 11,
            color: 'rgba(255,255,255,0.6)',
            pointerEvents: 'none',
            zIndex: 10,
          }}
        >
          {points.length === 0
            ? 'Clique para adicionar pontos'
            : points.length < 3
            ? `${points.length} pontos — adicione mais ${3 - points.length}`
            : `${points.length} pontos — clique no ● inicial para fechar`}
        </div>
      )}

      {/* Botão limpar */}
      {!readOnly && points.length > 0 && (
        <button
          onClick={e => { e.stopPropagation(); onChange([]) }}
          style={{
            position: 'absolute',
            top: 6,
            right: 6,
            padding: '3px 8px',
            background: 'rgba(0,0,0,0.7)',
            border: '1px solid rgba(255,255,255,0.2)',
            borderRadius: 4,
            color: '#fff',
            fontSize: 11,
            cursor: 'pointer',
            zIndex: 10,
          }}
        >
          Limpar
        </button>
      )}
    </div>
  )
}
