import { Modal } from '../Modal/Modal'
import { Button } from '../Button/Button'

interface ConfirmDialogProps {
  open: boolean
  onClose: () => void
  onConfirm: () => void
  title: string
  description: string
  confirmLabel?: string
  cancelLabel?: string
  variant?: 'danger' | 'primary'
  loading?: boolean
}

export function ConfirmDialog({
  open, onClose, onConfirm, title, description,
  confirmLabel = 'Confirmar', cancelLabel = 'Cancelar',
  variant = 'danger', loading = false,
}: ConfirmDialogProps) {
  return (
    <Modal
      open={open}
      onClose={onClose}
      title={title}
      maxWidth="400px"
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={loading}>{cancelLabel}</Button>
          <Button variant={variant} onClick={onConfirm} disabled={loading}>
            {loading ? 'Aguarde...' : confirmLabel}
          </Button>
        </>
      }
    >
      <p style={{ margin: 0, fontSize: 14, lineHeight: 1.6 }}>{description}</p>
    </Modal>
  )
}
