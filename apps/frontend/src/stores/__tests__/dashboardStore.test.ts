/**
 * dashboardStore — reorder, hide/show, período, reset e persistência.
 *
 * O jsdom deste ambiente expõe localStorage sem métodos funcionais — o mock
 * em memória é instalado via vi.hoisted ANTES do módulo do store carregar,
 * para o zustand/persist gravar de verdade no round-trip.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.hoisted(() => {
  const store = new Map<string, string>()
  const mock: Storage = {
    getItem: (k: string) => (store.has(k) ? (store.get(k) as string) : null),
    setItem: (k: string, v: string) => {
      store.set(k, String(v))
    },
    removeItem: (k: string) => {
      store.delete(k)
    },
    clear: () => {
      store.clear()
    },
    key: (i: number) => Array.from(store.keys())[i] ?? null,
    get length() {
      return store.size
    },
  }
  Object.defineProperty(globalThis, 'localStorage', {
    value: mock,
    configurable: true,
    writable: true,
  })
})

import { useDashboardStore, WIDGET_IDS } from '../dashboardStore'

const STORAGE_KEY = 'recognition-dashboard-widgets'

const DEFAULT_ORDER = [...WIDGET_IDS]

beforeEach(() => {
  localStorage.clear()
  useDashboardStore.getState().resetLayout()
})

describe('dashboardStore — layout', () => {
  it('começa com a ordem padrão, sem widgets ocultos e período 7d', () => {
    const s = useDashboardStore.getState()
    expect(s.widgetOrder).toEqual(DEFAULT_ORDER)
    expect(s.hiddenWidgets).toEqual([])
    expect(s.period).toBe('7d')
  })

  it('moveWidget reordena da posição origem para destino', () => {
    useDashboardStore.getState().moveWidget(0, 2)
    const order = useDashboardStore.getState().widgetOrder
    expect(order[2]).toBe('alerts-timeline')
    expect(order).toHaveLength(DEFAULT_ORDER.length)
    expect([...order].sort()).toEqual([...DEFAULT_ORDER].sort())
  })

  it('moveWidget ignora índices inválidos', () => {
    const before = useDashboardStore.getState().widgetOrder
    useDashboardStore.getState().moveWidget(-1, 2)
    useDashboardStore.getState().moveWidget(0, 99)
    expect(useDashboardStore.getState().widgetOrder).toEqual(before)
  })

  it('toggleWidget oculta e reexibe', () => {
    const { toggleWidget } = useDashboardStore.getState()
    toggleWidget('top-cameras')
    expect(useDashboardStore.getState().hiddenWidgets).toContain('top-cameras')
    expect(useDashboardStore.getState().isHidden('top-cameras')).toBe(true)

    useDashboardStore.getState().toggleWidget('top-cameras')
    expect(useDashboardStore.getState().hiddenWidgets).not.toContain('top-cameras')
  })

  it('getVisibleOrder exclui widgets ocultos preservando a ordem', () => {
    useDashboardStore.getState().toggleWidget('violations-distribution')
    const visible = useDashboardStore.getState().getVisibleOrder()
    expect(visible).toEqual(
      DEFAULT_ORDER.filter((id) => id !== 'violations-distribution')
    )
  })

  it('setPeriod altera o período', () => {
    useDashboardStore.getState().setPeriod('30d')
    expect(useDashboardStore.getState().period).toBe('30d')
  })

  it('resetLayout restaura ordem, visibilidade e período padrão', () => {
    const s = useDashboardStore.getState()
    s.moveWidget(0, 4)
    s.toggleWidget('event-log')
    s.setPeriod('24h')

    useDashboardStore.getState().resetLayout()

    const after = useDashboardStore.getState()
    expect(after.widgetOrder).toEqual(DEFAULT_ORDER)
    expect(after.hiddenWidgets).toEqual([])
    expect(after.period).toBe('7d')
  })
})

describe('dashboardStore — persistência (round-trip)', () => {
  it('persiste ordem/ocultos/período em localStorage na chave correta', () => {
    const s = useDashboardStore.getState()
    s.moveWidget(0, 1)
    s.toggleWidget('recent-alerts')
    s.setPeriod('24h')

    const raw = localStorage.getItem(STORAGE_KEY)
    expect(raw).toBeTruthy()
    const persisted = JSON.parse(raw as string)
    expect(persisted.state.widgetOrder[1]).toBe('alerts-timeline')
    expect(persisted.state.hiddenWidgets).toContain('recent-alerts')
    expect(persisted.state.period).toBe('24h')
  })

  it('reidrata o estado persistido (simula F5)', async () => {
    useDashboardStore.getState().toggleWidget('event-log')
    useDashboardStore.getState().setPeriod('30d')

    // Simula reload: zustand persist relê o storage no rehydrate()
    await useDashboardStore.persist.rehydrate()

    const after = useDashboardStore.getState()
    expect(after.hiddenWidgets).toContain('event-log')
    expect(after.period).toBe('30d')
  })
})
