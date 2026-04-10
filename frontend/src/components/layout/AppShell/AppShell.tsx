import type { ReactNode } from 'react'
import { useThemeStore } from '../../../stores/themeStore'
import { cyberpunkTheme } from '../../../styles/themes/cyberpunk.css'
import { professionalTheme } from '../../../styles/themes/professional.css'
import { root } from './AppShell.css'

interface AppShellProps {
  children: ReactNode
}

export function AppShell({ children }: AppShellProps) {
  const mode = useThemeStore((s) => s.mode)
  const themeClass = mode === 'cyberpunk' ? cyberpunkTheme : professionalTheme

  return (
    <div className={`${themeClass} ${root}`}>
      {children}
    </div>
  )
}
