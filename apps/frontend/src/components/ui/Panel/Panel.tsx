/**
 * Panel — contêiner canônico de seção de página (WS1, VMS §7).
 * Mata o padrão "container branco com título cinza": superfície tokenizada,
 * header opcional com título/subtítulo/ações, tudo em vars do tema.
 */
import type { HTMLAttributes, ReactNode } from 'react'
import { panel, panelHeader, panelTitle, panelSubtitle, panelActions, panelBody } from './Panel.css'

interface PanelProps extends Omit<HTMLAttributes<HTMLElement>, 'title'> {
  /** Superfície: surface (default) | card | elevated */
  variant?: 'surface' | 'card' | 'elevated'
  /** Título do header (header só renderiza se title/actions presentes) */
  title?: ReactNode
  /** Subtítulo em textSecondary abaixo do título */
  subtitle?: ReactNode
  /** Slot de ações à direita do header */
  actions?: ReactNode
  /** Padding do corpo: none | md | lg (default lg quando há body) */
  padding?: 'none' | 'md' | 'lg'
  children: ReactNode
}

export function Panel({
  variant = 'surface',
  title,
  subtitle,
  actions,
  padding,
  className,
  children,
  ...props
}: PanelProps) {
  const hasHeader = Boolean(title) || Boolean(actions)
  const cls = panel({ variant, padding: hasHeader ? 'none' : (padding ?? 'none') })

  return (
    <section className={`${cls}${className ? ` ${className}` : ''}`} {...props}>
      {hasHeader && (
        <header className={panelHeader}>
          <div>
            {title && <h2 className={panelTitle}>{title}</h2>}
            {subtitle && <p className={panelSubtitle}>{subtitle}</p>}
          </div>
          {actions && <div className={panelActions}>{actions}</div>}
        </header>
      )}
      {hasHeader ? <div className={panelBody}>{children}</div> : children}
    </section>
  )
}
