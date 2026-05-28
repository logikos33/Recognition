/**
 * Hook para eventos WebSocket do módulo de qualidade.
 * Assina o namespace /quality via socket.io-client.
 *
 * Eventos recebidos:
 *   quality_inspection  → nova inspeção processada
 *   quality_cep_alert   → processo fora de controle
 *   quality_andon       → dados ao vivo para Andon
 */
import { useEffect, useRef, useState } from 'react'
import type { QualityInspectionEvent, QualityCepAlertEvent } from '../types/quality'

interface QualityWebSocketState {
  lastInspection: QualityInspectionEvent | null
  lastCepAlert: QualityCepAlertEvent | null
  connected: boolean
}

export function useQualityWebSocket(cameraId?: string) {
  const [state, setState] = useState<QualityWebSocketState>({
    lastInspection: null,
    lastCepAlert: null,
    connected: false,
  })
  const socketRef = useRef<ReturnType<typeof import('socket.io-client')['io']> | null>(null)

  useEffect(() => {
    let socket: ReturnType<typeof import('socket.io-client')['io']> | null = null

    async function connect() {
      const { io } = await import('socket.io-client')
      const wsBase = import.meta.env.VITE_WS_URL
        || import.meta.env.VITE_API_URL
        || window.location.origin

      socket = io(`${wsBase}/quality`, {
        transports: ['websocket', 'polling'],
        autoConnect: true,
        reconnection: true,
        reconnectionDelay: 2000,
        reconnectionAttempts: 10,
      })

      socketRef.current = socket

      socket.on('connect', () => {
        setState(s => ({ ...s, connected: true }))
      })

      socket.on('disconnect', () => {
        setState(s => ({ ...s, connected: false }))
      })

      socket.on('quality_inspection', (data: QualityInspectionEvent) => {
        // Filtrar por câmera se especificado
        if (cameraId && data.camera_id !== cameraId) return
        setState(s => ({ ...s, lastInspection: data }))
      })

      socket.on('quality_cep_alert', (data: QualityCepAlertEvent) => {
        if (cameraId && data.camera_id !== cameraId) return
        setState(s => ({ ...s, lastCepAlert: data }))
      })
    }

    connect()

    return () => {
      socket?.disconnect()
      socketRef.current = null
    }
  }, [cameraId])

  return state
}
