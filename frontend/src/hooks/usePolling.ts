/**
 * Polling com exponential backoff.
 *
 * LIÇÃO V1: setInterval fixo flooda o backend quando ele cai.
 * Este hook é OBRIGATÓRIO para qualquer dado que precise atualizar.
 *
 * Comportamento:
 *   - Sucesso: volta para o intervalo base
 *   - Falha 1: 2x o intervalo
 *   - Falha 2: 4x o intervalo
 *   - Falha N: min(base * 2^N, maxInterval)
 */
import { useEffect, useRef } from 'react'

export function usePolling(
  fn: () => Promise<void>,
  interval = 5000,
  options: { maxInterval?: number; enabled?: boolean } = {}
) {
  const { maxInterval = 60000, enabled = true } = options
  const timeout = useRef<ReturnType<typeof setTimeout>>()
  const fails = useRef(0)
  const cancelled = useRef(false)

  useEffect(() => {
    if (!enabled) return
    cancelled.current = false
    fails.current = 0

    const poll = async () => {
      if (cancelled.current) return
      try {
        await fn()
        fails.current = 0
        if (!cancelled.current) timeout.current = setTimeout(poll, interval)
      } catch {
        fails.current++
        const backoff = Math.min(interval * 2 ** (fails.current - 1), maxInterval)
        if (!cancelled.current) timeout.current = setTimeout(poll, backoff)
      }
    }

    poll()
    return () => {
      cancelled.current = true
      if (timeout.current) clearTimeout(timeout.current)
    }
  }, [enabled, interval, maxInterval])
}
