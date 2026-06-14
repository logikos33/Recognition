/**
 * Badge visual para resultado de inspeção (OK/NOK) e status de feedback.
 */
import { badgeVariants } from './quality.css'
import type { InspectionResult, FeedbackStatus } from '../types/quality'

interface ResultBadgeProps {
  result: InspectionResult
}

export function ResultBadge({ result }: ResultBadgeProps) {
  return (
    <span className={badgeVariants[result]}>
      {result === 'ok' ? '✓ OK' : '✗ NOK'}
    </span>
  )
}

interface FeedbackBadgeProps {
  status: FeedbackStatus
}

export function FeedbackBadge({ status }: FeedbackBadgeProps) {
  const labels: Record<FeedbackStatus, string> = {
    pending: 'Pendente',
    confirmed: 'Confirmado',
    rejected: 'Rejeitado',
  }
  return (
    <span className={badgeVariants[status]}>
      {labels[status]}
    </span>
  )
}

interface DefectBadgeProps {
  classId: number | null
  label?: string
  color?: string
}

export function DefectBadge({ classId, label, color }: DefectBadgeProps) {
  if (classId === null || classId === 0) return null
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        padding: '2px 8px',
        borderRadius: '999px',
        fontSize: '11px',
        fontWeight: 600,
        background: color ? `${color}22` : 'rgba(239,83,80,0.12)',
        color: color ?? '#EF5350',
        border: `1px solid ${color ? `${color}44` : 'rgba(239,83,80,0.25)'}`,
      }}
    >
      {label ?? `Classe ${classId}`}
    </span>
  )
}
