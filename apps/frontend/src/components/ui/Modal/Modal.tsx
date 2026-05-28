import type { ReactNode } from 'react'
import * as Dialog from '@radix-ui/react-dialog'
import { X } from 'lucide-react'
import { overlay, content, header, title, closeButton, body, footer } from './Modal.css'

interface ModalProps {
  open: boolean
  onClose: () => void
  title: string
  children: ReactNode
  footer?: ReactNode
  maxWidth?: string
}

export function Modal({ open, onClose, title: titleText, children, footer: footerContent, maxWidth }: ModalProps) {
  return (
    <Dialog.Root open={open} onOpenChange={(v) => !v && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className={overlay} />
        <Dialog.Content
          className={content}
          style={maxWidth ? { maxWidth } : undefined}
          onInteractOutside={onClose}
        >
          <div className={header}>
            <Dialog.Title className={title}>{titleText}</Dialog.Title>
            <Dialog.Close asChild>
              <button className={closeButton} aria-label="Fechar">
                <X size={18} />
              </button>
            </Dialog.Close>
          </div>

          <div className={body}>{children}</div>

          {footerContent && <div className={footer}>{footerContent}</div>}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
