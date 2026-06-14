/**
 * Camera grid store — manages layout, cell assignments, presets, fullscreen.
 * Persists to localStorage.
 */
import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { GridLayout, GridPreset } from '../types/cameraGrid'
import { BUILT_IN_LAYOUTS } from '../types/cameraGrid'

interface CameraGridState {
  activeLayoutId: string
  cellAssignments: Record<number, string | null> // position -> cameraId
  customPresets: GridPreset[]
  expandedCell: number | null // position of fullscreen cell, null = grid view
  showLabels: boolean

  // Actions
  setLayout: (layoutId: string) => void
  assignCamera: (position: number, cameraId: string | null) => void
  swapCells: (fromPos: number, toPos: number) => void
  removeCamera: (position: number) => void
  expandCell: (position: number | null) => void
  toggleLabels: () => void

  // Presets
  savePreset: (name: string) => void
  deletePreset: (presetId: string) => void
  loadPreset: (presetId: string) => void

  // Helpers
  getActiveLayout: () => GridLayout
  getAllLayouts: () => GridLayout[]
}

const MAX_CUSTOM_PRESETS = 10

export const useCameraGridStore = create<CameraGridState>()(
  persist(
    (set, get) => ({
      activeLayoutId: '2x2',
      cellAssignments: {},
      customPresets: [],
      expandedCell: null,
      showLabels: true,

      setLayout: (layoutId) => {
        set({ activeLayoutId: layoutId, expandedCell: null })
      },

      assignCamera: (position, cameraId) => {
        set((s) => ({
          cellAssignments: { ...s.cellAssignments, [position]: cameraId },
        }))
      },

      swapCells: (fromPos, toPos) => {
        set((s) => {
          const a = s.cellAssignments
          const fromCam = a[fromPos] ?? null
          const toCam = a[toPos] ?? null
          return {
            cellAssignments: {
              ...a,
              [fromPos]: toCam,
              [toPos]: fromCam,
            },
          }
        })
      },

      removeCamera: (position) => {
        set((s) => ({
          cellAssignments: { ...s.cellAssignments, [position]: null },
        }))
      },

      expandCell: (position) => set({ expandedCell: position }),

      toggleLabels: () => set((s) => ({ showLabels: !s.showLabels })),

      savePreset: (name) => {
        const state = get()
        if (state.customPresets.length >= MAX_CUSTOM_PRESETS) return

        const preset: GridPreset = {
          id: `custom-${Date.now()}`,
          name,
          layout: state.getActiveLayout(),
          cameraAssignments: { ...state.cellAssignments },
          createdAt: new Date().toISOString(),
        }

        set((s) => ({
          customPresets: [...s.customPresets, preset],
        }))
      },

      deletePreset: (presetId) => {
        set((s) => ({
          customPresets: s.customPresets.filter((p) => p.id !== presetId),
        }))
      },

      loadPreset: (presetId) => {
        const preset = get().customPresets.find((p) => p.id === presetId)
        if (!preset) return
        set({
          activeLayoutId: preset.layout.id,
          cellAssignments: { ...preset.cameraAssignments },
          expandedCell: null,
        })
      },

      getActiveLayout: () => {
        const { activeLayoutId } = get()
        return BUILT_IN_LAYOUTS.find((l) => l.id === activeLayoutId) || BUILT_IN_LAYOUTS[1]
      },

      getAllLayouts: () => BUILT_IN_LAYOUTS,
    }),
    {
      name: 'epi-camera-grid',
      partialize: (state) => ({
        activeLayoutId: state.activeLayoutId,
        cellAssignments: state.cellAssignments,
        customPresets: state.customPresets,
        showLabels: state.showLabels,
      }),
    }
  )
)
