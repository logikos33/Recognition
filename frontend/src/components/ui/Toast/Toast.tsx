import { CheckCircle, XCircle, AlertTriangle, Info, X } from 'lucide-react'
import { useToastStore } from './useToast'
import { viewport, toast, toastIcon, toastBody, toastTitle, toastDescription, toastClose } from './Toast.css'
import type { ToastVariant } from './useToast'

const ICONS: Record<ToastVariant, typeof CheckCircle> = {
  success: CheckCircle,
  error: XCircle,
  warning: AlertTriangle,
  info: Info,
}

export function ToastProvider() {
  const toasts = useToastStore((s) => s.toasts)
  const dismiss = useToastStore((s) => s.dismiss)

  return (
    <div className={viewport} aria-live="polite" aria-label="Notificações">
      {toasts.map((t) => {
        const Icon = ICONS[t.variant]
        return (
          <div key={t.id} className={toast({ variant: t.variant })} role="status">
            <div className={toastIcon({ variant: t.variant })}>
              <Icon size={16} />
            </div>
            <div className={toastBody}>
              <div className={toastTitle}>{t.title}</div>
              {t.description && <div className={toastDescription}>{t.description}</div>}
            </div>
            <button className={toastClose} onClick={() => dismiss(t.id)} aria-label="Fechar">
              <X size={14} />
            </button>
          </div>
        )
      })}
    </div>
  )
}
