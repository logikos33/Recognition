import type { ReactNode } from 'react'
import * as s from './admin.css'

interface MetricCardProps {
  icon: ReactNode
  value: string | number
  label: string
  delta?: string
  deltaType?: 'positive' | 'negative' | 'neutral'
}

export function MetricCard({ icon, value, label, delta, deltaType = 'neutral' }: MetricCardProps) {
  return (
    <div className={s.metricCard}>
      <div className={s.metricIcon}>{icon}</div>
      <div>
        <div className={s.metricValue}>{value}</div>
        <div className={s.metricLabel}>{label}</div>
        {delta && <div className={s.metricDelta[deltaType]}>{delta}</div>}
      </div>
    </div>
  )
}
