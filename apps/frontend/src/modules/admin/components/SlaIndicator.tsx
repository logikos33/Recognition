import * as s from './admin.css'
import type { TicketPriority } from '../types/admin'
import { vars } from '../../../styles/theme.css'

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

  const color = breached ? vars.color.danger : pct > 75 ? '#ca8a04' : vars.color.success

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <div style={{
        background: 'rgba(0,0,0,0.08)', // allow: trilha de progresso translúcida
        height: 4, borderRadius: 2, width: 80,
      }}>
        <div style={{ height: '100%', width: `${pct}%`, background: color, borderRadius: 2, transition: 'width 0.3s' }} />
      </div>
      {breached && <span className={s.muted} style={{ color: vars.color.danger, fontSize: 10 }}>SLA vencido</span>}
    </div>
  )
}
