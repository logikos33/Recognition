/**
 * Chat store — persists messages across navigation via Zustand + localStorage.
 */
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export interface ChatMessage {
  id: string
  role: 'system' | 'user' | 'bot'
  text: string
  ts: string
}

interface ChatStore {
  messages: ChatMessage[]
  isStreaming: boolean
  addMessage: (msg: ChatMessage) => void
  appendToLastBot: (token: string) => void
  setStreaming: (v: boolean) => void
  clearMessages: () => void
}

const INITIAL_MESSAGE: ChatMessage = {
  id: '0',
  role: 'system',
  text: 'Recognition Assistant conectado. Como posso ajudar?',
  ts: new Date().toISOString(),
}

export const useChatStore = create<ChatStore>()(
  persist(
    (set) => ({
      messages: [INITIAL_MESSAGE],
      isStreaming: false,

      addMessage: (msg) =>
        set((state) => ({
          messages: [...state.messages.slice(-99), msg],
        })),

      appendToLastBot: (token) =>
        set((state) => {
          const msgs = [...state.messages]
          const last = msgs[msgs.length - 1]
          if (last?.role === 'bot') {
            msgs[msgs.length - 1] = { ...last, text: last.text + token }
          }
          return { messages: msgs }
        }),

      setStreaming: (v) => set({ isStreaming: v }),

      clearMessages: () =>
        set({ messages: [INITIAL_MESSAGE], isStreaming: false }),
    }),
    {
      name: 'epi-chat-messages',
      partialize: (state) => ({ messages: state.messages }),
    }
  )
)
