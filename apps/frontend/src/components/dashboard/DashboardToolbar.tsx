/**
 * DashboardToolbar — controles do dashboard BI (contrato de operabilidade):
 *  - Período: segmented control (valores fixos 24h/7d/30d, default 7d,
 *    aria-pressed) — afeta timeline, distribuição e top câmeras.
 *  - Personalizar: popover com checkbox por widget + Restaurar padrão.
 * Preferências persistem no navegador (dashboardStore/localStorage).
 * Todos os papéis do tenant podem personalizar (dashboard é read-only).
 */
import { SlidersHorizontal } from 'lucide-react'
import { Button } from '../ui/Button/Button'
import { Popover } from '../ui/Popover/Popover'
import {
  useDashboardStore,
  WIDGET_LABELS,
  type DashboardPeriod,
} from '../../stores/dashboardStore'
import {
  checkInput,
  checkRow,
  popoverBody,
  popoverFooter,
  popoverTitle,
  segmentButton,
  segmentButtonActive,
  segmented,
  toolbar,
  toolbarLabel,
  toolbarRight,
} from './DashboardToolbar.css'

const PERIOD_OPTIONS: Array<{ value: DashboardPeriod; label: string }> = [
  { value: '24h', label: 'Hoje (24h)' },
  { value: '7d', label: '7 dias' },
  { value: '30d', label: '30 dias' },
]

export function DashboardToolbar() {
  const period = useDashboardStore((s) => s.period)
  const setPeriod = useDashboardStore((s) => s.setPeriod)
  const widgetOrder = useDashboardStore((s) => s.widgetOrder)
  const hiddenWidgets = useDashboardStore((s) => s.hiddenWidgets)
  const toggleWidget = useDashboardStore((s) => s.toggleWidget)
  const resetLayout = useDashboardStore((s) => s.resetLayout)

  return (
    <div className={toolbar}>
      <span className={toolbarLabel}>Indicadores</span>

      <div className={toolbarRight}>
        <div className={segmented} role="group" aria-label="Período dos indicadores">
          {PERIOD_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              type="button"
              className={`${segmentButton}${period === opt.value ? ` ${segmentButtonActive}` : ''}`}
              aria-pressed={period === opt.value}
              onClick={() => setPeriod(opt.value)}
            >
              {opt.label}
            </button>
          ))}
        </div>

        <Popover
          align="end"
          trigger={
            <Button variant="ghost" size="sm">
              <SlidersHorizontal size={14} aria-hidden="true" />
              Personalizar
            </Button>
          }
        >
          <div className={popoverBody}>
            <span className={popoverTitle}>Widgets visíveis</span>
            {widgetOrder.map((id) => (
              <label key={id} className={checkRow}>
                <input
                  type="checkbox"
                  className={checkInput}
                  checked={!hiddenWidgets.includes(id)}
                  onChange={() => toggleWidget(id)}
                />
                <span>{WIDGET_LABELS[id]}</span>
              </label>
            ))}
            <div className={popoverFooter}>
              <Button variant="secondary" size="sm" onClick={resetLayout}>
                Restaurar padrão
              </Button>
            </div>
          </div>
        </Popover>
      </div>
    </div>
  )
}
