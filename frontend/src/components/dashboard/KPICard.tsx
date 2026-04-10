import type { ReactNode } from 'react'
import {
  card, iconWrap, content, label, valueRow, value,
  subtext, alertPulse, trendUp, trendDown,
} from './KPICard.css'

interface KPICardProps {
  icon: ReactNode
  iconBg: string
  title: string
  mainValue: string | number
  sub?: string
  trend?: 'up' | 'down'
  trendLabel?: string
  pulse?: boolean
}

export function KPICard({ icon, iconBg, title, mainValue, sub, trend, trendLabel, pulse }: KPICardProps) {
  return (
    <div className={card}>
      <div className={iconWrap} style={{ background: iconBg }}>
        {icon}
      </div>
      <div className={content}>
        <span className={label}>{title}</span>
        <div className={valueRow}>
          <span className={`${value} ${pulse ? alertPulse : ''}`}>
            {mainValue}
          </span>
          {trend && trendLabel && (
            <span className={trend === 'up' ? trendUp : trendDown}>
              {trend === 'up' ? '↑' : '↓'} {trendLabel}
            </span>
          )}
        </div>
        {sub && <span className={subtext}>{sub}</span>}
      </div>
    </div>
  )
}
