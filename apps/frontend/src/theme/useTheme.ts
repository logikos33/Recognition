/**
 * useTheme — hook para acesso ao modo de tema atual e controle.
 * Abstrai o themeStore para evitar importação direta em componentes.
 */
import { useThemeStore, type ThemeMode } from '../stores/themeStore'

export interface UseThemeReturn {
  mode: ThemeMode
  isAnimationsEnabled: boolean
  setMode: (mode: ThemeMode) => void
  toggleMode: () => void
}

export function useTheme(): UseThemeReturn {
  const mode = useThemeStore((s) => s.mode)
  const setMode = useThemeStore((s) => s.setMode)
  const toggleMode = useThemeStore((s) => s.toggleMode)
  const isAnimationsEnabled = useThemeStore((s) => s.isAnimationsEnabled())

  return { mode, isAnimationsEnabled, setMode, toggleMode }
}
