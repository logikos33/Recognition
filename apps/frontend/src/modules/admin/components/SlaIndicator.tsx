import * as s from './admin.css'
import type { TicketPriority } from '../types/admin'

const SLA_HOURS: Record<TicketPriority, number> = {
  critical: 1,
  high:     4,
  normal:   24,
  low:      72,
}

interface SlaIndicatorProps {
  priority: TicketPriority
  createdAt: string
  firstRespondedAt?: string
}

export function SlaIndicator({ priority, createdAt, firstRespondedAt }: SlaIndicatorProps) {
  const slaMs = SLA_HOURS[priority] * 3_600_000
  const elapsed = (firstRespondedAt ? new Date(firstRespondedAt) : new Date()).getTime() - new Date(createdAt).getTime()
  const breached = !firstRespondedAt && elapsed > slaMs
  const pct = Math.min(100, (elapsed / slaMs) * 100)

  const color = breached ? 'var(--color-danger, #ef4444)' : pct > 75 ? '#ca8a04' : '#16a34a'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <div style={{ height: 4, background: 'rgba(0,0,0,0.08)', borderRadius: 2, width: 80 }}>
        <div style={{ height: '100%', width: `${pct}%`, background: color, borderRadius: 2, transition: 'width 0.3s' }} />
      </div>
      {breached && <span className={s.muted} style={{ color: 'var(--color-danger, #ef4444)', fontSize: 10 }}>SLA vencido</span>}
    </div>
  )
}
