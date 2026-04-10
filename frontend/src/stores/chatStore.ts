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
  addMessage: (msg: ChatMessage) => void
  clearMessages: () => void
}

export const useChatStore = create<ChatStore>()(
  persist(
    (set) => ({
      messages: [
        {
          id: '0',
          role: 'system',
          text: 'EPI Monitor Assistant conectado. Como posso ajudar?',
          ts: new Date().toISOString(),
        },
      ],
      addMessage: (msg) =>
        set((state) => ({
          messages: [...state.messages.slice(-99), msg],
        })),
      clearMessages: () =>
        set({
          messages: [
            {
              id: '0',
              role: 'system',
              text: 'EPI Monitor Assistant conectado. Como posso ajudar?',
              ts: new Date().toISOString(),
            },
          ],
        }),
    }),
    {
      name: 'epi-chat-messages',
    }
  )
)
