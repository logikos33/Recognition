import type { ReactNode } from 'react'
import { badge } from './Badge.css'

export type BadgeVariant = 'success' | 'warning' | 'danger' | 'primary' | 'neutral' | 'accent'

interface BadgeProps {
  variant?: BadgeVariant
  children: ReactNode
  className?: string
}

export function Badge({ variant = 'neutral', children, className }: BadgeProps) {
  return (
    <span className={`${badge({ variant })}${className ? ` ${className}` : ''}`}>
      {children}
    </span>
  )
}

export function statusToBadgeVariant(status: string): BadgeVariant {
  switch (status) {
    case 'active': case 'online': case 'completed': case 'extracted': return 'success'
    case 'pending': case 'starting': case 'extracting': return 'warning'
    case 'error': case 'failed': return 'danger'
    case 'running': case 'uploaded': return 'primary'
    case 'stopped': case 'inactive': case 'offline': return 'neutral'
    default: return 'neutral'
  }
}
