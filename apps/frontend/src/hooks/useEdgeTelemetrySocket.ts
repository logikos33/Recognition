/**
 * Hook para telemetria do EDGE ao vivo (task-112, ADR-0053).
 *
 * Espelha useMonitoringSocket: conecta ao namespace /monitor e escuta o evento
 * "edge_telemetry" emitido pelo bridge Redis→SocketIO (canal Redis
 * edge_telemetry:{tenant_id}, publicado no ingest POST /api/v1/dashboard/edge-telemetry).
 *
 * Mantém um buffer curto (últimas N amostras) para sparklines + a última amostra
 * para os gauges. Reconexão automática (socket.io built-in).
 */
import { useEffect, useRef, useState } from 'react'
import { io, Socket } from 'socket.io-client'
import type { TelemetryPayload } from '../services/dashboardEdgeService'

export interface EdgeTelemetryEvent {
  tenant_id?: string
  site_id: string | null
  label: string | null
  sampled_at: string
  payload: TelemetryPayload
}

interface UseEdgeTelemetrySocketOptions {
  wsUrl: string
  token: string
  enabled?: boolean
  /** Máximo de amostras retidas para sparklines (default 120). */
  bufferSize?: number
}

export function useEdgeTelemetrySocket({
  wsUrl,
  token,
  enabled = true,
  bufferSize = 120,
}: UseEdgeTelemetrySocketOptions) {
  const socketRef = useRef<Socket | null>(null)
  const [connected, setConnected] = useState(false)
  const [samples, setSamples] = useState<EdgeTelemetryEvent[]>([])

  useEffect(() => {
    if (!enabled || !wsUrl || !token) return

    const socket = io(`${wsUrl}/monitor`, {
      // JWT no handshake (socket_auth.py lê `auth.token`; `?token=` na query só por
      // compatibilidade — token na URL vaza para logs de acesso).
      auth: { token },
      transports: ['websocket'],
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 10000,
      reconnectionAttempts: Infinity,
    })

    socket.on('connect', () => setConnected(true))
    socket.on('disconnect', () => setConnected(false))

    socket.on('edge_telemetry', (data: EdgeTelemetryEvent) => {
      setSamples((prev) => [...prev, data].slice(-bufferSize))
    })

    socketRef.current = socket
    return () => {
      socket.disconnect()
      socketRef.current = null
      setConnected(false)
    }
  }, [wsUrl, token, enabled, bufferSize])

  const latest = samples.length > 0 ? samples[samples.length - 1] : null

  return { connected, samples, latest }
}
