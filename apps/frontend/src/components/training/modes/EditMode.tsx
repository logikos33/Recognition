import { vars } from '../../../styles/theme.css'
import { Button } from '../../ui/Button/Button'
/**
 * Header do modo Edição — substitui header normal com Cancelar + Salvar.
 * Exibido quando usuário ativa modo de edição de operações.
 * task-063: cores hardcoded (#1e3a5f / rgba azul) → tokens WS1; botões
 * migrados para o ui/Button (hover e contraste resolvidos pelo tema).
 */

interface EditModeProps {
  onCancel: () => void
  onSave: () => void
  isDirty?: boolean
  saving?: boolean
}

export function EditMode({ onCancel, onSave, isDirty = false, saving = false }: EditModeProps) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '12px 20px',
        borderBottom: `1px solid ${vars.color.borderDefault}`,
        background: vars.color.primaryAlpha,
        minHeight: 52,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <div
          style={{
            width: 8,
            height: 8,
            borderRadius: '50%',
            background: vars.color.primary,
            boxShadow: `0 0 6px ${vars.color.primary}`,
          }}
        />
        <span style={{ fontSize: 13, fontWeight: 600, color: vars.color.primaryLight, letterSpacing: '0.05em' }}>
          MODO EDIÇÃO
        </span>
        {isDirty && (
          <span style={{ fontSize: 11, color: vars.color.textMuted, marginLeft: 4 }}>• alterações não salvas</span>
        )}
      </div>
      <div style={{ display: 'flex', gap: 8 }}>
        <Button size="sm" variant="secondary" onClick={onCancel} disabled={saving}>
          Cancelar
        </Button>
        <Button size="sm" variant="primary" onClick={onSave} disabled={saving} loading={saving}>
          {saving ? 'Salvando...' : 'Salvar'}
        </Button>
      </div>
    </div>
  )
}
