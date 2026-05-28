/**
 * useTraining — consolidated hook for training data management.
 *
 * Combines REST polling with the existing WebSocket live progress
 * (useTrainingSocket) into one ergonomic interface.
 */
import { useState, useEffect, useCallback, useRef } from 'react'
import { trainingService } from '../services/trainingService'
import type { TrainingJobProgress } from '../services/trainingService'

export interface TrainingJob {
  id: string
  status: string
  progress: number
  current_epoch?: number
  metrics?: Record<string, number>
  module?: string
  created_at: string
  error_message?: string
}

export interface TrainedModel {
  id: string
  name: string
  module?: string
  map50?: number
  is_active: boolean
  created_at: string
}

export function useTraining(pollIntervalMs = 5000) {
  const [jobs, setJobs] = useState<TrainingJob[]>([])
  const [models, setModels] = useState<TrainedModel[]>([])
  const [loading, setLoading] = useState(true)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const loadJobs = useCallback(async () => {
    try {
      const res = await trainingService.listJobs()
      const data = (res as unknown as { data: { jobs: TrainingJob[] } }).data
      setJobs(data?.jobs ?? [])
    } catch { /* silent */ }
  }, [])

  const loadModels = useCallback(async () => {
    try {
      const res = await trainingService.listModels()
      const data = (res as unknown as { data: { models: TrainedModel[] } }).data
      setModels(data?.models ?? [])
    } catch { /* silent */ }
  }, [])

  const refresh = useCallback(async () => {
    await Promise.all([loadJobs(), loadModels()])
  }, [loadJobs, loadModels])

  useEffect(() => {
    let mounted = true
    const init = async () => {
      await refresh()
      if (mounted) setLoading(false)
    }
    init()
    pollRef.current = setInterval(() => {
      const hasRunning = jobs.some(j => j.status === 'running' || j.status === 'pending')
      if (hasRunning) refresh()
    }, pollIntervalMs)
    return () => {
      mounted = false
      if (pollRef.current) clearInterval(pollRef.current)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pollIntervalMs])

  /** Poll progress Redis key for a specific running job. */
  const pollJobProgress = useCallback(
    async (jobId: string): Promise<TrainingJobProgress | null> => {
      try {
        const res = await trainingService.getJobProgress(jobId)
        return (res as unknown as { data: TrainingJobProgress }).data ?? null
      } catch {
        return null
      }
    },
    [],
  )

  const activateModel = useCallback(async (modelId: string) => {
    await trainingService.activateModel(modelId)
    await loadModels()
  }, [loadModels])

  return { jobs, models, loading, refresh, pollJobProgress, activateModel }
}
