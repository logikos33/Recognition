/**
 * AppShell — aplica classe de tema Vanilla Extract ao root da app.
 * Sprint 1: recognition-dark é o tema padrão; legacy modes mantidos.
 */
import type { ReactNode } from 'react'
import { useEffect } from 'react'
import { useThemeStore } from '../../../stores/themeStore'
import { recognitionDarkTheme } from '../../../theme/tokens/recognition-dark.css'
import { cyberpunkTheme } from '../../../styles/themes/cyberpunk.css'
import { professionalTheme } from '../../../styles/themes/professional.css'
import { root } from './AppShell.css'

const THEME_CLASS_MAP = {
  'recognition-dark': recognitionDarkTheme,
  cyberpunk: cyberpunkTheme,
  professional: professionalTheme,
} as const

interface AppShellProps {
  children: ReactNode
}

export function AppShell({ children }: AppShellProps) {
  const mode = useThemeStore((s) => s.mode)
  const themeClass = THEME_CLASS_MAP[mode] ?? recognitionDarkTheme

  // Expõe o modo como data-attribute para uso em CSS seletores se necessário
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', mode)
  }, [mode])

  return (
    <div className={`${themeClass} ${root}`}>
      {children}
    </div>
  )
}
