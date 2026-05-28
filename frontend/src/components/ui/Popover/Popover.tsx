import type { ReactNode } from 'react'
import * as RadixPopover from '@radix-ui/react-popover'
import { content } from './Popover.css'

interface PopoverProps {
  trigger: ReactNode
  children: ReactNode
  side?: 'top' | 'right' | 'bottom' | 'left'
  align?: 'start' | 'center' | 'end'
  open?: boolean
  onOpenChange?: (open: boolean) => void
}

export function Popover({ trigger, children, side = 'bottom', align = 'start', open, onOpenChange }: PopoverProps) {
  return (
    <RadixPopover.Root open={open} onOpenChange={onOpenChange}>
      <RadixPopover.Trigger asChild>{trigger}</RadixPopover.Trigger>
      <RadixPopover.Portal>
        <RadixPopover.Content className={content} side={side} align={align} sideOffset={8}>
          {children}
        </RadixPopover.Content>
      </RadixPopover.Portal>
    </RadixPopover.Root>
  )
}
