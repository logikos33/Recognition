/**
 * PageHeader — h1 + subtítulo + slot de ações, tokenizado (WS1).
 */
import type { ReactNode } from 'react'
import { header, titleGroup, title as titleCls, subtitle as subtitleCls, actions as actionsCls } from './PageHeader.css'

interface PageHeaderProps {
  title: ReactNode
  subtitle?: ReactNode
  actions?: ReactNode
}

export function PageHeader({ title, subtitle, actions }: PageHeaderProps) {
  return (
    <div className={header}>
      <div className={titleGroup}>
        <h1 className={titleCls}>{title}</h1>
        {subtitle && <p className={subtitleCls}>{subtitle}</p>}
      </div>
      {actions && <div className={actionsCls}>{actions}</div>}
    </div>
  )
}
