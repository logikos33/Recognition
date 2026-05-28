/**
 * Header do modo Edição — substitui header normal com Cancelar + Salvar.
 * Exibido quando usuário ativa modo de edição de operações.
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
        borderBottom: '1px solid #1e3a5f',
        background: 'rgba(59, 130, 246, 0.06)',
        minHeight: 52,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <div
          style={{
            width: 8,
            height: 8,
            borderRadius: '50%',
            background: '#3b82f6',
            boxShadow: '0 0 6px #3b82f6',
          }}
        />
        <span style={{ fontSize: 13, fontWeight: 600, color: '#60a5fa', letterSpacing: '0.05em' }}>
          MODO EDIÇÃO
        </span>
        {isDirty && (
          <span style={{ fontSize: 11, color: '#888', marginLeft: 4 }}>• alterações não salvas</span>
        )}
      </div>
      <div style={{ display: 'flex', gap: 8 }}>
        <button
          onClick={onCancel}
          disabled={saving}
          style={{
            padding: '7px 16px',
            background: 'transparent',
            border: '1px solid #333',
            borderRadius: 6,
            color: '#aaa',
            fontSize: 13,
            cursor: 'pointer',
          }}
        >
          Cancelar
        </button>
        <button
          onClick={onSave}
          disabled={saving}
          style={{
            padding: '7px 16px',
            background: '#3b82f6',
            border: 'none',
            borderRadius: 6,
            color: '#fff',
            fontSize: 13,
            fontWeight: 500,
            cursor: 'pointer',
            opacity: saving ? 0.7 : 1,
          }}
        >
          {saving ? 'Salvando...' : 'Salvar'}
        </button>
      </div>
    </div>
  )
}
