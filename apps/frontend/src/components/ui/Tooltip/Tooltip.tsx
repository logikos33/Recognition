import type { ReactNode } from 'react'
import * as RadixTooltip from '@radix-ui/react-tooltip'
import { content } from './Tooltip.css'

interface TooltipProps {
  children: ReactNode
  /** Texto simples (compat). Ignorado quando `content` é informado. */
  label?: string
  /** Conteúdo rico (título + corpo). Tem precedência sobre `label`. */
  content?: ReactNode
  side?: 'top' | 'right' | 'bottom' | 'left'
  delayDuration?: number
}

export function Tooltip({ children, label, content: richContent, side = 'top', delayDuration = 300 }: TooltipProps) {
  return (
    <RadixTooltip.Provider delayDuration={delayDuration}>
      <RadixTooltip.Root>
        <RadixTooltip.Trigger asChild>{children}</RadixTooltip.Trigger>
        <RadixTooltip.Portal>
          <RadixTooltip.Content className={content} side={side} sideOffset={6}>
            {richContent ?? label}
          </RadixTooltip.Content>
        </RadixTooltip.Portal>
      </RadixTooltip.Root>
    </RadixTooltip.Provider>
  )
}
