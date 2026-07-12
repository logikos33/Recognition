import type { ReactNode } from 'react'
import { Info } from 'lucide-react'
import { Tooltip } from '../ui/Tooltip/Tooltip'
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
  /** Texto do tooltip (i) explicando a métrica em pt-BR */
  info?: string
}

export function KPICard({ icon, iconBg, title, mainValue, sub, trend, trendLabel, pulse, onClick, active, info }: KPICardProps) {
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
        <span className={label}>
          {title}
          {info && (
            <Tooltip label={info}>
              <span
                aria-label={`Sobre: ${title}`}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  marginLeft: 4,
                  color: vars.color.textDim,
                  cursor: 'help',
                  verticalAlign: 'middle',
                }}
              >
                <Info size={12} />
              </span>
            </Tooltip>
          )}
        </span>
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
