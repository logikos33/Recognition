/**
 * DrawingCanvas — canvas SVG para desenho de linha de cruzamento (contagem).
 *
 * Padrão: espelha RoiDrawer.tsx (components/training/canvas/RoiDrawer.tsx)
 *   - SVG viewBox="0 0 1 1" com pointerEvents:'none' em shapes
 *   - Camada transparente separada para interação (div com onClick/onMouseMove)
 *   - Coordenadas normalizadas [0, 1]
 *   - NUNCA onClick em shapes SVG
 *
 * Uso: inserir sobre frame de referência da câmera durante config de modelo.
 * Salva: { x1, y1, x2, y2 } normalizados — ou null se não definida.
 *
 * Fluxo: 1° clique → ponto inicial | 2° clique → ponto final → linha salva.
 */
import { useCallback, useRef, useState } from 'react'

export interface CountingLine {
  x1: number
  y1: number
  x2: number
  y2: number
}

interface DrawingCanvasProps {
  line: CountingLine | null
  onChange: (line: CountingLine | null) => void
  width?: number
  height?: number
  backgroundSrc?: string
  color?: string
  readOnly?: boolean
}

export function DrawingCanvas({
  line,
  onChange,
  width = 480,
  height = 270,
  backgroundSrc,
  color = '#f59e0b',
  readOnly = false,
}: DrawingCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [draft, setDraft] = useState<{ x: number; y: number } | null>(null)
  const [hover, setHover] = useState<{ x: number; y: number } | null>(null)

  const toNorm = useCallback((e: React.MouseEvent): { x: number; y: number } => {
    const rect = containerRef.current?.getBoundingClientRect()
    if (!rect) return { x: 0, y: 0 }
    return {
      x: Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width)),
      y: Math.max(0, Math.min(1, (e.clientY - rect.top) / rect.height)),
    }
  }, [])

  const handleClick = useCallback(
    (e: React.MouseEvent) => {
      if (readOnly) return
      const pt = toNorm(e)
      if (!draft) {
        // Primeiro clique: define ponto inicial, limpa linha anterior
        onChange(null)
        setDraft(pt)
      } else {
        // Segundo clique: define ponto final — salva linha completa
        onChange({ x1: draft.x, y1: draft.y, x2: pt.x, y2: pt.y })
        setDraft(null)
        setHover(null)
      }
    },
    [draft, onChange, toNorm, readOnly],
  )

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      if (readOnly || !draft) return
      setHover(toNorm(e))
    },
    [readOnly, draft, toNorm],
  )

  const handleMouseLeave = useCallback(() => setHover(null), [])

  const clear = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation()
      onChange(null)
      setDraft(null)
      setHover(null)
    },
    [onChange],
  )

  const hasLine = line !== null
  const hasDraft = draft !== null

  const instruction = readOnly
    ? ''
    : hasDraft
    ? 'Clique para definir o ponto final da linha'
    : hasLine
    ? 'Linha definida — clique para redesenhar'
    : 'Clique para definir o ponto inicial'

  return (
    <div
      style={{
        position: 'relative',
        width,
        height,
        borderRadius: 6,
        overflow: 'hidden',
        background: '#111',
        border: '1px solid #333',
        flexShrink: 0,
      }}
    >
      {/* Imagem de fundo: frame de referência da câmera */}
      {backgroundSrc && (
        <img
          src={backgroundSrc}
          alt="frame de referência"
          style={{
            position: 'absolute',
            inset: 0,
            width: '100%',
            height: '100%',
            objectFit: 'cover',
            pointerEvents: 'none',
          }}
          draggable={false}
        />
      )}

      {/* SVG overlay — TODOS os shapes com pointerEvents:none (regra obrigatória) */}
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
        {/* Linha definitiva salva */}
        {hasLine && (
          <>
            {/* Sombra para legibilidade sobre fundos claros */}
            <line
              x1={line.x1} y1={line.y1}
              x2={line.x2} y2={line.y2}
              stroke="rgba(0,0,0,0.5)"
              strokeWidth={0.007}
              strokeLinecap="round"
            />
            <line
              x1={line.x1} y1={line.y1}
              x2={line.x2} y2={line.y2}
              stroke={color}
              strokeWidth={0.005}
              strokeLinecap="round"
            />
            {/* Ponto inicial (preenchido) */}
            <circle cx={line.x1} cy={line.y1} r={0.018} fill={color} fillOpacity={0.95} />
            {/* Ponto final (contorno branco) */}
            <circle
              cx={line.x2} cy={line.y2} r={0.018}
              fill="#fff" fillOpacity={0.95}
              stroke={color} strokeWidth={0.004}
            />
          </>
        )}

        {/* Ponto inicial em rascunho (aguardando 2° clique) */}
        {hasDraft && (
          <>
            <circle cx={draft.x} cy={draft.y} r={0.018} fill={color} fillOpacity={0.95} />
            {/* Linha tracejada até posição do mouse */}
            {hover && (
              <>
                <line
                  x1={draft.x} y1={draft.y}
                  x2={hover.x} y2={hover.y}
                  stroke="rgba(0,0,0,0.4)"
                  strokeWidth={0.006}
                  strokeLinecap="round"
                />
                <line
                  x1={draft.x} y1={draft.y}
                  x2={hover.x} y2={hover.y}
                  stroke={color}
                  strokeWidth={0.004}
                  strokeDasharray="0.012 0.006"
                  opacity={0.85}
                />
              </>
            )}
          </>
        )}
      </svg>

      {/* Camada de interação — separada dos shapes (padrão obrigatório) */}
      {!readOnly && (
        <div
          ref={containerRef}
          onClick={handleClick}
          onMouseMove={handleMouseMove}
          onMouseLeave={handleMouseLeave}
          style={{
            position: 'absolute',
            inset: 0,
            cursor: 'crosshair',
            zIndex: 5,
          }}
        />
      )}
      {readOnly && <div ref={containerRef} style={{ position: 'absolute', inset: 0 }} />}

      {/* Instrução contextual */}
      {!readOnly && (
        <div
          style={{
            position: 'absolute',
            bottom: 6,
            left: 8,
            fontSize: 11,
            color: 'rgba(255,255,255,0.65)',
            pointerEvents: 'none',
            zIndex: 10,
            textShadow: '0 1px 2px rgba(0,0,0,0.8)',
          }}
        >
          {instruction}
        </div>
      )}

      {/* Botão Limpar */}
      {!readOnly && (hasLine || hasDraft) && (
        <button
          onClick={clear}
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
