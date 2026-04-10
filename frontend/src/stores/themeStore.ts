/**
 * Theme store — persisted via localStorage.
 * Default: cyberpunk (gamer mode with animations).
 */
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type ThemeMode = 'cyberpunk' | 'professional'

interface ThemeState {
  mode: ThemeMode
  setMode: (mode: ThemeMode) => void
  toggleMode: () => void
  isAnimationsEnabled: () => boolean
}

export const useThemeStore = create<ThemeState>()(
  persist(
    (set, get) => ({
      mode: 'cyberpunk',

      setMode: (mode) => set({ mode }),

      toggleMode: () =>
        set((state) => ({
          mode: state.mode === 'cyberpunk' ? 'professional' : 'cyberpunk',
        })),

      isAnimationsEnabled: () => get().mode === 'cyberpunk',
    }),
    { name: 'epi-monitor-theme' }
  )
)
