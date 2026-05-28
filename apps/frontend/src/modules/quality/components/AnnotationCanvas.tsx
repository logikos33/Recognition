/**
 * Canvas de anotação com bounding boxes para frames de inspeção de qualidade.
 *
 * REGRAS CRÍTICAS:
 * - bboxOverlay e todas as bboxes têm pointerEvents: 'none' — NUNCA onClick nelas
 * - seleção via hit-test matemático em handleMouseDown (no container)
 * - drag para desenhar nova bbox (handleMouseDown → Move → Up no container)
 * - bbox selecionada exibe borda destacada
 */
import { canvasContainer, canvasImage, bboxOverlay } from './quality.css'
import type { BoundingBox } from '../types/quality'

const CLASS_COLORS: Record<number, string> = {
  0: '#43D186',  // ok
  1: '#EF5350',  // nok
  2: '#FF8A65',  // visual
  3: '#FFB74D',  // dimensional
  4: '#F06292',  // superficie
  5: '#CE93D8',  // bolha
  6: '#4FC3F7',  // mancha
  7: '#E57373',  // montagem_faltando
  8: '#FFD54F',  // montagem_errada
}

interface AnnotationCanvasProps {
  imageUrl: string | null
  bboxes: BoundingBox[]
  previewBox: BoundingBox | null
  selectedId: string | null
  onMouseDown: (e: React.MouseEvent<HTMLDivElement>) => void
  onMouseMove: (e: React.MouseEvent<HTMLDivElement>) => void
  onMouseUp: (e: React.MouseEvent<HTMLDivElement>) => void
}

export function AnnotationCanvas({
  imageUrl,
  bboxes,
  previewBox,
  selectedId,
  onMouseDown,
  onMouseMove,
  onMouseUp,
}: AnnotationCanvasProps) {
  const allBoxes = previewBox ? [...bboxes, previewBox] : bboxes

  return (
    <div
      className={canvasContainer}
      onMouseDown={onMouseDown}
      onMouseMove={onMouseMove}
      onMouseUp={onMouseUp}
      // Evitar seleção de texto ao arrastar
      style={{ WebkitUserSelect: 'none', userSelect: 'none' }}
    >
      {imageUrl ? (
        <img
          src={imageUrl}
          alt="Frame para anotação"
          className={canvasImage}
          draggable={false}
        />
      ) : (
        <div style={{ aspectRatio: '16/9', background: '#111', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#555', fontSize: '13px' }}>
          Carregando frame…
        </div>
      )}

      {/* Overlay SVG — pointerEvents: none para não interceptar mouse do container */}
      <svg
        className={bboxOverlay}
        viewBox="0 0 1 1"
        preserveAspectRatio="none"
        style={{ pointerEvents: 'none' }}
      >
        {allBoxes.map((box) => {
          const isPreview = box.id === '__preview__'
          const isSelected = box.id === selectedId
          const color = CLASS_COLORS[box.class_id] ?? '#888'
          const x = box.cx - box.w / 2
          const y = box.cy - box.h / 2

          return (
            <g key={box.id} style={{ pointerEvents: 'none' }}>
              <rect
                x={x}
                y={y}
                width={box.w}
                height={box.h}
                fill={isPreview ? `${color}22` : `${color}18`}
                stroke={color}
                strokeWidth={isSelected ? 0.006 : 0.003}
                strokeDasharray={isPreview ? '0.02 0.01' : undefined}
                rx={0.004}
              />
              {!isPreview && (
                <rect
                  x={x}
                  y={Math.max(0, y - 0.04)}
                  width={0.12}
                  height={0.035}
                  fill={color}
                  rx={0.004}
                />
              )}
              {!isPreview && (
                <text
                  x={x + 0.005}
                  y={Math.max(0.03, y - 0.012)}
                  fill="#fff"
                  fontSize={0.025}
                  fontWeight="bold"
                  style={{ pointerEvents: 'none', userSelect: 'none' }}
                >
                  {box.label ?? `c${box.class_id}`}
                </text>
              )}
              {/* Handle de seleção no canto superior direito */}
              {isSelected && (
                <circle
                  cx={x + box.w}
                  cy={y}
                  r={0.008}
                  fill={color}
                  stroke="#fff"
                  strokeWidth={0.003}
                />
              )}
            </g>
          )
        })}
      </svg>
    </div>
  )
}
