/**
 * Pareto de defeitos: barras horizontais ordenadas por frequência.
 */
import { paretoBar, paretoLabel, paretoCount, progressBar, progressFill } from './quality.css'
import type { ShiftReport } from '../types/quality'
import { vars } from '../../../styles/theme.css'

const DEFECT_COLORS: Record<number, string> = {
  1: vars.color.danger,
  2: '#FF8A65',
  3: '#FFB74D',
  4: '#F06292',
  5: '#CE93D8',
  6: '#4FC3F7',
  7: '#E57373',
  8: '#FFD54F',
}

interface DefectParetoProps {
  pareto: ShiftReport['defect_pareto']
  classLabels?: Record<number, string>
}

export function DefectPareto({ pareto, classLabels }: DefectParetoProps) {
  if (!pareto || pareto.length === 0) {
    return (
      <div style={{ color: vars.color.textMuted, fontSize: '13px', textAlign: 'center', padding: '16px 0' }}>
        Sem defeitos registrados neste turno.
      </div>
    )
  }

  const maxCount = Math.max(...pareto.map(p => p.count), 1)

  return (
    <div>
      {pareto.map(item => {
        const label = classLabels?.[item.defect_class] ?? item.label ?? `Classe ${item.defect_class}`
        const color = DEFECT_COLORS[item.defect_class] ?? vars.color.textMuted
        const width = (item.count / maxCount) * 100

        return (
          <div key={item.defect_class} className={paretoBar}>
            <span className={paretoLabel} title={label}>{label}</span>
            <div className={progressBar} style={{ flex: 1 }}>
              <div
                className={progressFill}
                style={{ width: `${width}%`, background: color }}
              />
            </div>
            <span className={paretoCount}>{item.count}</span>
            <span style={{ fontSize: '11px', color: vars.color.textMuted, minWidth: '36px', textAlign: 'right' }}>
              {(item.pct * 100).toFixed(0)}%
            </span>
          </div>
        )
      })}
    </div>
  )
}
