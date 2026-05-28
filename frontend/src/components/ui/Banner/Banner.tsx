import type { ReactNode } from 'react'
import { X } from 'lucide-react'
import { banner, bannerMessage, bannerClose } from './Banner.css'

interface BannerProps {
  variant?: 'info' | 'success' | 'warning' | 'danger'
  icon?: ReactNode
  children: ReactNode
  onDismiss?: () => void
  className?: string
}

export function Banner({ variant = 'info', icon, children, onDismiss, className }: BannerProps) {
  return (
    <div className={`${banner({ variant })}${className ? ` ${className}` : ''}`} role="alert">
      {icon}
      <span className={bannerMessage}>{children}</span>
      {onDismiss && (
        <button className={bannerClose} onClick={onDismiss} aria-label="Fechar aviso">
          <X size={14} />
        </button>
      )}
    </div>
  )
}
