/**
 * Header do modo Visualização — exibe ações primárias do módulo.
 * Substituído pelo EditMode quando usuário entra no modo de edição.
 */
import type { ReactNode } from 'react'
import { vars } from '../../../styles/theme.css'

interface ViewModeProps {
  title: string
  children?: ReactNode
}

export function ViewMode({ title, children }: ViewModeProps) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '12px 20px',
        borderBottom: `1px solid ${vars.color.borderDefault}`,
        background: vars.color.bgBase,
        minHeight: 52,
      }}
    >
      <h2 style={{ margin: 0, fontSize: 16, fontWeight: 600, color: vars.color.textSecondary }}>{title}</h2>
      {children && <div style={{ display: 'flex', gap: 8 }}>{children}</div>}
    </div>
  )
}
