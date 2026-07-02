/**
 * Catálogo de tipos de operação disponíveis (exibido no modo Edição).
 * Cards clicáveis que disparam o modal de criação.
 */
import type { OperationType } from '../../../types/operations'
import { getOperationIcon } from '../icons/operationTypeIcons'
import { vars } from '../../../styles/theme.css'

interface OperationCatalogPanelProps {
  types: OperationType[]
  onSelectType: (type: OperationType) => void
  loading?: boolean
}

export function OperationCatalogPanel({
  types,
  onSelectType,
  loading = false,
}: OperationCatalogPanelProps) {
  if (loading) {
    return (
      <div style={{ padding: 16, color: vars.color.textMuted, fontSize: 13 }}>
        Carregando tipos...
      </div>
    )
  }

  const canonical = types.filter(t => ['position', 'overlap_fixed', 'overlap_dynamic', 'count_static'].includes(t.type_id))
  const specific = types.filter(t => !['position', 'overlap_fixed', 'overlap_dynamic', 'count_static'].includes(t.type_id))

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 0, padding: '8px 0' }}>
      {/* Seção: canônicos */}
      <div style={{ padding: '0 12px 8px', borderBottom: `1px solid ${vars.color.borderDefault}` }}>
        <span style={{ fontSize: 11, fontWeight: 600, color: vars.color.textMuted, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
          Tipos canônicos
        </span>
      </div>

      <div style={{ padding: '8px 8px 12px', display: 'flex', flexDirection: 'column', gap: 6 }}>
        {canonical.map(type => (
          <TypeCard key={type.type_id} type={type} onClick={() => onSelectType(type)} />
        ))}
      </div>

      {/* Seção: específicos do módulo */}
      {specific.length > 0 && (
        <>
          <div style={{ padding: '8px 12px', borderTop: `1px solid ${vars.color.borderDefault}`, borderBottom: `1px solid ${vars.color.borderDefault}` }}>
            <span style={{ fontSize: 11, fontWeight: 600, color: vars.color.textMuted, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
              Específicos do módulo
            </span>
          </div>
          <div style={{ padding: '8px 8px 12px', display: 'flex', flexDirection: 'column', gap: 6 }}>
            {specific.map(type => (
              <TypeCard key={type.type_id} type={type} onClick={() => onSelectType(type)} />
            ))}
          </div>
        </>
      )}

      {types.length === 0 && (
        <div style={{ padding: 16, color: vars.color.textMuted, fontSize: 12, textAlign: 'center' }}>
          Nenhum tipo disponível para este módulo
        </div>
      )}
    </div>
  )
}

function TypeCard({ type, onClick }: { type: OperationType; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      style={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: 10,
        padding: '10px 12px',
        background: vars.color.bgSurface,
        border: `1px solid ${vars.color.borderDefault}`,
        borderRadius: 6,
        color: 'inherit',
        cursor: 'pointer',
        textAlign: 'left',
        width: '100%',
        transition: 'background 0.15s',
      }}
      onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.background = '#181818' }}
      onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.background = vars.color.bgSurface }}
    >
      <span style={{ color: vars.color.primary, flexShrink: 0, marginTop: 1 }}>
        {getOperationIcon(type.type_id, { size: 18, color: vars.color.primary })}
      </span>
      <div>
        <div style={{ fontSize: 13, fontWeight: 500, color: vars.color.textSecondary, marginBottom: 2 }}>
          {type.type_label}
        </div>
        {type.description && (
          <div style={{ fontSize: 11, color: vars.color.textMuted, lineHeight: 1.4 }}>
            {type.description}
          </div>
        )}
      </div>
    </button>
  )
}
