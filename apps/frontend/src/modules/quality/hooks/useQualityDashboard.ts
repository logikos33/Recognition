import { useState, useEffect, useCallback, useRef } from 'react'
import { qualityDashboardService } from '../services/qualityDashboardService'
import type { DashboardSummary, StationLive } from '../types/qualityDashboard'

const SUMMARY_INTERVAL_MS = 15_000
const STATIONS_INTERVAL_MS = 5_000
const MAX_BACKOFF_MS = 60_000

export interface QualityDashboardState {
  summary: DashboardSummary | null
  stations: StationLive[]
  summaryLoading: boolean
  stationsLoading: boolean
  summaryError: string | null
  stationsError: string | null
  refresh: () => void
}

export function useQualityDashboard(): QualityDashboardState {
  const [summary, setSummary] = useState<DashboardSummary | null>(null)
  const [stations, setStations] = useState<StationLive[]>([])
  const [summaryLoading, setSummaryLoading] = useState(true)
  const [stationsLoading, setStationsLoading] = useState(true)
  const [summaryError, setSummaryError] = useState<string | null>(null)
  const [stationsError, setStationsError] = useState<string | null>(null)

  const summaryBackoff = useRef(SUMMARY_INTERVAL_MS)
  const stationsBackoff = useRef(STATIONS_INTERVAL_MS)
  const summaryTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const stationsTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const mounted = useRef(true)

  const fetchSummary = useCallback(async () => {
    if (!mounted.current) return
    try {
      const res = await qualityDashboardService.getSummary()
      if (!mounted.current) return
      setSummary(res.data.summary)
      setSummaryError(null)
      summaryBackoff.current = SUMMARY_INTERVAL_MS
    } catch (e) {
      if (!mounted.current) return
      setSummaryError(e instanceof Error ? e.message : 'Erro ao carregar totais')
      summaryBackoff.current = Math.min(summaryBackoff.current * 2, MAX_BACKOFF_MS)
    } finally {
      if (mounted.current) setSummaryLoading(false)
    }
    if (mounted.current) {
      summaryTimer.current = setTimeout(fetchSummary, summaryBackoff.current)
    }
  }, [])

  const fetchStations = useCallback(async () => {
    if (!mounted.current) return
    try {
      const res = await qualityDashboardService.getStations()
      if (!mounted.current) return
      setStations(res.data.stations)
      setStationsError(null)
      stationsBackoff.current = STATIONS_INTERVAL_MS
    } catch (e) {
      if (!mounted.current) return
      setStationsError(e instanceof Error ? e.message : 'Erro ao carregar estações')
      stationsBackoff.current = Math.min(stationsBackoff.current * 2, MAX_BACKOFF_MS)
    } finally {
      if (mounted.current) setStationsLoading(false)
    }
    if (mounted.current) {
      stationsTimer.current = setTimeout(fetchStations, stationsBackoff.current)
    }
  }, [])

  useEffect(() => {
    mounted.current = true
    fetchSummary()
    fetchStations()
    return () => {
      mounted.current = false
      if (summaryTimer.current) clearTimeout(summaryTimer.current)
      if (stationsTimer.current) clearTimeout(stationsTimer.current)
    }
  }, [fetchSummary, fetchStations])

  const refresh = useCallback(() => {
    if (summaryTimer.current) clearTimeout(summaryTimer.current)
    if (stationsTimer.current) clearTimeout(stationsTimer.current)
    summaryBackoff.current = SUMMARY_INTERVAL_MS
    stationsBackoff.current = STATIONS_INTERVAL_MS
    setSummaryLoading(true)
    setStationsLoading(true)
    fetchSummary()
    fetchStations()
  }, [fetchSummary, fetchStations])

  return {
    summary, stations,
    summaryLoading, stationsLoading,
    summaryError, stationsError,
    refresh,
  }
}
