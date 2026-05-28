/**
 * Hook para WebSocket de progresso de treinamento em tempo real.
 *
 * Conecta ao namespace /training e recebe eventos training_progress
 * publicados pelo training-service via Redis → socket_bridge.
 *
 * Payload do evento:
 *   {job_id, status, progress, epoch?, total_epochs?, loss?, metrics?, eta_seconds?}
 */
import { useEffect, useRef, useState } from 'react'
import { io, Socket } from 'socket.io-client'

export interface TrainingMetrics {
  loss?: number
  map50?: number
  precision?: number
  recall?: number
}

export interface TrainingProgressEvent {
  job_id: string
  status: 'creating_pod' | 'training' | 'completed' | 'failed' | 'pending'
  progress: number          // 0-100
  epoch?: number
  total_epochs?: number
  loss?: number
  metrics?: TrainingMetrics
  eta_seconds?: number
  error?: string
  model_key?: string
  timestamp?: string
}

export interface TrainingJobState {
  status: TrainingProgressEvent['status']
  progress: number
  epoch: number
  total_epochs: number
  metrics: TrainingMetrics
  eta_seconds: number
  error?: string
  model_key?: string
  // Histórico para gráficos
  lossHistory: number[]
  map50History: number[]
}

const DEFAULT_STATE: TrainingJobState = {
  status: 'pending',
  progress: 0,
  epoch: 0,
  total_epochs: 0,
  metrics: {},
  eta_seconds: 0,
  lossHistory: [],
  map50History: [],
}

interface UseTrainingSocketOptions {
  wsUrl: string
  token: string
  enabled?: boolean
}

export function useTrainingSocket({ wsUrl, token, enabled = true }: UseTrainingSocketOptions) {
  const socketRef = useRef<Socket | null>(null)
  const [connected, setConnected] = useState(false)
  const [jobs, setJobs] = useState<Record<string, TrainingJobState>>({})

  useEffect(() => {
    if (!enabled || !wsUrl || !token) return

    const socket = io(`${wsUrl}/training`, {
      query: { token },
      transports: ['websocket'],
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 10000,
      reconnectionAttempts: Infinity,
    })

    socket.on('connect', () => setConnected(true))
    socket.on('disconnect', () => setConnected(false))

    socket.on('training_progress', (data: TrainingProgressEvent) => {
      const { job_id, status, progress, epoch, total_epochs, loss, metrics, eta_seconds, error, model_key } = data

      setJobs(prev => {
        const existing = prev[job_id] ?? { ...DEFAULT_STATE }
        const lossHistory = loss != null
          ? [...existing.lossHistory, loss].slice(-200)
          : existing.lossHistory
        const map50History = metrics?.map50 != null
          ? [...existing.map50History, metrics.map50].slice(-200)
          : existing.map50History

        return {
          ...prev,
          [job_id]: {
            status,
            progress,
            epoch: epoch ?? existing.epoch,
            total_epochs: total_epochs ?? existing.total_epochs,
            metrics: { ...existing.metrics, ...metrics },
            eta_seconds: eta_seconds ?? existing.eta_seconds,
            error,
            model_key,
            lossHistory,
            map50History,
          },
        }
      })
    })

    socketRef.current = socket
    return () => {
      socket.disconnect()
      socketRef.current = null
      setConnected(false)
    }
  }, [wsUrl, token, enabled])

  return { connected, jobs }
}
