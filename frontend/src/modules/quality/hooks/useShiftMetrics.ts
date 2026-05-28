/**
 * Hook para métricas de turno atual com polling a cada 30s.
 */
import { useState, useEffect, useRef } from 'react'
import { qualityService } from '../services/qualityService'
import type { InspectionSummary } from '../types/quality'

function getCurrentShift(): 'morning' | 'afternoon' | 'night' {
  const hour = new Date().getHours()
  if (hour >= 6 && hour < 14) return 'morning'
  if (hour >= 14 && hour < 22) return 'afternoon'
  return 'night'
}

interface ShiftMetricsState {
  summary: InspectionSummary | null
  loading: boolean
  error: string | null
}

export function useShiftMetrics(cameraId?: string) {
  const [state, setState] = useState<ShiftMetricsState>({ summary: null, loading: true, error: null })
  const mountedRef = useRef(true)

  useEffect(() => {
    mountedRef.current = true

    async function fetch() {
      if (!mountedRef.current) return
      try {
        const res = await qualityService.getSummary({
          shift: getCurrentShift(),
          camera_id: cameraId,
          date: new Date().toISOString().slice(0, 10),
        })
        if (!mountedRef.current) return
        setState({ summary: res.data, loading: false, error: null })
      } catch {
        if (!mountedRef.current) return
        setState(s => ({ ...s, loading: false, error: 'Erro ao carregar métricas de turno' }))
      }
    }

    fetch()
    const interval = setInterval(fetch, 30_000)

    return () => {
      mountedRef.current = false
      clearInterval(interval)
    }
  }, [cameraId])

  return state
}
