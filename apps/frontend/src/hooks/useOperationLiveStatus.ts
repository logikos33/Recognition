/**
 * Hook para status em tempo real de operações via Socket.io.
 * Espelha padrão de useMonitoringSocket — conexão no namespace /monitor.
 * Conexão separada do useMonitoringSocket (SRP — não criar god-hook).
 */
import { useEffect, useRef, useState } from 'react'
import { io, Socket } from 'socket.io-client'
import type { OperationStatusEvent, OperationReloadedEvent, OperationStatus } from '../types/operations'

interface UseOperationLiveStatusOptions {
  wsUrl: string
  token: string
  operationIds: number[]
  enabled?: boolean
}

interface LiveStatus {
  status: OperationStatus
  last_value?: unknown
  timestamp?: string
}

export function useOperationLiveStatus({
  wsUrl,
  token,
  operationIds: _operationIds,
  enabled = true,
}: UseOperationLiveStatusOptions) {
  const socketRef = useRef<Socket | null>(null)
  const [connected, setConnected] = useState(false)
  const [liveStatuses, setLiveStatuses] = useState<Record<number, LiveStatus>>({})
  const [reloadedIds, setReloadedIds] = useState<Set<number>>(new Set())

  useEffect(() => {
    if (!enabled || !wsUrl || !token) return

    const socket = io(`${wsUrl}/monitor`, {
      query: { token },
      transports: ['websocket'],
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 10000,
      reconnectionAttempts: Infinity,
    })

    socket.on('connect', () => setConnected(true))
    socket.on('disconnect', () => setConnected(false))

    socket.on('operation:status_changed', (data: OperationStatusEvent) => {
      setLiveStatuses(prev => ({
        ...prev,
        [data.operation_id]: {
          status: data.status,
          last_value: data.last_value,
          timestamp: data.timestamp,
        },
      }))
    })

    socket.on('operation:reloaded', (data: OperationReloadedEvent) => {
      setReloadedIds(prev => new Set(prev).add(data.operation_id))
      // Limpa após 3 segundos para não acumular
      setTimeout(() => {
        setReloadedIds(prev => {
          const next = new Set(prev)
          next.delete(data.operation_id)
          return next
        })
      }, 3000)
    })

    socketRef.current = socket

    return () => {
      socket.disconnect()
      socketRef.current = null
      setConnected(false)
    }
  }, [wsUrl, token, enabled])

  return { connected, liveStatuses, reloadedIds }
}
