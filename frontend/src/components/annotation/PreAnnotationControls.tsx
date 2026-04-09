import { Button } from '../ui/Button/Button'
import {
  container, header, sparkIcon, title, uncertaintyBadge, description, actions,
} from './PreAnnotationControls.css'

interface PreAnnotationControlsProps {
  hasPreAnnotations: boolean
  uncertaintyScore?: number
  onConfirm: () => void
  onEdit: () => void
  onReject: () => void
  disabled?: boolean
}

function uncertaintyLevel(score: number): 'high' | 'medium' | 'low' {
  if (score > 0.7) return 'high'
  if (score > 0.4) return 'medium'
  return 'low'
}

function uncertaintyLabel(score: number): string {
  if (score > 0.7) return 'Alta incerteza'
  if (score > 0.4) return 'Média incerteza'
  return 'Baixa incerteza'
}

export function PreAnnotationControls({
  hasPreAnnotations,
  uncertaintyScore,
  onConfirm,
  onEdit,
  onReject,
  disabled,
}: PreAnnotationControlsProps) {
  if (!hasPreAnnotations) return null

  return (
    <div className={container}>
      <div className={header}>
        <span className={sparkIcon}>✨</span>
        <span className={title}>Pré-anotação automática</span>
        {uncertaintyScore !== undefined && (
          <span className={uncertaintyBadge({ level: uncertaintyLevel(uncertaintyScore) })}>
            • {uncertaintyLabel(uncertaintyScore)} ({(uncertaintyScore * 100).toFixed(0)}%)
          </span>
        )}
      </div>

      <p className={description}>
        Boxes detectados automaticamente por IA. Revise e confirme, ajuste ou rejeite.
      </p>

      <div className={actions}>
        <Button variant="success" size="sm" onClick={onConfirm} disabled={disabled}>
          ✓ Confirmar
        </Button>
        <Button variant="primary" size="sm" onClick={onEdit} disabled={disabled}>
          ✏ Ajustar
        </Button>
        <Button variant="danger" size="sm" onClick={onReject} disabled={disabled}>
          ✗ Rejeitar
        </Button>
      </div>
    </div>
  )
}
