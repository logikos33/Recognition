/**
 * ChatFAB — floating action button + chat panel com streaming SSE.
 * Conecta ao endpoint POST /api/chat (Ollama backend).
 * Fallback: mensagem de erro se Ollama estiver offline.
 */
import { useState, useEffect, useRef } from 'react'
import { MessageCircle, X, Send } from 'lucide-react'
import { useChatStore } from '../../stores/chatStore'
import { getToken } from '../../services/api'
import {
  fab, panelOverlay, chatPanel, chatHeader, chatTitle,
  chatBody, msgSystem, msgUser, msgBot,
  chatInputRow, chatInput, chatSendBtn,
} from './chat.css'

export function ChatFAB() {
  const [open, setOpen] = useState(false)
  const messages = useChatStore((s) => s.messages)
  const isStreaming = useChatStore((s) => s.isStreaming)
  const addMessage = useChatStore((s) => s.addMessage)
  const appendToLastBot = useChatStore((s) => s.appendToLastBot)
  const setStreaming = useChatStore((s) => s.setStreaming)
  const [input, setInput] = useState('')
  const bodyRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }
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
    if (!text || isStreaming) return

    const userMsg = { id: `u-${Date.now()}`, role: 'user' as const, text, ts: new Date().toISOString() }
    addMessage(userMsg)
    setInput('')
    setStreaming(true)

    // Cria mensagem bot vazia para receber tokens em streaming
    const botId = `b-${Date.now()}`
    addMessage({ id: botId, role: 'bot', text: '', ts: new Date().toISOString() })

    try {
      const token = getToken()
      const history = messages.slice(-6).map(m => ({ role: m.role, text: m.text }))

      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ message: text, history }),
      })

      if (!response.ok || !response.body) {
        appendToLastBot('Assistente indisponível no momento.')
        return
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        const chunk = decoder.decode(value, { stream: true })
        for (const line of chunk.split('\n')) {
          if (!line.startsWith('data: ')) continue
          const payload = line.slice(6).trim()
          if (payload === '[DONE]') break
          try {
            const parsed = JSON.parse(payload)
            if (parsed.token) appendToLastBot(parsed.token)
            if (parsed.error) appendToLastBot(parsed.error)
          } catch {
            // linha malformada, ignorar
          }
        }
      }
    } catch {
      appendToLastBot('Erro ao conectar com o assistente.')
    } finally {
      setStreaming(false)
    }
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
          {isStreaming && messages[messages.length - 1]?.role === 'bot' && !messages[messages.length - 1]?.text && (
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
            disabled={isStreaming}
            autoFocus
          />
          <button className={chatSendBtn} onClick={send} disabled={!input.trim() || isStreaming}>
            <Send size={16} />
          </button>
        </div>
      </div>
    </>
  )
}
