import type { ReactNode } from 'react'
import { container, icon, title, description } from './EmptyState.css'

interface EmptyStateProps {
  icon?: ReactNode
  title: string
  description?: string
  action?: ReactNode
  className?: string
}

export function EmptyState({ icon: iconNode, title: titleText, description: desc, action, className }: EmptyStateProps) {
  return (
    <div className={`${container}${className ? ` ${className}` : ''}`} role="status">
      {iconNode && <div className={icon}>{iconNode}</div>}
      <p className={title}>{titleText}</p>
      {desc && <p className={description}>{desc}</p>}
      {action}
    </div>
  )
}
