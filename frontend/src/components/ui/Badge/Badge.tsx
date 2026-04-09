import type { ReactNode } from 'react'
import { badge } from './Badge.css'

type BadgeStatus =
  | 'active' | 'inactive' | 'error' | 'warning' | 'running' | 'starting'
  | 'pending' | 'completed' | 'failed' | 'stopped' | 'online' | 'offline'

interface BadgeProps {
  status?: BadgeStatus
  children: ReactNode
  className?: string
}

/** Maps legacy string status values to badge variants */
export function statusToBadge(status: string): BadgeStatus {
  const map: Record<string, BadgeStatus> = {
    active: 'active', running: 'running', completed: 'completed',
    pending: 'pending', error: 'error', failed: 'failed',
    stopped: 'stopped', inactive: 'inactive', starting: 'starting',
    uploaded: 'pending', extracting: 'running', extracted: 'completed',
    online: 'online', offline: 'offline', warning: 'warning',
  }
  return map[status] ?? 'inactive'
}

export function Badge({ status = 'inactive', children, className }: BadgeProps) {
  return (
    <span className={`${badge({ status })}${className ? ` ${className}` : ''}`}>
      {children}
    </span>
  )
}
