/**
 * ChatFAB — floating action button + chat panel drawer.
 */
import { useState, useEffect, useRef } from 'react'
import { MessageCircle, X, Send } from 'lucide-react'
import {
  fab, panelOverlay, chatPanel, chatHeader, chatTitle,
  chatBody, msgSystem, msgUser, msgBot,
  chatInputRow, chatInput, chatSendBtn,
} from './chat.css'

interface ChatMessage {
  id: string
  role: 'system' | 'user' | 'bot'
  text: string
  ts: string
}

const MOCK_RESPONSES = [
  'Sistema operando normalmente. Todas as cameras ativas.',
  'Nenhum alerta critico nas ultimas 2 horas.',
  'Taxa de conformidade atual: 94%. Acima da meta de 90%.',
  'Proximo treinamento agendado para amanha as 08:00.',
  'Dica: use o painel lateral do grid para reorganizar cameras rapidamente.',
]

export function ChatFAB() {
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState<ChatMessage[]>([
    { id: '0', role: 'system', text: 'EPI Monitor Assistant conectado. Como posso ajudar?', ts: new Date().toISOString() },
  ])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const bodyRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [open])

  useEffect(() => {
    if (bodyRef.current) {
      bodyRef.current.scrollTop = bodyRef.current.scrollHeight
    }
  }, [messages])

  const send = async () => {
    const text = input.trim()
    if (!text || sending) return

    const userMsg: ChatMessage = {
      id: `u-${Date.now()}`, role: 'user', text, ts: new Date().toISOString(),
    }
    setMessages(m => [...m, userMsg])
    setInput('')
    setSending(true)

    // Mock response (replace with POST /api/chat when backend is ready)
    setTimeout(() => {
      const reply = MOCK_RESPONSES[Math.floor(Math.random() * MOCK_RESPONSES.length)]
      setMessages(m => [...m, {
        id: `b-${Date.now()}`, role: 'bot', text: reply, ts: new Date().toISOString(),
      }])
      setSending(false)
    }, 800)
  }

  if (!open) {
    return (
      <button className={fab} onClick={() => setOpen(true)} aria-label="Abrir chat">
        <MessageCircle size={24} />
      </button>
    )
  }

  return (
    <>
      <div className={panelOverlay} onClick={() => setOpen(false)} />
      <div className={chatPanel}>
        <div className={chatHeader}>
          <span className={chatTitle}>EPI Assistant</span>
          <button
            onClick={() => setOpen(false)}
            style={{ background: 'none', border: 'none', color: 'inherit', cursor: 'pointer', padding: 4 }}
            aria-label="Fechar chat"
          >
            <X size={18} />
          </button>
        </div>

        <div className={chatBody} ref={bodyRef}>
          {messages.map(msg => (
            <div
              key={msg.id}
              className={msg.role === 'system' ? msgSystem : msg.role === 'user' ? msgUser : msgBot}
            >
              {msg.text}
            </div>
          ))}
          {sending && (
            <div className={msgBot} style={{ opacity: 0.5 }}>Digitando...</div>
          )}
        </div>

        <div className={chatInputRow}>
          <input
            className={chatInput}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') send() }}
            placeholder="Digite sua pergunta..."
            autoFocus
          />
          <button className={chatSendBtn} onClick={send} disabled={!input.trim() || sending}>
            <Send size={16} />
          </button>
        </div>
      </div>
    </>
  )
}
