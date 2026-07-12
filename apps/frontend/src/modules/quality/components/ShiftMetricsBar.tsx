/**
 * Barra de métricas do turno atual: Total, OK, NOK, Taxa NOK.
 */
import { metricsBar, metricItem, metricLabel, metricValue, metricValueOk, metricValueNok } from './quality.css'
import type { InspectionSummary } from '../types/quality'
import { vars } from '../../../styles/theme.css'

interface ShiftMetricsBarProps {
  summary: InspectionSummary | null
  loading?: boolean
}

export function ShiftMetricsBar({ summary, loading }: ShiftMetricsBarProps) {
  const shiftLabel: Record<string, string> = {
    morning: 'Manhã',
    afternoon: 'Tarde',
    night: 'Noite',
  }

  return (
    <div className={metricsBar}>
      <div className={metricItem}>
        <span className={metricLabel}>
          Turno {summary ? shiftLabel[summary.shift] ?? summary.shift : '—'}
        </span>
        <span className={metricValue}>
          {loading ? '…' : (summary?.total ?? 0).toLocaleString()}
        </span>
        <span style={{ fontSize: '11px', color: vars.color.textSecondary }}>inspeções</span>
      </div>

      <div className={metricItem}>
        <span className={metricLabel}>OK</span>
        <span className={metricValueOk}>
          {loading ? '…' : (summary?.ok ?? 0).toLocaleString()}
        </span>
      </div>

      <div className={metricItem}>
        <span className={metricLabel}>NOK</span>
        <span className={metricValueNok}>
          {loading ? '…' : (summary?.nok ?? 0).toLocaleString()}
        </span>
      </div>

      <div className={metricItem}>
        <span className={metricLabel}>Taxa NOK</span>
        <span className={metricValueNok}>
          {loading
            ? '…'
            : summary
            ? `${(summary.nok_rate * 100).toFixed(1)}%`
            : '—'}
        </span>
      </div>
    </div>
  )
}
