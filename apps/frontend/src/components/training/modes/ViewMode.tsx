/**
 * Header do modo Visualização — exibe ações primárias do módulo.
 * Substituído pelo EditMode quando usuário entra no modo de edição.
 */
import type { ReactNode } from 'react'

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
        borderBottom: '1px solid #1e1e1e',
        background: '#0d0d0d',
        minHeight: 52,
      }}
    >
      <h2 style={{ margin: 0, fontSize: 16, fontWeight: 600, color: '#e0e0e0' }}>{title}</h2>
      {children && <div style={{ display: 'flex', gap: 8 }}>{children}</div>}
    </div>
  )
}
