/**
 * Dashboard BI store — ordem, visibilidade dos widgets e período selecionado.
 * Persistido em localStorage (client-side only — preferência não vai ao banco
 * nesta fase). Espelha o padrão de cameraGridStore.ts.
 */
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export const WIDGET_IDS = [
  'alerts-timeline',
  'violations-distribution',
  'top-cameras',
  'recent-alerts',
  'event-log',
] as const

export type WidgetId = (typeof WIDGET_IDS)[number]

export const WIDGET_LABELS: Record<WidgetId, string> = {
  'alerts-timeline': 'Alertas ao longo do tempo',
  'violations-distribution': 'Distribuição de Violações',
  'top-cameras': 'Câmeras com mais alertas',
  'recent-alerts': 'Últimos Alertas',
  'event-log': 'Registro de Eventos',
}

export type DashboardPeriod = '24h' | '7d' | '30d'

const DEFAULT_ORDER: WidgetId[] = [...WIDGET_IDS]
const DEFAULT_PERIOD: DashboardPeriod = '7d'

interface DashboardState {
  widgetOrder: WidgetId[]
  hiddenWidgets: WidgetId[]
  period: DashboardPeriod

  // Actions
  moveWidget: (fromIndex: number, toIndex: number) => void
  toggleWidget: (id: WidgetId) => void
  setPeriod: (period: DashboardPeriod) => void
  resetLayout: () => void

  // Helpers
  isHidden: (id: WidgetId) => boolean
  getVisibleOrder: () => WidgetId[]
}

export const useDashboardStore = create<DashboardState>()(
  persist(
    (set, get) => ({
      widgetOrder: DEFAULT_ORDER,
      hiddenWidgets: [],
      period: DEFAULT_PERIOD,

      moveWidget: (fromIndex, toIndex) => {
        set((s) => {
          if (
            fromIndex < 0 ||
            toIndex < 0 ||
            fromIndex >= s.widgetOrder.length ||
            toIndex >= s.widgetOrder.length ||
            fromIndex === toIndex
          ) {
            return s
          }
          const next = [...s.widgetOrder]
          const [moved] = next.splice(fromIndex, 1)
          next.splice(toIndex, 0, moved)
          return { ...s, widgetOrder: next }
        })
      },

      toggleWidget: (id) => {
        set((s) => ({
          hiddenWidgets: s.hiddenWidgets.includes(id)
            ? s.hiddenWidgets.filter((w) => w !== id)
            : [...s.hiddenWidgets, id],
        }))
      },

      setPeriod: (period) => set({ period }),

      resetLayout: () =>
        set({
          widgetOrder: [...DEFAULT_ORDER],
          hiddenWidgets: [],
          period: DEFAULT_PERIOD,
        }),

      isHidden: (id) => get().hiddenWidgets.includes(id),

      getVisibleOrder: () => {
        const { widgetOrder, hiddenWidgets } = get()
        return widgetOrder.filter((id) => !hiddenWidgets.includes(id))
      },
    }),
    {
      name: 'recognition-dashboard-widgets',
      partialize: (state) => ({
        widgetOrder: state.widgetOrder,
        hiddenWidgets: state.hiddenWidgets,
        period: state.period,
      }),
    }
  )
)
