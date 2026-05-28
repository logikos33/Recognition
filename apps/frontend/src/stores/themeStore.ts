/**
 * Theme store — persisted via localStorage.
 * Sprint 1 (Recognition rebrand): recognition-dark é o novo padrão.
 * Modos legacy (cyberpunk/professional) mantidos para compatibilidade.
 * Chave do localStorage será renomeada em Sprint 3 junto com o rebrand global.
 */
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type ThemeMode = 'recognition-dark' | 'cyberpunk' | 'professional'

interface ThemeState {
  mode: ThemeMode
  setMode: (mode: ThemeMode) => void
  toggleMode: () => void
  isAnimationsEnabled: () => boolean
}

export const useThemeStore = create<ThemeState>()(
  persist(
    (set, get) => ({
      mode: 'recognition-dark',

      setMode: (mode) => set({ mode }),

      // Recognition dark ↔ Professional (sem animações)
      toggleMode: () =>
        set((state) => ({
          mode: state.mode === 'professional' ? 'recognition-dark' : 'professional',
        })),

      isAnimationsEnabled: () => get().mode !== 'professional',
    }),
    { name: 'recognition-theme' }
  )
)
