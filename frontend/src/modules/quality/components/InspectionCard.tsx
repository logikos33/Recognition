/**
 * Card compacto de inspeção para listagem e dashboard.
 */
import { card } from './quality.css'
import { ResultBadge, FeedbackBadge, DefectBadge } from './DefectBadge'
import type { QualityInspection, QualityClass } from '../types/quality'

interface InspectionCardProps {
  inspection: QualityInspection
  classes?: QualityClass[]
  onClick?: () => void
}

export function InspectionCard({ inspection, classes, onClick }: InspectionCardProps) {
  const defectClass = classes?.find(c => c.id === inspection.defect_class)

  const time = new Date(inspection.created_at).toLocaleTimeString('pt-BR', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })

  return (
    <div
      className={card}
      onClick={onClick}
      style={{ cursor: onClick ? 'pointer' : 'default', display: 'flex', flexDirection: 'column', gap: '8px' }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <ResultBadge result={inspection.result} />
        <span style={{ fontSize: '11px', color: '#888' }}>{time}</span>
      </div>

      <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
        {defectClass && (
          <DefectBadge
            classId={defectClass.id}
            label={defectClass.label}
            color={defectClass.color}
          />
        )}
        <FeedbackBadge status={inspection.feedback_status} />
      </div>

      {inspection.production_order && (
        <div style={{ fontSize: '11px', color: '#888' }}>
          Lote: <strong style={{ color: '#ccc' }}>{inspection.production_order}</strong>
        </div>
      )}

      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: '#888' }}>
        <span>Conf: <strong style={{ color: '#ccc' }}>{(inspection.confidence * 100).toFixed(0)}%</strong></span>
        {inspection.rolling_nok_rate_1h !== null && (
          <span>
            Taxa 1h: <strong style={{ color: (inspection.rolling_nok_rate_1h ?? 0) > 0.1 ? '#EF5350' : '#43D186' }}>
              {((inspection.rolling_nok_rate_1h ?? 0) * 100).toFixed(1)}%
            </strong>
          </span>
        )}
      </div>

      {inspection.is_cep_alert && (
        <div style={{ fontSize: '11px', color: '#EF5350', fontWeight: 600 }}>
          ⚠ Processo fora de controle (CEP)
        </div>
      )}
    </div>
  )
}
