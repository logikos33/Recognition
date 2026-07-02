/**
 * Painel lateral com lista de operações cadastradas e status em tempo real.
 * Exibido no modo de Visualização (não edição).
 * Status atualizado via props do useOperationLiveStatus.
 */
import { Settings, Trash2, Activity, AlertTriangle, XCircle, Clock } from 'lucide-react'
import type { OperationWithStatus } from '../../../types/operations'
import { getOperationIcon } from '../icons/operationTypeIcons'
import { vars } from '../../../styles/theme.css'

interface RegisteredToolsPanelProps {
  operations: OperationWithStatus[]
  onEdit: (op: OperationWithStatus) => void
  onDelete: (op: OperationWithStatus) => void
  loading?: boolean
}

const STATUS_CONFIG = {
  active: { label: 'ativa', color: vars.color.success, Icon: Activity },
  warning: { label: 'alerta', color: '#f59e0b', Icon: AlertTriangle },
  error: { label: 'erro', color: '#ef4444', Icon: XCircle },
  inactive: { label: 'inativa', color: vars.color.textSecondary, Icon: Clock },
}

function formatLastValue(value: unknown): string {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'boolean') return value ? 'true' : 'false'
  if (typeof value === 'number') return value.toFixed(2)
  if (typeof value === 'object') return JSON.stringify(value).slice(0, 40)
  return String(value)
}

function formatTimestamp(ts?: string): string {
  if (!ts) return ''
  const diff = Math.floor((Date.now() - new Date(ts).getTime()) / 1000)
  if (diff < 10) return 'agora'
  if (diff < 60) return `${diff}s atrás`
  if (diff < 3600) return `${Math.floor(diff / 60)}min atrás`
  return `${Math.floor(diff / 3600)}h atrás`
}

export function RegisteredToolsPanel({
  operations,
  onEdit,
  onDelete,
  loading = false,
}: RegisteredToolsPanelProps) {
  if (loading) {
    return (
      <div style={{ padding: 16, color: vars.color.textMuted, fontSize: 13 }}>
        Carregando operações...
      </div>
    )
  }

  if (operations.length === 0) {
    return (
      <div style={{ padding: 16, textAlign: 'center' }}>
        <div style={{ color: vars.color.textMuted, fontSize: 13, marginBottom: 8 }}>
          Nenhuma operação cadastrada
        </div>
        <div style={{ color: vars.color.textPrimary, fontSize: 12 }}>
          Clique em "Operação" no vídeo para criar
        </div>
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, padding: '8px 0' }}>
      <div style={{ padding: '0 12px 8px', borderBottom: `1px solid ${vars.color.borderDefault}`, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontSize: 11, fontWeight: 600, color: vars.color.textMuted, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
          Ferramentas cadastradas
        </span>
        <span style={{ fontSize: 11, color: vars.color.textMuted }}>{operations.length}</span>
      </div>

      {operations.map((op, idx) => {
        const status = op.live_status ?? op.status
        const cfg = STATUS_CONFIG[status] ?? STATUS_CONFIG.inactive
        const lastValue = op.live_last_value ?? op.last_value_json?.metric_value
        const ts = op.live_timestamp ?? op.last_evaluated_at

        return (
          <div
            key={op.id}
            style={{
              margin: '0 8px',
              padding: '10px 12px',
              background: vars.color.bgSurface,
              borderRadius: 6,
              border: `1px solid ${vars.color.borderDefault}`,
            }}
          >
            {/* Header row: ID + type icon + name */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
              <span style={{ fontFamily: 'monospace', fontSize: 11, color: vars.color.textMuted, minWidth: 20 }}>
                {String(idx + 1).padStart(2, '0')}
              </span>
              <span style={{ color: vars.color.textMuted, flexShrink: 0 }}>
                {getOperationIcon(op.type_id, { size: 14, color: vars.color.textMuted })}
              </span>
              <span style={{ fontSize: 13, fontWeight: 500, color: vars.color.textSecondary, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {op.name}
              </span>
            </div>

            {/* Status row */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6, fontSize: 12 }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: 4, color: cfg.color }}>
                <cfg.Icon size={12} />
                {cfg.label}
              </span>
              {lastValue !== undefined && lastValue !== null && (
                <>
                  <span style={{ color: vars.color.textPrimary }}>·</span>
                  <span style={{ color: vars.color.textSecondary, fontFamily: 'monospace', fontSize: 11 }}>
                    {formatLastValue(lastValue)}
                  </span>
                </>
              )}
              {ts && (
                <>
                  <span style={{ color: vars.color.textPrimary }}>·</span>
                  <span style={{ color: vars.color.textMuted, fontSize: 11 }}>{formatTimestamp(ts)}</span>
                </>
              )}
            </div>

            {/* Action buttons */}
            <div style={{ display: 'flex', gap: 6 }}>
              <button
                onClick={() => onEdit(op)}
                title="Editar operação"
                style={{
                  display: 'flex', alignItems: 'center', gap: 4,
                  padding: '4px 8px', background: 'transparent',
                  border: '1px solid #2a2a2a', borderRadius: 4,
                  color: vars.color.primary, fontSize: 11, cursor: 'pointer',
                }}
              >
                <Settings size={11} />
                Editar
              </button>
              <button
                onClick={() => onDelete(op)}
                title="Excluir operação"
                style={{
                  display: 'flex', alignItems: 'center', gap: 4,
                  padding: '4px 8px', background: 'transparent',
                  border: '1px solid #2a2a2a', borderRadius: 4,
                  color: '#ef4444', fontSize: 11, cursor: 'pointer',
                }}
              >
                <Trash2 size={11} />
                Excluir
              </button>
            </div>
          </div>
        )
      })}
    </div>
  )
}
