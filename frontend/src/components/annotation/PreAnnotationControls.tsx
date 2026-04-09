/**
 * PreAnnotationControls — controles de revisão de pré-anotação automática.
 * Mostra apenas quando o frame tem pré-anotações (DINO+SAM).
 */

interface PreAnnotationControlsProps {
  hasPreAnnotations: boolean
  uncertaintyScore?: number
  onConfirm: () => void
  onEdit: () => void
  onReject: () => void
  disabled?: boolean
}

function uncertaintyColor(score: number): string {
  if (score > 0.7) return '#ef4444'
  if (score > 0.4) return '#f59e0b'
  return '#22c55e'
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

  const btn = (label: string, color: string, onClick: () => void) => (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        display: 'flex', alignItems: 'center', gap: 6,
        padding: '8px 16px', borderRadius: 8, border: 'none',
        background: color, color: 'white', fontWeight: 600,
        fontSize: 13, cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.5 : 1,
      }}
    >
      {label}
    </button>
  )

  return (
    <div style={{
      background: '#1e1b4b', border: '1px solid #4338ca',
      borderRadius: 10, padding: 16, marginBottom: 16,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
        <span style={{ fontSize: 16 }}>✨</span>
        <span style={{ fontWeight: 700, color: '#a5b4fc', fontSize: 14 }}>
          Pré-anotação automática
        </span>
        {uncertaintyScore !== undefined && (
          <span style={{ fontSize: 12, color: uncertaintyColor(uncertaintyScore), marginLeft: 4 }}>
            • {uncertaintyLabel(uncertaintyScore)} ({(uncertaintyScore * 100).toFixed(0)}%)
          </span>
        )}
      </div>

      <p style={{ fontSize: 12, color: '#818cf8', margin: '0 0 14px' }}>
        Boxes detectados automaticamente por IA. Revise e confirme, ajuste ou rejeite.
      </p>

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {btn('✓ Confirmar', '#22c55e', onConfirm)}
        {btn('✏ Ajustar', '#3b82f6', onEdit)}
        {btn('✗ Rejeitar', '#ef4444', onReject)}
      </div>
    </div>
  )
}

export default PreAnnotationControls
