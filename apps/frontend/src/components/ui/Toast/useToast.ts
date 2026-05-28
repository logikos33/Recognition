import { create } from 'zustand'

export type ToastVariant = 'success' | 'error' | 'warning' | 'info'

export interface ToastItem {
  id: string
  variant: ToastVariant
  title: string
  description?: string
  duration?: number
}

interface ToastStore {
  toasts: ToastItem[]
  push: (item: Omit<ToastItem, 'id'>) => void
  dismiss: (id: string) => void
}

let counter = 0

export const useToastStore = create<ToastStore>((set) => ({
  toasts: [],
  push: (item) => {
    const id = String(++counter)
    const duration = item.duration ?? 4000
    set((s) => ({ toasts: [...s.toasts, { ...item, id }] }))
    if (duration > 0) {
      setTimeout(() => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })), duration)
    }
  },
  dismiss: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}))

export function useToast() {
  const push = useToastStore((s) => s.push)
  return {
    success: (title: string, description?: string) => push({ variant: 'success', title, description }),
    error: (title: string, description?: string) => push({ variant: 'error', title, description }),
    warning: (title: string, description?: string) => push({ variant: 'warning', title, description }),
    info: (title: string, description?: string) => push({ variant: 'info', title, description }),
  }
}
