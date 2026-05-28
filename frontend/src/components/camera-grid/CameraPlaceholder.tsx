/**
 * CameraPlaceholder — empty cell with "+" button to assign a camera.
 */
import { useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { Plus } from 'lucide-react'
import { cellBase, cellDragOver, placeholder, placeholderText } from './CameraGrid.css'

interface CameraPlaceholderProps {
  position: number
  colspan?: number
  rowspan?: number
  onClick: () => void
}

export function CameraPlaceholder({ position, colspan, rowspan, onClick }: CameraPlaceholderProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isOver,
  } = useSortable({ id: `cell-${position}`, data: { position } })

  const style: React.CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
    ...(colspan && { gridColumn: `span ${colspan}` }),
    ...(rowspan && { gridRow: `span ${rowspan}` }),
  }

  return (
    <div
      ref={setNodeRef}
      className={`${cellBase} ${isOver ? cellDragOver : ''}`}
      style={style}
      {...attributes}
      {...listeners}
    >
      <button
        className={placeholder}
        onClick={onClick}
        aria-label={`Adicionar câmera na posição ${position + 1}`}
      >
        <Plus size={24} />
        <span className={placeholderText}>Adicionar câmera</span>
      </button>
    </div>
  )
}
