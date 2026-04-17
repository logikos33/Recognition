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
      name: 'epi-monitor-app',
      partialize: (state) => ({ selectedModule: state.selectedModule }),
    }
  )
)
