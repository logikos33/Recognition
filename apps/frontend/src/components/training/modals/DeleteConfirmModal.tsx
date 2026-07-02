/**
 * Modal de confirmação de exclusão com regra de digitação.
 * - Sem histórico: apenas Cancelar + Confirmar
 * - Com histórico: obriga digitar o nome da operação antes de confirmar
 */
import { useState } from 'react'
import { Modal } from '../../ui/Modal/Modal'
import { Button } from '../../ui/Button/Button'
import { AlertTriangle } from 'lucide-react'
import { vars } from '../../../styles/theme.css'

interface DeleteConfirmModalProps {
  open: boolean
  onClose: () => void
  onConfirm: (confirmName?: string) => Promise<void>
  operationName: string
  resultCount?: number
  loading?: boolean
}

export function DeleteConfirmModal({
  open,
  onClose,
  onConfirm,
  operationName,
  resultCount = 0,
  loading = false,
}: DeleteConfirmModalProps) {
  const [inputName, setInputName] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const requiresTyping = resultCount > 0
  const canConfirm = !requiresTyping || inputName === operationName

  const handleClose = () => { setInputName(''); setError(null); onClose() }

  const handleConfirm = async () => {
    if (!canConfirm) return
    setSubmitting(true)
    setError(null)
    try {
      await onConfirm(requiresTyping ? inputName : undefined)
      setInputName('')
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao excluir operação')
    } finally {
      setSubmitting(false)
    }
  }

  const footer = (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
      <div style={{ flex: 1 }}>
        {error && <span style={{ color: vars.color.danger, fontSize: 12 }}>{error}</span>}
      </div>
      <div style={{ display: 'flex', gap: 8 }}>
        <Button variant="ghost" onClick={handleClose} disabled={submitting}>
          Cancelar
        </Button>
        <Button
          variant="danger"
          onClick={handleConfirm}
          disabled={!canConfirm || loading}
          loading={submitting}
        >
          {submitting ? 'Excluindo...' : 'Confirmar exclusão'}
        </Button>
      </div>
    </div>
  )

  return (
    <Modal open={open} onClose={handleClose} title="Confirmar exclusão" footer={footer} maxWidth="440px">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div style={{ display: 'flex', gap: 10, padding: 12, background: vars.color.dangerMuted, borderRadius: 6, border: `1px solid ${vars.color.danger}` }}>
          <AlertTriangle size={16} color={vars.color.danger} style={{ flexShrink: 0, marginTop: 2 }} />
          <div>
            <div style={{ fontSize: 13, color: vars.color.textSecondary, marginBottom: 4 }}>
              Esta ação <strong>não pode ser desfeita</strong>.
            </div>
            <div style={{ fontSize: 12, color: vars.color.textMuted }}>
              A operação "<strong style={{ color: vars.color.textSecondary }}>{operationName}</strong>" será permanentemente removida.
              {resultCount > 0 && ` O histórico de ${resultCount} resultado(s) também será descartado.`}
            </div>
          </div>
        </div>

        {requiresTyping && (
          <div>
            <label style={{ display: 'block', marginBottom: 6, fontSize: 13, color: vars.color.textSecondary }}>
              Digite o nome da operação para confirmar:
            </label>
            <input
              value={inputName}
              onChange={e => setInputName(e.target.value)}
              placeholder={operationName}
              autoFocus
              style={{
                width: '100%',
                padding: '8px 10px',
                background: vars.color.bgSurface,
                border: `1px solid ${inputName === operationName ? vars.color.success : vars.color.borderDefault}`,
                borderRadius: 6,
                color: vars.color.textPrimary,
                fontSize: 13,
                boxSizing: 'border-box',
              }}
            />
            {inputName.length > 0 && inputName !== operationName && (
              <div style={{ fontSize: 11, color: vars.color.danger, marginTop: 4 }}>
                Nome não confere
              </div>
            )}
          </div>
        )}
      </div>
    </Modal>
  )
}
