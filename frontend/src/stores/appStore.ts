/**
 * App store — sidebar state + selected module.
 * Persists selectedModule to localStorage so it survives reload.
 */
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type ModuleCode = 'epi' | 'fueling' | 'quality' | null

interface AppState {
  sidebarOpen: boolean
  selectedModule: ModuleCode
  openSidebar: () => void
  closeSidebar: () => void
  toggleSidebar: () => void
  setSelectedModule: (mod: ModuleCode) => void
  clearModule: () => void
}

// Migrate persisted state from old localStorage key to new name (one-time, silent)
const OLD_KEY = 'epi-monitor-app'
const NEW_KEY = 'recognition-app'
if (typeof window !== 'undefined') {
  const legacy = localStorage.getItem(OLD_KEY)
  if (legacy && !localStorage.getItem(NEW_KEY)) {
    localStorage.setItem(NEW_KEY, legacy)
  }
  localStorage.removeItem(OLD_KEY)
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      sidebarOpen: false,
      selectedModule: null,

      openSidebar: () => set({ sidebarOpen: true }),
      closeSidebar: () => set({ sidebarOpen: false }),
      toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
      setSelectedModule: (mod) => set({ selectedModule: mod }),
      clearModule: () => set({ selectedModule: null }),
    }),
    {
      name: NEW_KEY,
      partialize: (state) => ({ selectedModule: state.selectedModule }),
    }
  )
)
