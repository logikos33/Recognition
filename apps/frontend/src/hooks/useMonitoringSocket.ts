/**
 * Hook para WebSocket de monitoramento em tempo real.
 *
 * Conecta ao WS Gateway no namespace /monitor e gerencia:
 * - Conexão com autenticação via token
 * - Subscribe/unsubscribe de câmeras
 * - Recebimento de detecções e alertas
 * - Reconexão automática (socket.io built-in)
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { io, Socket } from 'socket.io-client'

export interface Detection {
  class: string
  confidence: number
  bbox: [number, number, number, number]  // x, y, w, h
  is_violation?: boolean
}

export interface DetectionEvent {
  camera_id: string
  timestamp: string
  detections: Detection[]
  has_violation: boolean
}

export interface AlertEvent {
  id?: string
  camera_id: string
  violations: Detection[]
  created_at?: string
  tenant_id?: string
}

interface UseMonitoringSocketOptions {
  wsUrl: string
  token: string
  enabled?: boolean
}

export function useMonitoringSocket({ wsUrl, token, enabled = true }: UseMonitoringSocketOptions) {
  const socketRef = useRef<Socket | null>(null)
  const [connected, setConnected] = useState(false)
  const [detections, setDetections] = useState<Record<string, Detection[]>>({})
  const [alerts, setAlerts] = useState<AlertEvent[]>([])
  const subscribedCameras = useRef<Set<string>>(new Set())

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

    socket.on('connect', () => {
      setConnected(true)
      // Re-subscribe all cameras after reconnect
      for (const cameraId of subscribedCameras.current) {
        socket.emit('subscribe_camera', { camera_id: cameraId })
      }
    })

    socket.on('disconnect', () => {
      setConnected(false)
    })

    socket.on('detection', (data: DetectionEvent) => {
      setDetections(prev => ({
        ...prev,
        [data.camera_id]: data.detections,
      }))
    })

    socket.on('alert', (data: AlertEvent) => {
      setAlerts(prev => [data, ...prev].slice(0, 100))
    })

    socketRef.current = socket

    return () => {
      socket.disconnect()
      socketRef.current = null
      setConnected(false)
    }
  }, [wsUrl, token, enabled])

  const subscribeCamera = useCallback((cameraId: string) => {
    subscribedCameras.current.add(cameraId)
    socketRef.current?.emit('subscribe_camera', { camera_id: cameraId })
  }, [])

  const unsubscribeCamera = useCallback((cameraId: string) => {
    subscribedCameras.current.delete(cameraId)
    socketRef.current?.emit('unsubscribe_camera', { camera_id: cameraId })
    setDetections(prev => {
      const next = { ...prev }
      delete next[cameraId]
      return next
    })
  }, [])

  const clearAlerts = useCallback(() => {
    setAlerts([])
  }, [])

  return {
    connected,
    detections,
    alerts,
    subscribeCamera,
    unsubscribeCamera,
    clearAlerts,
  }
}
