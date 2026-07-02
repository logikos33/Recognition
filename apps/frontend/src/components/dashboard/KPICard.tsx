import type { ReactNode } from 'react'
import { vars } from '../../styles/theme.css'
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
  onClick?: () => void
  active?: boolean
}

export function KPICard({ icon, iconBg, title, mainValue, sub, trend, trendLabel, pulse, onClick, active }: KPICardProps) {
  return (
    <div
      className={card}
      onClick={onClick}
      style={{
        cursor: onClick ? 'pointer' : undefined,
        borderColor: active ? vars.color.primary : undefined,
      }}
    >
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
