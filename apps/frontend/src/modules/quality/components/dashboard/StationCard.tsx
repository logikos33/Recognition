import type { ReactNode } from 'react'
import { StepTimer } from './StepTimer'
import { vars } from '../../../../styles/theme.css'
import type { StationLive } from '../../types/qualityDashboard'

const STATUS_COLOR: Record<StationLive['status'], string> = {
  ok:       vars.color.success,
  warning:  '#FFB74D',
  critical: vars.color.danger,
  offline:  vars.color.textMuted,
}

const STATUS_LABEL: Record<StationLive['status'], string> = {
  ok:       'OK',
  warning:  'Atenção',
  critical: 'Crítico',
  offline:  'Offline',
}

interface StationCardProps {
  station: StationLive
}

export function StationCard({ station }: StationCardProps) {
  const color = STATUS_COLOR[station.status]
  const isOffline = station.status === 'offline'

  return (
    <div style={{
      border: `1px solid ${isOffline ? vars.color.borderSubtle : color + '40'}`,
      borderRadius: 14,
      overflow: 'hidden',
      background: vars.color.bgCard,
      opacity: isOffline ? 0.6 : 1,
      display: 'flex',
      flexDirection: 'column',
    }}>
      {/* Placeholder de vídeo */}
      <div style={{
        aspectRatio: '16/9',
        background: vars.color.bgBase,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        position: 'relative',
        borderBottom: `1px solid ${vars.color.borderSubtle}`,
      }}>
        <span style={{ color: vars.color.textDim, fontSize: 13 }}>
          {station.camera_ids.length > 0
            ? `${station.camera_ids.length} câmera(s) — stream v2`
            : 'Sem câmera atribuída'}
        </span>
        {station.camera_ids.length > 0 && (
          <span style={{
            position: 'absolute', top: 8, right: 8,
            background: 'rgba(0,0,0,0.55)', color: vars.color.textSecondary,
            fontSize: 11, padding: '2px 8px', borderRadius: 20,
          }}>
            {station.camera_ids.length}x cam
          </span>
        )}
      </div>

      {/* Dados operacionais */}
      <div style={{ padding: '14px 16px', display: 'flex', flexDirection: 'column', gap: 0 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
          <span style={{ fontWeight: 700, fontSize: 15, color: vars.color.textPrimary }}>
            {station.name || station.station_code}
          </span>
          <span style={{
            fontSize: 11, fontWeight: 600,
            color: color, background: color + '18',
            padding: '3px 10px', borderRadius: 20,
          }}>
            ● {STATUS_LABEL[station.status]}
          </span>
        </div>

        <div style={{ height: 1, background: vars.color.borderSubtle, marginBottom: 10 }} />

        {station.active_piece ? (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <tbody>
              <Row label="Operador" value={station.operator?.name ?? '—'} />
              <Row label="OP" value={station.active_piece.op ?? '—'} />
              <Row label="Peça" value={station.active_piece.code ?? '—'} />
              <Row label="Etapa" value={station.active_piece.status_label} bold />
              <Row
                label="Tempo na etapa"
                value={
                  <StepTimer
                    startedAt={station.active_piece.started_at}
                    warn={station.status === 'warning' || station.status === 'critical'}
                  />
                }
              />
              <Row
                label="Turno OK / NOK"
                value={`${station.shift_stats.ok} / ${station.shift_stats.nok}`}
              />
            </tbody>
          </table>
        ) : (
          <div style={{ textAlign: 'center', color: vars.color.textMuted, fontSize: 13, padding: '10px 0' }}>
            {isOffline ? 'Estação offline' : 'Aguardando peça'}
          </div>
        )}
      </div>
    </div>
  )
}

function Row({
  label,
  value,
  bold = false,
}: {
  label: string
  value: ReactNode
  bold?: boolean
}) {
  return (
    <tr>
      <td style={{ color: vars.color.textSecondary, paddingBottom: 6, width: '45%', verticalAlign: 'top' }}>
        {label}
      </td>
      <td style={{
        color: bold ? vars.color.textPrimary : vars.color.textSecondary,
        fontWeight: bold ? 600 : 400,
        paddingBottom: 6,
        verticalAlign: 'top',
      }}>
        {value}
      </td>
    </tr>
  )
}
