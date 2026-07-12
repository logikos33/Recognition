/**
 * AppDrawer — contêiner padrão gaveta lateral (deliverable l).
 *
 * Abre sobre o contexto atual sem recarregar a página.
 * Fechar com Escape, clique no overlay ou botão X.
 *
 * Props:
 *   isOpen   — controla visibilidade
 *   onClose  — callback ao fechar
 *   title    — texto no cabeçalho
 *   size     — largura: 'sm' | 'md' | 'lg' | 'xl'
 *   children — conteúdo interno
 */
import type { ReactNode } from 'react'
import * as Dialog from '@radix-ui/react-dialog'
import { X } from 'lucide-react'
import { overlay, drawer, drawerHeader, drawerTitle, closeBtn, drawerBody } from './AppDrawer.css'

export interface AppDrawerProps {
  isOpen: boolean
  onClose: () => void
  title: string
  size?: 'sm' | 'md' | 'lg' | 'xl'
  children: ReactNode
}

export function AppDrawer({ isOpen, onClose, title, size = 'md', children }: AppDrawerProps) {
  return (
    <Dialog.Root open={isOpen} onOpenChange={(open) => { if (!open) onClose() }}>
      <Dialog.Portal>
        <Dialog.Overlay className={overlay} />
        <Dialog.Content
          className={drawer({ size })}
          aria-describedby={undefined}
          onInteractOutside={onClose}
          onEscapeKeyDown={onClose}
        >
          <div className={drawerHeader}>
            <Dialog.Title className={drawerTitle}>{title}</Dialog.Title>
            <Dialog.Close asChild>
              <button className={closeBtn} aria-label="Fechar gaveta">
                <X size={16} />
              </button>
            </Dialog.Close>
          </div>
          <div className={drawerBody}>{children}</div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
